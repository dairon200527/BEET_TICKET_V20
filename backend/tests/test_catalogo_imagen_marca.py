"""GET /api/convenios/catalogo now also exposes `imagen_marca_url` — the
branding image of a convenio's active plantilla (same image already used
inside its ticket PDF, see app/services/pdf_service.plantilla_activa),
so the portal catalog card can show real branding instead of the generic
diagonal-stripes placeholder. `None` when the convenio has no active
plantilla (or none with a logo) yet — never an error, never a broken
field. See app/routers/convenios.py (catalogo, imagen_marca)."""
from __future__ import annotations

import base64
import json

from app.models.convenio import Convenio
from app.models.plantilla import Plantilla
from app.services import storage_service
from tests.conftest import afiliado_token, auth_headers, crear_unidades


def _png_1x1() -> bytes:
    return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _crear_plantilla_con_logo(db_session, convenio_id):
    """Directly builds a LEGACY ("template_key") plantilla row + its
    storage_service-backed config — the same shape the retired
    `POST /api/plantillas` used to persist — since that creation
    endpoint no longer exists (see routers/plantillas.py's module
    docstring: only the fixed 4-design catalog can be selected now).
    This is exactly what `pdf_service.logo_storage_path_de_plantilla`
    still reads for any convenio without a catalog selection."""
    logo_key = storage_service.generate_object_key("plantillas-logos", 1, "convenio", convenio_id, ".png")
    storage_service.upload_bytes(logo_key, _png_1x1(), "image/png")
    config = {"template_key": "diseno_base_1", "logo_storage_path": logo_key, "titulo_ticket": "Ticket"}
    object_key = storage_service.generate_object_key("plantillas", 1, "convenio", convenio_id, ".json")
    storage_service.upload_bytes(object_key, json.dumps(config).encode("utf-8"), "application/json")
    plantilla = Plantilla(convenio_id=convenio_id, nombre="Plantilla con logo", version=1, storage_path=object_key, estado=True)
    db_session.add(plantilla)
    db_session.commit()
    return plantilla


def test_catalogo_expone_imagen_marca_cuando_hay_plantilla_con_logo(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=2)
    _crear_plantilla_con_logo(db_session, convenio_a.id)

    r = client.get("/api/convenios/catalogo", headers=auth_headers(afiliado_token(afiliado_a)))
    assert r.status_code == 200
    encontrado = next(c for c in r.json() if c["id"] == convenio_a.id)
    assert encontrado["imagen_marca_url"] == f"/api/convenios/{convenio_a.id}/imagen-marca"


def test_catalogo_expone_imagen_marca_null_sin_plantilla(client, db_session, afiliado_a, convenio_a):
    """A convenio can be perfectly sellable (active, in-vigencia, stocked)
    without ever having had a plantilla configured — `imagen_marca_url`
    must come back `None`, never an error, so the card falls back to the
    placeholder."""
    crear_unidades(db_session, convenio_a, cantidad=2)

    r = client.get("/api/convenios/catalogo", headers=auth_headers(afiliado_token(afiliado_a)))
    assert r.status_code == 200
    encontrado = next(c for c in r.json() if c["id"] == convenio_a.id)
    assert encontrado["imagen_marca_url"] is None


def test_imagen_marca_devuelve_los_bytes_reales_del_logo(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    _crear_plantilla_con_logo(db_session, convenio_a.id)

    r = client.get(f"/api/convenios/{convenio_a.id}/imagen-marca", headers=auth_headers(afiliado_token(afiliado_a)))
    assert r.status_code == 200
    assert r.content == _png_1x1()
    assert r.headers["content-type"] == "image/png"


def test_imagen_marca_404_sin_plantilla(client, afiliado_a, convenio_a):
    r = client.get(f"/api/convenios/{convenio_a.id}/imagen-marca", headers=auth_headers(afiliado_token(afiliado_a)))
    assert r.status_code == 404


def test_imagen_marca_404_para_convenio_de_otra_cooperativa(client, db_session, admin_a, afiliado_a, convenio_a, cooperativa_b):
    """Same isolation guarantee as /catalogo itself: convenio_id is never
    trusted on its own — a convenio from another cooperativa is a 404,
    indistinguishable from one that doesn't exist at all."""
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
    db_session.refresh(convenio_b)

    r = client.get(f"/api/convenios/{convenio_b.id}/imagen-marca", headers=auth_headers(afiliado_token(afiliado_a)))
    assert r.status_code == 404
