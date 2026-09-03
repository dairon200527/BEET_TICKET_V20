"""
Deactivating a convenio (`PATCH /api/convenios/{id}` con estado=false —
soft delete, never a physical DELETE, since a real convenio almost always
already has unidades_inventario/transacciones/plantillas with no
ON DELETE CASCADE) must make it disappear from the affiliate catalog and
from "pick a convenio" selectors, while its PAST sales stay intact in
historical dashboard/reportes figures. See routers/convenios.py
(catalogo, listar), routers/dashboard.py (stats).
"""
from __future__ import annotations

from app.models.enums import EstadoTransaccion, MetodoPago
from app.models.plantilla import Plantilla
from app.models.transaccion import Transaccion
from app.models.unidad_inventario import UnidadInventario
from tests.conftest import admin_token, afiliado_token, auth_headers


def test_desactivar_convenio_con_inventario_y_plantilla_no_truena(client, admin_a, convenio_a, db_session):
    """Acceptance test from the spec: deactivate a convenio that already
    has inventory AND at least 1 (real, per-convenio) plantilla — nothing
    must break."""
    db_session.add(UnidadInventario(convenio_id=convenio_a.id, codigo="ACPT-001"))
    db_session.add(Plantilla(convenio_id=convenio_a.id, nombre="Diseño de prueba", version=1, storage_path="plantillas/test.json"))
    db_session.commit()

    token = admin_token(admin_a)
    resp = client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"estado": False})
    assert resp.status_code == 200
    assert resp.json()["estado"] is False


def test_convenio_desactivado_desaparece_del_catalogo_del_afiliado(client, afiliado_a, convenio_a, db_session):
    db_session.add(UnidadInventario(convenio_id=convenio_a.id, codigo="CAT-001"))
    convenio_a.estado = True
    db_session.commit()

    token = afiliado_token(afiliado_a)
    antes = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert any(c["id"] == convenio_a.id for c in antes.json())

    convenio_a.estado = False
    db_session.commit()

    despues = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert not any(c["id"] == convenio_a.id for c in despues.json())


def test_listado_admin_sin_filtro_muestra_activos_e_inactivos(client, admin_a, convenio_a, db_session):
    convenio_a.estado = False
    db_session.commit()

    token = admin_token(admin_a)
    sin_filtro = client.get("/api/convenios", headers=auth_headers(token))
    assert any(c["id"] == convenio_a.id for c in sin_filtro.json()["items"])

    solo_activos = client.get("/api/convenios?estado=true", headers=auth_headers(token))
    assert not any(c["id"] == convenio_a.id for c in solo_activos.json()["items"])

    solo_inactivos = client.get("/api/convenios?estado=false", headers=auth_headers(token))
    assert any(c["id"] == convenio_a.id for c in solo_inactivos.json()["items"])


def test_dashboard_preserva_ventas_historicas_pero_no_cuenta_convenio_inactivo_como_activo(client, admin_a, afiliado_a, convenio_a, db_session):
    transaccion = Transaccion(
        afiliado_id=afiliado_a.id, convenio_id=convenio_a.id, cantidad=1,
        subtotal=10000, total=10000, metodo_pago=MetodoPago.TARJETA,
        estado=EstadoTransaccion.COMPLETADA,
    )
    db_session.add(transaccion)
    db_session.commit()

    token = admin_token(admin_a)
    antes = client.get("/api/dashboard/stats", headers=auth_headers(token)).json()
    assert antes["convenios_activos"] >= 1
    assert float(antes["ventas_del_mes"]) >= 10000

    convenio_a.estado = False
    db_session.commit()

    despues = client.get("/api/dashboard/stats", headers=auth_headers(token)).json()
    assert despues["convenios_activos"] == antes["convenios_activos"] - 1
    # Historical revenue from BEFORE deactivation must survive untouched —
    # the query never filters by Convenio.estado for this figure.
    assert float(despues["ventas_del_mes"]) == float(antes["ventas_del_mes"])
