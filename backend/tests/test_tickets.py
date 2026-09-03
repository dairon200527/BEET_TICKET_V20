"""Scenarios: /api/tickets/me listing and PDF download, including that a
ticket belonging to another affiliate is hidden as 404, never 403 (see
../app/routers/tickets.py)."""
from __future__ import annotations

from tests.conftest import afiliado_token, auth_headers, crear_unidades


def _comprar(client, token, convenio_id, cantidad=1):
    r = client.post(
        "/api/transacciones/comprar",
        json={"convenio_id": convenio_id, "cantidad": cantidad, "metodo_pago": "TARJETA", "numero_tarjeta": "4111111111110000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    return r.json()


def test_mis_tickets_lists_purchased_units(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=2)
    token = afiliado_token(afiliado_a)
    _comprar(client, token, convenio_a.id, cantidad=2)

    r = client.get("/api/tickets/me", headers=auth_headers(token))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_descargar_mi_ticket_returns_a_real_pdf(client, db_session, afiliado_a, convenio_a):
    crear_unidades(db_session, convenio_a, cantidad=1)
    token = afiliado_token(afiliado_a)
    _comprar(client, token, convenio_a.id, cantidad=1)

    ticket_id = client.get("/api/tickets/me", headers=auth_headers(token)).json()[0]["id"]
    r = client.get(f"/api/tickets/me/{ticket_id}/descarga", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_cannot_download_another_affiliates_ticket(client, db_session, afiliado_a, convenio_a, cooperativa_b):
    from app.models.afiliado import Afiliado

    crear_unidades(db_session, convenio_a, cantidad=1)
    token_a = afiliado_token(afiliado_a)
    ticket = _comprar(client, token_a, convenio_a.id, cantidad=1)
    ticket_id = ticket["codigos"] and client.get("/api/tickets/me", headers=auth_headers(token_a)).json()[0]["id"]

    otro_afiliado = Afiliado(
        cooperativa_id=cooperativa_b.id, documento="999", nombres="Otro", apellidos="Afiliado", correo="otro@beetticket.test"
    )
    db_session.add(otro_afiliado)
    db_session.commit()
    token_otro = afiliado_token(otro_afiliado)

    r = client.get(f"/api/tickets/me/{ticket_id}/descarga", headers=auth_headers(token_otro))
    assert r.status_code == 404
