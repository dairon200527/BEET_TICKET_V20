"""The afiliados bulk-load endpoint (POST /api/afiliados/carga-masiva) —
a real UPSERT (not create-only): new documento creates the afiliado AND
its cupos_credito row; existing documento updates
nombres/apellidos/correo/telefono unconditionally, estado only if the
column has a value, and cupo_total via the same delta-adjustment policy
as PATCH /api/cupos/{id} — see ../app/routers/afiliados.py and
../app/services/cupo_service.ajustar_cupo_total."""
from __future__ import annotations

from sqlalchemy import select

from app.models.cupo_credito import CupoCredito
from tests.conftest import admin_token, auth_headers


def _csv_upload(content: str):
    return {"file": ("afiliados.csv", content.encode("utf-8"), "text/csv")}


def test_carga_masiva_creates_new_afiliados_with_cupo(client, db_session, admin_a):
    token = admin_token(admin_a)
    csv_content = (
        "documento,nombres,apellidos,correo,telefono,cupo_total\n"
        "500001,Ana,Perez,ana.perez@beetticket.test,3000000001,500000\n"
        "500002,Luis,Gomez,luis.gomez@beetticket.test,,300000\n"
    )
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "2 creados" in body["detail"]
    assert body["creados"] == 2

    r_list = client.get("/api/afiliados", headers=auth_headers(token))
    documentos = {a["documento"]: a["id"] for a in r_list.json()["items"]}
    assert {"500001", "500002"} <= set(documentos)

    cupo = db_session.execute(select(CupoCredito).where(CupoCredito.afiliado_id == documentos["500001"])).scalar_one()
    assert cupo.cupo_total == 500000
    assert cupo.cupo_disponible == 500000  # a freshly-assigned cupo, unspent


def test_carga_masiva_updates_existing_afiliado_by_documento(client, db_session, admin_a, afiliado_a):
    token = admin_token(admin_a)
    csv_content = (
        f"documento,nombres,apellidos,correo,cupo_total\n"
        f"{afiliado_a.documento},NuevoNombre,NuevoApellido,actualizado@beetticket.test,500000\n"
    )
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "1 actualizados" in body["detail"]
    assert body["actualizados"] == 1

    db_session.refresh(afiliado_a)
    assert afiliado_a.nombres == "NuevoNombre"
    assert afiliado_a.correo == "actualizado@beetticket.test"


def test_carga_masiva_cupo_total_change_adjusts_disponible_by_delta(client, db_session, admin_a, afiliado_a):
    # afiliado_a's fixture cupo: cupo_total=500000, cupo_disponible=500000.
    cupo = db_session.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado_a.id)).scalar_one()
    cupo.cupo_disponible = 100000  # simulate some of it already spent
    db_session.commit()

    token = admin_token(admin_a)
    csv_content = f"documento,nombres,apellidos,correo,cupo_total\n{afiliado_a.documento},{afiliado_a.nombres},{afiliado_a.apellidos},{afiliado_a.correo},600000\n"
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200

    db_session.refresh(cupo)
    assert cupo.cupo_total == 600000
    assert cupo.cupo_disponible == 200000  # 100000 + (600000 - 500000) delta


def test_carga_masiva_blank_estado_leaves_existing_estado_unchanged(client, db_session, admin_a, afiliado_a):
    afiliado_a.estado = False
    db_session.commit()

    token = admin_token(admin_a)
    csv_content = f"documento,nombres,apellidos,correo,cupo_total,estado\n{afiliado_a.documento},{afiliado_a.nombres},{afiliado_a.apellidos},{afiliado_a.correo},500000,\n"
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200

    db_session.refresh(afiliado_a)
    assert afiliado_a.estado is False  # untouched, since the estado cell was blank


def test_carga_masiva_explicit_estado_updates_it(client, db_session, admin_a, afiliado_a):
    token = admin_token(admin_a)
    csv_content = f"documento,nombres,apellidos,correo,cupo_total,estado\n{afiliado_a.documento},{afiliado_a.nombres},{afiliado_a.apellidos},{afiliado_a.correo},500000,inactivo\n"
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200

    db_session.refresh(afiliado_a)
    assert afiliado_a.estado is False


def test_carga_masiva_reports_invalid_rows_with_reason_without_failing_whole_batch(client, admin_a):
    token = admin_token(admin_a)
    csv_content = (
        "documento,nombres,apellidos,correo,cupo_total\n"
        "500010,Valido,Row,valido@beetticket.test,500000\n"
        ",SinDocumento,Row,x@beetticket.test,500000\n"
    )
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "1 creados" in body["detail"]
    assert "1 inválidos" in body["detail"]
    assert body["invalidos"] == 1
    assert len(body["errores"]) == 1
    assert "Fila 3" in body["errores"][0]


def test_carga_masiva_never_touches_an_afiliado_absent_from_the_file(client, db_session, admin_a, afiliado_a):
    token = admin_token(admin_a)
    csv_content = "documento,nombres,apellidos,correo,cupo_total\n999999,Otro,Afiliado,otro2@beetticket.test,100000\n"
    r = client.post("/api/afiliados/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200

    db_session.refresh(afiliado_a)
    assert afiliado_a.nombres == "Afiliado"  # unchanged from the fixture's original value
