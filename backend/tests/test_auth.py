"""Scenarios: admin login success/failure, unauthenticated access, disjoint
admin/affiliate token spaces.

See test_auth_afiliado.py for affiliate registro/login/me."""
from __future__ import annotations

from tests.conftest import admin_token, afiliado_token, auth_headers


def test_admin_login_success(client, superadmin_a):
    r = client.post("/api/auth/admin/login", json={"correo": superadmin_a.correo, "password": "Password123!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["usuario"]["correo"] == superadmin_a.correo
    assert "password_hash" not in body["usuario"]


def test_admin_login_wrong_password_fails(client, superadmin_a):
    r = client.post("/api/auth/admin/login", json={"correo": superadmin_a.correo, "password": "wrong-password"})
    assert r.status_code == 401


def test_admin_login_unknown_email_fails_identically(client, superadmin_a):
    r_wrong_pw = client.post("/api/auth/admin/login", json={"correo": superadmin_a.correo, "password": "wrong"})
    r_unknown = client.post("/api/auth/admin/login", json={"correo": "nope@beetticket.test", "password": "wrong"})
    assert r_wrong_pw.status_code == r_unknown.status_code == 401
    assert r_wrong_pw.json() == r_unknown.json()


def test_unauthenticated_request_rejected(client):
    r = client.get("/api/afiliados")
    assert r.status_code == 401


def test_admin_me_returns_authenticated_user(client, superadmin_a):
    token = admin_token(superadmin_a)
    r = client.get("/api/auth/admin/me", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["correo"] == superadmin_a.correo


def test_afiliado_token_rejected_on_admin_endpoint(client, afiliado_a):
    token = afiliado_token(afiliado_a)
    r = client.get("/api/auth/admin/me", headers=auth_headers(token))
    assert r.status_code == 401
