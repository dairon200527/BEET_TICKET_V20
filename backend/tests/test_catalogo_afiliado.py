"""GET /api/convenios/catalogo (affiliate-facing) must hide any convenio
that has sold out its inventory entirely — not just flag it — while the
admin-facing GET /api/convenios must keep showing every convenio
regardless of stock (see ../app/routers/convenios.py)."""
from __future__ import annotations

from app.models.enums import EstadoUnidadInventario
from app.models.unidad_inventario import UnidadInventario
from tests.conftest import afiliado_token, auth_headers, crear_unidades


def test_catalogo_oculta_convenio_sin_inventario(client, db_session, afiliado_a, convenio_a):
    # convenio_a has zero unidades_inventario at all (fixture creates none)
    token = afiliado_token(afiliado_a)
    r = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert r.status_code == 200
    assert convenio_a.id not in {c["id"] for c in r.json()}


def test_catalogo_muestra_convenio_con_inventario_disponible(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=2)
    token = afiliado_token(afiliado_a)
    r = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert r.status_code == 200
    encontrado = next((c for c in r.json() if c["id"] == convenio_a.id), None)
    assert encontrado is not None
    assert encontrado["unidades_disponibles"] == 2


def test_catalogo_oculta_convenio_cuando_inventario_llega_a_cero(client, db_session, afiliado_a, convenio_a):
    """The exact scenario the bug report described: a convenio existía,
    estaba activo, y su inventario llegó a 0 — debe desaparecer, no solo
    mostrarse deshabilitado."""
    unidades = crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)

    r = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert convenio_a.id in {c["id"] for c in r.json()}

    unidades[0].estado = EstadoUnidadInventario.ENTREGADA
    db_session.commit()

    r = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert convenio_a.id not in {c["id"] for c in r.json()}


def test_admin_sigue_viendo_convenio_sin_inventario(client, admin_a, convenio_a):
    """Unlike the affiliate catalog, the admin listing must never filter
    by stock — the admin needs to see (and restock) exactly the convenios
    sitting at 0."""
    from tests.conftest import admin_token

    token = admin_token(admin_a)
    r = client.get("/api/convenios", headers=auth_headers(token))
    assert r.status_code == 200
    assert convenio_a.id in {c["id"] for c in r.json()["items"]}


def test_catalogo_nunca_mezcla_convenios_de_otra_cooperativa(client, db_session, afiliado_a, convenio_a, cooperativa_b):
    """Security/isolation control, not just a business rule: a convenio
    from ANOTHER cooperativa must NEVER appear in an afiliado's catalog —
    not even if it's active, in-vigencia, and fully stocked. Exactly the
    same class of guarantee as every other cooperativa_id boundary in
    this app (never trust/derive scope from anything but the JWT)."""
    from app.models.convenio import Convenio

    convenio_b = Convenio(
        cooperativa_id=cooperativa_b.id,
        nombre="Convenio de Otra Cooperativa",
        precio_publico=50000,
        precio_beet=40000,
        fecha_inicio="2024-01-01",
        estado=True,
    )
    db_session.add(convenio_b)
    db_session.commit()
    crear_unidades(db_session, convenio_b, cantidad=5)  # active, in-vigencia, plenty of stock
    crear_unidades(db_session, convenio_a, cantidad=5)  # afiliado_a's own convenio, same conditions

    token = afiliado_token(afiliado_a)  # afiliado_a belongs to cooperativa_a
    r = client.get("/api/convenios/catalogo", headers=auth_headers(token))
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}

    assert convenio_a.id in ids  # own cooperativa's convenio: visible
    assert convenio_b.id not in ids  # other cooperativa's convenio: NEVER visible, no matter how "eligible" it looks
