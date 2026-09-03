"""Creating a real per-convenio plantilla by pasting raw HTML/Jinja2
source directly — no visual editor, no manual positioning (see
services/template_engine.py's `validar_y_renderizar`, shared by
`POST /api/plantillas/preview` (never persists) and `POST /api/plantillas`
(persists a new versioned row in the real `plantillas` table)."""
from __future__ import annotations

import io

from pypdf import PdfReader

from tests.conftest import admin_token, auth_headers, crear_unidades

HTML_VALIDO = """
<html><body>
<h1>{{ convenio.nombre }}</h1>
{% for item in items %}<p>{{ item.codigo }}</p>{% endfor %}
<p>{{ afiliado.nombres }} {{ afiliado.apellidos }}</p>
<p>Transaccion: {{ transaccion_id }}</p>
<p>Emision: {{ fecha_emision }} Vence: {{ fecha_vencimiento }}</p>
</body></html>
"""


def _html_con_marca(texto):
    """A valid HTML_VALIDO variant carrying a literal, hardcoded marker —
    used instead of a content-field variable (removed from the creation
    endpoints) to tell one rendered PDF apart from another in assertions."""
    return HTML_VALIDO.replace("</body></html>", f"<p>{texto}</p></body></html>")

HTML_SIN_VARIABLES_REQUERIDAS = "<html><body><h1>Hola</h1></body></html>"

HTML_SINTAXIS_INVALIDA = "<html><body>{{ convenio.nombre </body></html>"


def _form(convenio_id, html, **extra):
    data = {"convenio_id": str(convenio_id), "html": html}
    data.update(extra)
    return data


def test_preview_html_valido_devuelve_pdf_sin_guardar(client, admin_a, convenio_a, db_session):
    from app.models.plantilla import Plantilla

    antes = db_session.query(Plantilla).count()
    resp = client.post(
        "/api/plantillas/preview", headers=auth_headers(admin_token(admin_a)),
        data=_form(convenio_a.id, HTML_VALIDO),
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1
    despues = db_session.query(Plantilla).count()
    assert despues == antes


def test_preview_sin_variables_requeridas_es_400(client, admin_a, convenio_a):
    resp = client.post(
        "/api/plantillas/preview", headers=auth_headers(admin_token(admin_a)),
        data=_form(convenio_a.id, HTML_SIN_VARIABLES_REQUERIDAS),
    )
    assert resp.status_code == 400
    assert "variable" in resp.json()["detail"].lower()


def test_preview_sintaxis_invalida_es_400(client, admin_a, convenio_a):
    resp = client.post(
        "/api/plantillas/preview", headers=auth_headers(admin_token(admin_a)),
        data=_form(convenio_a.id, HTML_SINTAXIS_INVALIDA),
    )
    assert resp.status_code == 400


def test_lector_no_puede_previsualizar_ni_crear(client, lector_a, convenio_a):
    token = admin_token(lector_a)
    r1 = client.post("/api/plantillas/preview", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    assert r1.status_code == 403
    r2 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    assert r2.status_code == 403


def test_crear_plantilla_html_persiste_version_1(client, admin_a, convenio_a, db_session):
    resp = client.post(
        "/api/plantillas", headers=auth_headers(admin_token(admin_a)),
        data=_form(convenio_a.id, HTML_VALIDO, nombre="Diseño personalizado"),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["convenio_id"] == convenio_a.id
    assert body["version"] == 1
    assert body["estado"] is True
    assert body["nombre"] == "Diseño personalizado"


def test_crear_dos_veces_incrementa_version(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    r1 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    r2 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


def test_crear_con_html_invalido_no_persiste_nada(client, admin_a, convenio_a, db_session):
    from app.models.plantilla import Plantilla

    antes = db_session.query(Plantilla).count()
    resp = client.post(
        "/api/plantillas", headers=auth_headers(admin_token(admin_a)),
        data=_form(convenio_a.id, HTML_SIN_VARIABLES_REQUERIDAS),
    )
    assert resp.status_code == 400
    despues = db_session.query(Plantilla).count()
    assert despues == antes


def test_ticket_real_usa_la_plantilla_html_creada(client, admin_a, convenio_a, db_session):
    from app.services import pdf_service

    token = admin_token(admin_a)
    resp = client.post(
        "/api/plantillas", headers=auth_headers(token),
        data=_form(convenio_a.id, _html_con_marca("BEET Personalizado")),
    )
    assert resp.status_code == 201, resp.text

    unidades = crear_unidades(db_session, convenio_a, cantidad=1)
    db_session.expire_all()
    from app.models.convenio import Convenio

    convenio_fresco = db_session.get(Convenio, convenio_a.id)
    pdf_bytes = pdf_service.generar_ticket(
        convenio_fresco, unidades[0],
        variables={"afiliado_nombre": "Ana Gómez", "afiliado_documento": "1", "transaccion_id": 1, "fecha_compra": "2026-01-01"},
    )
    texto = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "BEET Personalizado" in texto
    assert "TICKET PROVISIONAL" not in texto
    assert unidades[0].codigo in texto


def test_catalogo_seleccionado_gana_sobre_plantilla_html(client, admin_a, convenio_a, db_session):
    """If the convenio ALSO has a catalog design selected, that one still
    wins — the HTML plantilla only takes effect once the catalog
    selection is cleared."""
    from app.services import pdf_service

    token = admin_token(admin_a)
    client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, _html_con_marca("NO DEBE APARECER")))
    client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "cine_colombia"})

    unidades = crear_unidades(db_session, convenio_a, cantidad=1)
    db_session.expire_all()
    from app.models.convenio import Convenio

    convenio_fresco = db_session.get(Convenio, convenio_a.id)
    pdf_bytes = pdf_service.generar_ticket(
        convenio_fresco, unidades[0],
        variables={"afiliado_nombre": "Ana Gómez", "afiliado_documento": "1", "transaccion_id": 1, "fecha_compra": "2026-01-01"},
    )
    texto = PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "CINECO PASS" in texto
    assert "NO DEBE APARECER" not in texto


def test_crear_segunda_plantilla_desactiva_la_primera(client, admin_a, convenio_a, db_session):
    from app.models.plantilla import Plantilla

    token = admin_token(admin_a)
    r1 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    r2 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    assert r1.json()["estado"] is True
    assert r2.json()["estado"] is True

    db_session.expire_all()
    fila1 = db_session.get(Plantilla, r1.json()["id"])
    fila2 = db_session.get(Plantilla, r2.json()["id"])
    assert fila1.estado is False
    assert fila2.estado is True


def test_disponibles_incluye_catalogo_y_personalizadas_con_en_uso_correcto(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    crear = client.post(
        "/api/plantillas", headers=auth_headers(token),
        data=_form(convenio_a.id, HTML_VALIDO, nombre="Mi diseño"),
    )
    assert crear.status_code == 201, crear.text
    plantilla_id = crear.json()["id"]

    resp = client.get(f"/api/plantillas/disponibles?convenio_id={convenio_a.id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()

    catalogo_items = [i for i in items if i["tipo"] == "catalogo"]
    personalizada_items = [i for i in items if i["tipo"] == "personalizada"]
    assert len(catalogo_items) == 4
    assert len(personalizada_items) == 1
    assert all(not i["en_uso"] for i in catalogo_items)
    assert personalizada_items[0]["id"] == plantilla_id
    assert personalizada_items[0]["en_uso"] is True
    assert sum(1 for i in items if i["en_uso"]) == 1

    client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "cine_colombia"})
    resp2 = client.get(f"/api/plantillas/disponibles?convenio_id={convenio_a.id}", headers=auth_headers(token))
    items2 = resp2.json()
    assert sum(1 for i in items2 if i["en_uso"]) == 1
    ganador = next(i for i in items2 if i["en_uso"])
    assert ganador["tipo"] == "catalogo"
    assert ganador["clave"] == "cine_colombia"


def test_disponibles_sin_seleccion_ningun_item_en_uso(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    resp = client.get(f"/api/plantillas/disponibles?convenio_id={convenio_a.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 4
    assert all(not i["en_uso"] for i in items)


def test_patch_activar_plantilla_limpia_clave_de_catalogo_y_desactiva_hermanas(client, admin_a, convenio_a, db_session):
    from app.models.plantilla import Plantilla

    token = admin_token(admin_a)
    r1 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    r2 = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    client.patch(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token), json={"plantilla_catalogo_clave": "cine_colombia"})

    resp = client.patch(f"/api/plantillas/{r1.json()['id']}", headers=auth_headers(token), json={"estado": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] is True

    db_session.expire_all()
    from app.models.convenio import Convenio

    convenio_fresco = db_session.get(Convenio, convenio_a.id)
    assert convenio_fresco.plantilla_catalogo_clave is None
    assert db_session.get(Plantilla, r1.json()["id"]).estado is True
    assert db_session.get(Plantilla, r2.json()["id"]).estado is False


def test_patch_desactivar_plantilla_deja_convenio_sin_plantilla(client, admin_a, convenio_a, db_session):
    token = admin_token(admin_a)
    creada = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    plantilla_id = creada.json()["id"]

    resp = client.patch(f"/api/plantillas/{plantilla_id}", headers=auth_headers(token), json={"estado": False})
    assert resp.status_code == 200
    assert resp.json()["estado"] is False

    detalle = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token))
    assert detalle.json()["plantilla_en_uso"] is None


def test_lector_no_puede_hacer_patch_estado(client, lector_a, admin_a, convenio_a):
    creada = client.post(
        "/api/plantillas", headers=auth_headers(admin_token(admin_a)), data=_form(convenio_a.id, HTML_VALIDO),
    )
    resp = client.patch(
        f"/api/plantillas/{creada.json()['id']}", headers=auth_headers(admin_token(lector_a)), json={"estado": False},
    )
    assert resp.status_code == 403


def test_preview_por_id_devuelve_pdf_para_plantilla_html(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    creada = client.post(
        "/api/plantillas", headers=auth_headers(token),
        data=_form(convenio_a.id, _html_con_marca("Marca de prueba")),
    )
    plantilla_id = creada.json()["id"]

    resp = client.get(f"/api/plantillas/{plantilla_id}/preview", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 1
    texto = reader.pages[0].extract_text()
    assert "Marca de prueba" in texto


def test_convenio_sin_plantilla_reporta_en_uso_none(client, admin_a, convenio_a):
    resp = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(admin_token(admin_a)))
    assert resp.status_code == 200
    assert resp.json()["plantilla_en_uso"] is None


def test_convenio_reporta_nombre_de_la_plantilla_html_activa(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    client.post(
        "/api/plantillas", headers=auth_headers(token),
        data=_form(convenio_a.id, HTML_VALIDO, nombre="Diseño especial"),
    )
    resp = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token))
    assert resp.json()["plantilla_en_uso"] == "Diseño especial"


def test_eliminar_plantilla_la_borra_y_desaparece_de_disponibles(client, admin_a, convenio_a, db_session):
    from app.models.plantilla import Plantilla

    token = admin_token(admin_a)
    creada = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    plantilla_id = creada.json()["id"]

    resp = client.delete(f"/api/plantillas/{plantilla_id}", headers=auth_headers(token))
    assert resp.status_code == 204

    assert db_session.get(Plantilla, plantilla_id) is None

    disponibles = client.get(f"/api/plantillas/disponibles?convenio_id={convenio_a.id}", headers=auth_headers(token)).json()
    assert all(not (i["tipo"] == "personalizada" and i["id"] == plantilla_id) for i in disponibles)


def test_eliminar_plantilla_activa_deja_convenio_sin_plantilla(client, admin_a, convenio_a):
    token = admin_token(admin_a)
    creada = client.post("/api/plantillas", headers=auth_headers(token), data=_form(convenio_a.id, HTML_VALIDO))
    plantilla_id = creada.json()["id"]

    resp = client.delete(f"/api/plantillas/{plantilla_id}", headers=auth_headers(token))
    assert resp.status_code == 204

    detalle = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token))
    assert detalle.json()["plantilla_en_uso"] is None


def test_eliminar_plantilla_inexistente_es_404(client, admin_a):
    token = admin_token(admin_a)
    resp = client.delete("/api/plantillas/999999", headers=auth_headers(token))
    assert resp.status_code == 404


def test_lector_no_puede_eliminar_plantilla(client, lector_a, admin_a, convenio_a):
    creada = client.post(
        "/api/plantillas", headers=auth_headers(admin_token(admin_a)), data=_form(convenio_a.id, HTML_VALIDO),
    )
    resp = client.delete(
        f"/api/plantillas/{creada.json()['id']}", headers=auth_headers(admin_token(lector_a)),
    )
    assert resp.status_code == 403


def test_no_puede_eliminar_plantilla_de_otra_cooperativa(client, admin_a, admin_b, convenio_a):
    creada = client.post(
        "/api/plantillas", headers=auth_headers(admin_token(admin_a)), data=_form(convenio_a.id, HTML_VALIDO),
    )
    resp = client.delete(
        f"/api/plantillas/{creada.json()['id']}", headers=auth_headers(admin_token(admin_b)),
    )
    assert resp.status_code == 404
