"""The 4 fixed, code-owned ticket designs (app/services/plantillas_catalogo.py)
— listed and previewed read-only via `GET /api/plantillas/catalogo` and
`GET /api/plantillas/catalogo/{clave}/preview`, pure code (no database
row ever backs one of these 4). A convenio selects one via
`PATCH /api/convenios/{id}` (`{"plantilla_catalogo_clave": <clave>}`) —
a plain string column, never a foreign key into `plantillas` (see
Convenio's model docstring for why)."""
from __future__ import annotations

import io

from pypdf import PdfReader

from app.services import plantillas_catalogo
from tests.conftest import admin_token, afiliado_token, auth_headers, crear_unidades

CLAVES_ESPERADAS = {"cine_colombia", "mundo_aventura", "wellness_spa", "salitre_magico"}


def test_get_catalogo_lista_las_4_plantillas(client, lector_a):
    resp = client.get("/api/plantillas/catalogo", headers=auth_headers(admin_token(lector_a)))
    assert resp.status_code == 200, resp.text
    claves = {p["clave"] for p in resp.json()}
    assert claves == CLAVES_ESPERADAS


def test_catalogo_no_toca_la_base_de_datos(client, admin_a, db_session):
    """The catalog listing must never insert into `plantillas` — these 4
    designs are pure code, never a real per-convenio plantilla row."""
    from app.models.plantilla import Plantilla

    antes = db_session.query(Plantilla).count()
    client.get("/api/plantillas/catalogo", headers=auth_headers(admin_token(admin_a)))
    despues = db_session.query(Plantilla).count()
    assert despues == antes


def test_preview_de_catalogo_devuelve_un_pdf_real(client, admin_a):
    resp = client.get("/api/plantillas/catalogo/cine_colombia/preview", headers=auth_headers(admin_token(admin_a)))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1


def test_preview_de_clave_inexistente_es_404(client, admin_a):
    resp = client.get("/api/plantillas/catalogo/no_existe/preview", headers=auth_headers(admin_token(admin_a)))
    assert resp.status_code == 404


def test_generar_pdf_de_las_4_claves():
    """Every catalog design actually renders — one real PDF per brand."""
    from app.services import template_engine

    for clave in CLAVES_ESPERADAS:
        contexto = template_engine.contexto_preview(
            convenio_nombre=plantillas_catalogo.nombre_de(clave), convenio_descripcion=None, n_unidades=4,
        )
        pdf_bytes = plantillas_catalogo.generar_pdf(clave, contexto)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) == 1


# --- Selection: PATCH /api/convenios/{id} -----------------------------

def test_seleccionar_plantilla_valida_en_convenio(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    resp = client.patch(
        f"/api/convenios/{convenio_a.id}", headers=auth_headers(token),
        json={"plantilla_catalogo_clave": "cine_colombia"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plantilla_catalogo_clave"] == "cine_colombia"


def test_seleccionar_clave_inexistente_es_400(client, admin_a, convenio_a):
    resp = client.patch(
        f"/api/convenios/{convenio_a.id}", headers=auth_headers(admin_token(admin_a)),
        json={"plantilla_catalogo_clave": "no_existe"},
    )
    assert resp.status_code == 400


def test_lector_no_puede_seleccionar_plantilla(client, lector_a, convenio_a):
    resp = client.patch(
        f"/api/convenios/{convenio_a.id}", headers=auth_headers(admin_token(lector_a)),
        json={"plantilla_catalogo_clave": "cine_colombia"},
    )
    assert resp.status_code == 403


def test_limpiar_seleccion_con_null(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "cine_colombia"})

    resp = client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": None})
    assert resp.status_code == 200
    assert resp.json()["plantilla_catalogo_clave"] is None


def test_dos_convenios_pueden_compartir_la_misma_plantilla(client, admin_a, convenio_a, db_session):
    from app.models.convenio import Convenio

    otro = Convenio(
        cooperativa_id=convenio_a.cooperativa_id, nombre="Convenio B",
        precio_publico=20000, precio_beet=15000, fecha_inicio="2024-01-01",
    )
    db_session.add(otro)
    db_session.commit()

    token = admin_token(admin_a)
    r1 = client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "wellness_spa"})
    r2 = client.patch(f"/api/convenios/{otro.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "wellness_spa"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["plantilla_catalogo_clave"] == r2.json()["plantilla_catalogo_clave"] == "wellness_spa"


# --- pdf_service actually uses the selection ---------------------------

def test_ticket_usa_la_plantilla_del_catalogo_seleccionada(db_session, convenio_a):
    from app.services import pdf_service

    convenio_a.plantilla_catalogo_clave = "cine_colombia"
    db_session.commit()

    unidades = crear_unidades(db_session, convenio_a, cantidad=1)
    db_session.expire_all()

    pdf_bytes = pdf_service.generar_ticket(
        convenio_a, unidades[0],
        variables={"afiliado_nombre": "Ana Gómez", "afiliado_documento": "1", "transaccion_id": 1, "fecha_compra": "2026-01-01"},
    )
    texto = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "CINECO PASS" in texto
    assert "TICKET PROVISIONAL" not in texto
    assert unidades[0].codigo in texto


def test_convenio_sin_seleccion_ni_plantilla_legacy_usa_el_generico(db_session, convenio_a):
    from app.services import pdf_service

    assert convenio_a.plantilla_catalogo_clave is None
    unidades = crear_unidades(db_session, convenio_a, cantidad=1)
    db_session.expire_all()

    pdf_bytes = pdf_service.generar_ticket(
        convenio_a, unidades[0],
        variables={"afiliado_nombre": "Ana Gómez", "afiliado_documento": "1", "transaccion_id": 1, "fecha_compra": "2026-01-01"},
    )
    texto = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "TICKET PROVISIONAL" in texto
    assert unidades[0].codigo in texto


# --- imagen-marca resolves the catalog design's real logo --------------

def test_imagen_marca_usa_el_logo_real_de_la_plantilla_seleccionada(client, admin_a, afiliado_a, convenio_a, db_session):
    convenio_a.plantilla_catalogo_clave = "cine_colombia"
    convenio_a.estado = True
    db_session.commit()

    resp = client.get(f"/api/convenios/{convenio_a.id}/imagen-marca", headers=auth_headers(afiliado_token(afiliado_a)))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == plantillas_catalogo.logo_bytes("cine_colombia")
