"""Scenarios: bulk convenio load (create + update-by-nombre), same
validate-per-row / never-all-or-nothing pattern as the afiliados bulk
load (see ../app/routers/convenios.py)."""
from __future__ import annotations

from tests.conftest import admin_token, auth_headers


def _csv_upload(content: str):
    return {"file": ("convenios.csv", content.encode("utf-8"), "text/csv")}


def test_carga_masiva_creates_new_convenios(client, admin_a):
    token = admin_token(admin_a)
    csv_content = (
        "nombre,descripcion,precio_publico,precio_beet,fecha_inicio,fecha_fin,estado\n"
        "Gimnasio Central,Acceso full,100000,80000,2024-01-01,,true\n"
        "Spa Relax,Masajes,50000,40000,2024-01-01,2025-12-31,true\n"
    )
    r = client.post("/api/convenios/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    assert "2 creados" in r.json()["detail"]

    r_list = client.get("/api/convenios", headers=auth_headers(token))
    nombres = {item["nombre"] for item in r_list.json()["items"]}
    assert {"Gimnasio Central", "Spa Relax"} <= nombres


def test_carga_masiva_updates_existing_by_nombre(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    csv_content = (
        "nombre,precio_publico,precio_beet,fecha_inicio\n"
        f"{convenio_a.nombre},20000,15000,2024-01-01\n"
    )
    r = client.post("/api/convenios/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    assert "1 actualizados" in r.json()["detail"]

    r_get = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token))
    assert r_get.json()["precio_beet"] == "15000.00" or float(r_get.json()["precio_beet"]) == 15000


def test_carga_masiva_reports_invalid_rows_without_failing_whole_batch(client, admin_a):
    token = admin_token(admin_a)
    csv_content = (
        "nombre,precio_publico,precio_beet,fecha_inicio\n"
        "Valido,10000,8000,2024-01-01\n"
        ",10000,8000,2024-01-01\n"  # missing nombre -> invalid
        "PrecioInvertido,5000,9000,2024-01-01\n"  # beet > publico -> invalid
    )
    r = client.post("/api/convenios/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()["detail"]
    assert "1 creados" in body
    assert "2 inválidos" in body


def test_carga_masiva_is_scoped_to_own_cooperativa(client, admin_a, admin_b):
    token_a = admin_token(admin_a)
    csv_content = "nombre,precio_publico,precio_beet,fecha_inicio\nSoloCoopA,10000,8000,2024-01-01\n"
    client.post("/api/convenios/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token_a))

    token_b = admin_token(admin_b)
    r = client.get("/api/convenios", headers=auth_headers(token_b))
    nombres = {item["nombre"] for item in r.json()["items"]}
    assert "SoloCoopA" not in nombres


def test_carga_masiva_rejects_unsupported_extension(client, admin_a):
    token = admin_token(admin_a)
    files = {"file": ("convenios.txt", b"nombre\nX\n", "text/plain")}
    r = client.post("/api/convenios/carga-masiva", files=files, headers=auth_headers(token))
    assert r.status_code == 400
