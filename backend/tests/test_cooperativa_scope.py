"""Scenarios for the SUPER_ADMIN cooperativa-scope selector
(`resolve_cooperativa_scope`/`_write` in app/dependencies/auth.py):

- SUPER_ADMIN with no `?cooperativa_id=` -> 400.
- SUPER_ADMIN with a `?cooperativa_id=` that doesn't exist -> 404.
- SUPER_ADMIN with a valid `?cooperativa_id=` -> sees that cooperativa's
  real data, and a bulk upload lands there.
- ADMIN/LECTOR: a foreign `?cooperativa_id=` they send is silently
  ignored — they always stay scoped to their own cooperativa.
- Cooperativas CRUD (`POST /api/admin/cooperativas`).
"""
from __future__ import annotations

from tests.conftest import admin_token, auth_headers


def _csv_upload(content: str, filename: str = "carga.csv"):
    return {"file": (filename, content.encode("utf-8"), "text/csv")}


# --- SUPER_ADMIN must select a cooperativa ------------------------------
def test_superadmin_without_cooperativa_id_gets_400(client, superadmin_sin_cooperativa):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.get("/api/afiliados", headers=auth_headers(token))
    assert r.status_code == 400


def test_superadmin_dashboard_without_cooperativa_id_gets_400(client, superadmin_sin_cooperativa):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.get("/api/dashboard/stats", headers=auth_headers(token))
    assert r.status_code == 400


def test_superadmin_with_nonexistent_cooperativa_id_gets_404(client, superadmin_sin_cooperativa):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.get("/api/afiliados?cooperativa_id=999999", headers=auth_headers(token))
    assert r.status_code == 404


# --- SUPER_ADMIN with a valid selection sees real, correctly-scoped data ---
def test_superadmin_with_valid_cooperativa_id_sees_that_cooperativas_data(
    client, superadmin_sin_cooperativa, admin_a, afiliado_a, cooperativa_a, cooperativa_b
):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.get(f"/api/afiliados?cooperativa_id={cooperativa_a.id}", headers=auth_headers(token))
    assert r.status_code == 200
    documentos = {item["documento"] for item in r.json()["items"]}
    assert afiliado_a.documento in documentos

    # Switching the selection to the OTHER cooperativa must not leak A's data.
    r2 = client.get(f"/api/afiliados?cooperativa_id={cooperativa_b.id}", headers=auth_headers(token))
    assert r2.status_code == 200
    assert afiliado_a.documento not in {item["documento"] for item in r2.json()["items"]}


def test_superadmin_carga_masiva_lands_in_the_selected_cooperativa(
    client, db_session, superadmin_sin_cooperativa, cooperativa_a, cooperativa_b
):
    from sqlalchemy import select

    from app.models.afiliado import Afiliado

    token = admin_token(superadmin_sin_cooperativa)
    csv_content = "documento,nombres,apellidos,correo,cupo_total\n5551234,Test,Superadmin,test.sa@beetticket.test,100000\n"
    r = client.post(
        f"/api/afiliados/carga-masiva?cooperativa_id={cooperativa_b.id}",
        files=_csv_upload(csv_content),
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["creados"] == 1

    creado = db_session.execute(select(Afiliado).where(Afiliado.documento == "5551234")).scalar_one()
    assert creado.cooperativa_id == cooperativa_b.id


def test_superadmin_can_create_and_edit_the_selected_cooperativas_config(
    client, superadmin_sin_cooperativa, cooperativa_a
):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.get(f"/api/admin/cooperativa?cooperativa_id={cooperativa_a.id}", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["id"] == cooperativa_a.id

    r2 = client.patch(
        f"/api/admin/cooperativa?cooperativa_id={cooperativa_a.id}",
        json={"nombre": "Cooperativa A Renombrada"},
        headers=auth_headers(token),
    )
    assert r2.status_code == 200
    assert r2.json()["nombre"] == "Cooperativa A Renombrada"


# --- ADMIN/LECTOR: a foreign cooperativa_id is always ignored -----------
def test_admin_sending_foreign_cooperativa_id_is_ignored(client, admin_a, admin_b, cooperativa_b):
    token = admin_token(admin_a)
    # admin_a belongs to cooperativa_a — asking for cooperativa_b's id must
    # NOT leak cooperativa_b's data; admin_a still only sees its own.
    r = client.get(f"/api/afiliados?cooperativa_id={cooperativa_b.id}", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["items"] == []  # cooperativa_a has no afiliados here, and none of cooperativa_b's leak in


def test_lector_sending_foreign_cooperativa_id_is_ignored(client, lector_a, cooperativa_b):
    token = admin_token(lector_a)
    r = client.get(f"/api/convenios?cooperativa_id={cooperativa_b.id}", headers=auth_headers(token))
    assert r.status_code == 200  # never a 400/403 from the foreign id — it's just ignored


# --- Cooperativas CRUD ----------------------------------------------------
def test_crear_cooperativa_success(client, superadmin_sin_cooperativa):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.post(
        "/api/admin/cooperativas",
        json={"nombre": "Cooperativa Nueva", "nit": "900555555-5"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Cooperativa Nueva"
    assert body["estado"] is True

    r2 = client.get("/api/admin/cooperativas", headers=auth_headers(token))
    assert any(c["nombre"] == "Cooperativa Nueva" for c in r2.json())


def test_crear_cooperativa_duplicate_nit_fails(client, superadmin_sin_cooperativa, cooperativa_a):
    token = admin_token(superadmin_sin_cooperativa)
    r = client.post(
        "/api/admin/cooperativas",
        json={"nombre": "Otra Cooperativa", "nit": cooperativa_a.nit},
        headers=auth_headers(token),
    )
    assert r.status_code == 409


def test_admin_cannot_create_cooperativa(client, admin_a):
    token = admin_token(admin_a)
    r = client.post(
        "/api/admin/cooperativas",
        json={"nombre": "No debería poder", "nit": "900777777-7"},
        headers=auth_headers(token),
    )
    assert r.status_code == 403
