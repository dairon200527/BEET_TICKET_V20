"""Affiliate-facing debt-assumption documents (`GET /api/documentos/me`,
`GET /api/documentos/me/{id}/descarga`) — the portal's "Mis documentos"
and `DocumentDetail` screens were already built against these paths (see
frontend/src/services/documentosService.js) but the backend previously
had no route mounted for them at all. See app/routers/documentos.py."""
from __future__ import annotations

from app.models.afiliado import Afiliado
from tests.conftest import afiliado_token, auth_headers, crear_unidades

FIRMA_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def _comprar_con_cupo(client, token, convenio_id, *, cuotas=3):
    r = client.post(
        "/api/transacciones/comprar",
        json={
            "convenio_id": convenio_id, "cantidad": 1, "metodo_pago": "CUPO",
            "numero_cuotas": cuotas, "firma_base64": FIRMA_PNG_B64,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_mis_documentos_lista_los_propios(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    _comprar_con_cupo(client, token, convenio_a.id, cuotas=6)

    resp = client.get("/api/documentos/me", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["numero_cuotas"] == 6
    assert item["estado"] == "FIRMADO"
    assert item["fecha_firma"] is not None


def test_mis_documentos_vacio_cuando_nunca_compro_con_cupo(client, afiliado_a):
    token = afiliado_token(afiliado_a)
    resp = client.get("/api/documentos/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_descargar_mi_documento_devuelve_el_pdf_real(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    _comprar_con_cupo(client, token, convenio_a.id)

    documento_id = client.get("/api/documentos/me", headers=auth_headers(token)).json()["items"][0]["id"]
    resp = client.get(f"/api/documentos/me/{documento_id}/descarga", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_no_puede_descargar_el_documento_de_otro_afiliado(client, db_session, afiliado_a, convenio_a, cooperativa_b):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token_a = afiliado_token(afiliado_a)
    _comprar_con_cupo(client, token_a, convenio_a.id)
    documento_id = client.get("/api/documentos/me", headers=auth_headers(token_a)).json()["items"][0]["id"]

    otro_afiliado = Afiliado(
        cooperativa_id=cooperativa_b.id, documento="998", nombres="Otro", apellidos="Afiliado", correo="otro-doc@beetticket.test"
    )
    db_session.add(otro_afiliado)
    db_session.commit()
    token_otro = afiliado_token(otro_afiliado)

    resp = client.get(f"/api/documentos/me/{documento_id}/descarga", headers=auth_headers(token_otro))
    assert resp.status_code == 404


def test_no_puede_listar_documentos_de_otro_afiliado(client, db_session, afiliado_a, convenio_a, cooperativa_b):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token_a = afiliado_token(afiliado_a)
    _comprar_con_cupo(client, token_a, convenio_a.id)

    otro_afiliado = Afiliado(
        cooperativa_id=cooperativa_b.id, documento="997", nombres="Otro", apellidos="Afiliado", correo="otro-doc2@beetticket.test"
    )
    db_session.add(otro_afiliado)
    db_session.commit()
    token_otro = afiliado_token(otro_afiliado)

    resp = client.get("/api/documentos/me", headers=auth_headers(token_otro))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
