"""POST /api/inventario/carga-masiva — bulk unit load across MULTIPLE
convenios in one file (unlike POST /api/inventario/carga, which loads
into one already-selected convenio). Each row names its own convenio by
nombre, scoped to the uploading admin's own cooperativa (see
../app/routers/inventario.py)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.unidad_inventario import UnidadInventario
from tests.conftest import admin_token, auth_headers


def _csv_upload(content: str):
    return {"file": ("inventario.csv", content.encode("utf-8"), "text/csv")}


def test_carga_masiva_creates_units_across_multiple_convenios(client, db_session, admin_a, cooperativa_a):
    from app.models.convenio import Convenio

    convenio_b = Convenio(
        cooperativa_id=cooperativa_a.id, nombre="Convenio B", precio_publico=5000, precio_beet=4000, fecha_inicio="2024-01-01"
    )
    db_session.add(convenio_b)
    db_session.commit()

    token = admin_token(admin_a)
    csv_content = (
        "convenio,codigo\n"
        "Convenio B,COD-B-001\n"
        "Convenio B,COD-B-002\n"
    )
    r = client.post("/api/inventario/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["creados"] == 2

    unidades = db_session.execute(select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_b.id)).scalars().all()
    assert len(unidades) == 2


def test_carga_masiva_unknown_convenio_name_is_invalid(client, admin_a):
    token = admin_token(admin_a)
    csv_content = "convenio,codigo\nNo Existe,COD-X-001\n"
    r = client.post("/api/inventario/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["invalidos"] == 1
    assert "no existe" in body["errores"][0]


def test_carga_masiva_duplicate_codigo_is_omitted_not_error(client, db_session, admin_a, convenio_a):
    from app.models.unidad_inventario import UnidadInventario as UI

    db_session.add(UI(convenio_id=convenio_a.id, codigo="COD-EXISTENTE"))
    db_session.commit()

    token = admin_token(admin_a)
    csv_content = f"convenio,codigo\n{convenio_a.nombre},COD-EXISTENTE\n"
    r = client.post("/api/inventario/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["omitidos"] == 1
    assert body["invalidos"] == 0


def test_carga_masiva_scoped_to_own_cooperativa(client, admin_a, admin_b, cooperativa_b, db_session):
    from app.models.convenio import Convenio

    convenio_otra = Convenio(
        cooperativa_id=cooperativa_b.id, nombre="Convenio Ajeno", precio_publico=1000, precio_beet=800, fecha_inicio="2024-01-01"
    )
    db_session.add(convenio_otra)
    db_session.commit()

    token = admin_token(admin_a)
    csv_content = "convenio,codigo\nConvenio Ajeno,COD-AJENO-001\n"
    r = client.post("/api/inventario/carga-masiva", files=_csv_upload(csv_content), headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    # admin_a's cooperativa doesn't have a convenio named "Convenio
    # Ajeno" (it belongs to cooperativa_b) — must be reported invalid, not
    # matched across tenants.
    assert body["invalidos"] == 1
