"""Regression tests for the bulk-upload reporting bug: re-uploading a file
where only 1 row/field genuinely changed used to report every matched row
as "actualizado" (afiliados: fields were always reassigned regardless of
whether the value differed; convenios: a full `model_dump()` overwrite
also reset untouched optional columns to their Pydantic defaults). Both
now diff field-by-field and only count/write a real change — see
routers/afiliados.py and routers/convenios.py."""
from __future__ import annotations

from io import BytesIO

import openpyxl

from app.models.convenio import Convenio
from tests.conftest import admin_token, auth_headers


def _xlsx(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return {"file": ("carga.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def test_afiliados_reupload_identico_reporta_sin_cambios(client, admin_a):
    token = admin_token(admin_a)
    headers = ["Documento", "Nombres", "Apellidos", "Correo", "Cupo total"]
    row = ["7001", "Ana", "Diff", "ana.diff@test.com", 500000]

    r1 = client.post("/api/afiliados/carga-masiva", files=_xlsx(headers, [row]), headers=auth_headers(token))
    assert r1.status_code == 200
    assert r1.json()["creados"] == 1

    # Re-upload the EXACT same row — nothing should count as "actualizado".
    r2 = client.post("/api/afiliados/carga-masiva", files=_xlsx(headers, [row]), headers=auth_headers(token))
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["creados"] == 0
    assert body2["actualizados"] == 0
    assert body2["omitidos"] == 1
    assert "sin cambios" in body2["detail"]
    assert body2["cambios"] == []


def test_afiliados_reupload_con_1_campo_distinto_reporta_solo_ese_cambio(client, db_session, admin_a):
    token = admin_token(admin_a)
    headers = ["Documento", "Nombres", "Apellidos", "Correo", "Cupo total"]
    fila_1 = ["7002", "Bruno", "Diff", "bruno.diff@test.com", 300000]
    fila_2 = ["7003", "Carla", "Diff", "carla.diff@test.com", 400000]

    r1 = client.post("/api/afiliados/carga-masiva", files=_xlsx(headers, [fila_1, fila_2]), headers=auth_headers(token))
    assert r1.status_code == 200
    assert r1.json()["creados"] == 2

    # Re-upload: fila_1 unchanged, fila_2's cupo_total goes from 400000 -> 450000.
    fila_2_modificada = ["7003", "Carla", "Diff", "carla.diff@test.com", 450000]
    r2 = client.post(
        "/api/afiliados/carga-masiva", files=_xlsx(headers, [fila_1, fila_2_modificada]), headers=auth_headers(token)
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["creados"] == 0
    assert body2["actualizados"] == 1  # only Carla's row
    assert body2["omitidos"] == 1  # Bruno's row: no real change
    assert len(body2["cambios"]) == 1
    assert "7003" not in body2["cambios"][0]  # cambios are keyed by Excel row number, not documento
    assert "cupo_total" in body2["cambios"][0]
    assert "400000" in body2["cambios"][0] and "450000" in body2["cambios"][0]


def test_convenios_reupload_con_celda_opcional_en_blanco_no_borra_el_valor_existente(client, db_session, admin_a, cooperativa_a):
    """The actual over-write risk the user flagged: a convenio already has
    a real `descripcion`; re-uploading a file that changes ONLY the price
    and leaves the Descripción cell blank must NOT wipe the existing
    descripcion — a blank optional cell on an UPDATE means "leave it",
    not "clear it" (same convention as `estado` in afiliados)."""
    token = admin_token(admin_a)
    headers = ["Nombre", "Descripción", "Precio publico", "Precio beet", "Fecha inicio", "Estado"]
    fila = ["Diff Convenio", "Descripción original detallada", 100000, 80000, "2024-01-01", "Activo"]

    r1 = client.post("/api/convenios/carga-masiva", files=_xlsx(headers, [fila]), headers=auth_headers(token))
    assert r1.status_code == 200
    assert r1.json()["creados"] == 1

    convenio = db_session.execute(
        __import__("sqlalchemy").select(Convenio).where(Convenio.nombre == "Diff Convenio")
    ).scalar_one()
    assert convenio.descripcion == "Descripción original detallada"
    assert convenio.estado is True

    # Re-upload: ONLY precio_beet changes (100000->95000... actually change precio_beet),
    # Descripción and Estado cells left BLANK this time.
    headers_sin_desc_ni_estado = ["Nombre", "Precio publico", "Precio beet", "Fecha inicio"]
    fila_modificada = ["Diff Convenio", 100000, 90000, "2024-01-01"]
    r2 = client.post(
        "/api/convenios/carga-masiva", files=_xlsx(headers_sin_desc_ni_estado, [fila_modificada]), headers=auth_headers(token)
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["actualizados"] == 1
    assert len(body2["cambios"]) == 1
    assert "precio_beet" in body2["cambios"][0]

    db_session.refresh(convenio)
    assert convenio.precio_beet == 90000
    # The whole point of the fix: these must NOT have been wiped/reset.
    assert convenio.descripcion == "Descripción original detallada"
    assert convenio.estado is True


def test_convenios_reupload_identico_reporta_sin_cambios(client, admin_a):
    token = admin_token(admin_a)
    headers = ["Nombre", "Precio publico", "Precio beet", "Fecha inicio"]
    fila = ["Convenio Estable", 50000, 40000, "2024-01-01"]

    r1 = client.post("/api/convenios/carga-masiva", files=_xlsx(headers, [fila]), headers=auth_headers(token))
    assert r1.status_code == 200
    assert r1.json()["creados"] == 1

    r2 = client.post("/api/convenios/carga-masiva", files=_xlsx(headers, [fila]), headers=auth_headers(token))
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["actualizados"] == 0
    assert body2["omitidos"] == 1
    assert body2["cambios"] == []
