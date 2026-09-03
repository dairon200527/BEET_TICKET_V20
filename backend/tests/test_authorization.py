"""Scenarios: LECTOR write-block, cross-cooperativa access, and that every
scoped query actually excludes other tenants."""
from __future__ import annotations

from tests.conftest import admin_token, auth_headers


def _payload():
    return {"nombre": "X", "precio_publico": "1000", "precio_beet": "900", "fecha_inicio": "2024-01-01"}


def test_lector_cannot_create_convenio(client, lector_a):
    token = admin_token(lector_a)
    r = client.post("/api/convenios", json=_payload(), headers=auth_headers(token))
    assert r.status_code == 403


def test_lector_can_read(client, lector_a):
    token = admin_token(lector_a)
    r = client.get("/api/convenios", headers=auth_headers(token))
    assert r.status_code == 200


def test_admin_can_create_convenio(client, admin_a):
    token = admin_token(admin_a)
    r = client.post("/api/convenios", json=_payload(), headers=auth_headers(token))
    assert r.status_code == 201


def test_lector_cannot_manage_admin_users(client, lector_a):
    token = admin_token(lector_a)
    r = client.get("/api/admin/usuarios", headers=auth_headers(token))
    assert r.status_code == 403


def test_cross_cooperativa_convenio_hidden_as_404(client, admin_b, convenio_a):
    token = admin_token(admin_b)
    r = client.get(f"/api/convenios/{convenio_a.id}", headers=auth_headers(token))
    assert r.status_code == 404


def test_listing_is_scoped_to_own_cooperativa(client, admin_b, convenio_a):
    token = admin_token(admin_b)
    r = client.get("/api/convenios", headers=auth_headers(token))
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert convenio_a.id not in ids


def test_cross_cooperativa_afiliado_hidden_as_404(client, admin_b, afiliado_a):
    token = admin_token(admin_b)
    r = client.get(f"/api/afiliados/{afiliado_a.id}", headers=auth_headers(token))
    assert r.status_code == 404
