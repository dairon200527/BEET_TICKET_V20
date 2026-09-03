"""Scenarios: affiliate self-registro (claiming a roster row an admin
already loaded), login, and /me — including the deliberate design
decision that `documento` alone does not identify a row (only
`(cooperativa_id, documento)` is unique), so /registro also requires
`correo` to match the same row (see ../app/routers/auth_afiliado.py)."""
from __future__ import annotations

from tests.conftest import AFILIADO_A_PASSWORD, auth_headers, afiliado_token


def test_registro_succeeds_with_matching_documento_and_correo(client, afiliado_sin_cuenta):
    r = client.post(
        "/api/auth/afiliado/registro",
        json={
            "documento": afiliado_sin_cuenta.documento,
            "correo": afiliado_sin_cuenta.correo,
            "password": "NuevaPass123!",
            "confirmar_password": "NuevaPass123!",
        },
    )
    assert r.status_code == 201

    # And can now log in with the password just set.
    r_login = client.post(
        "/api/auth/afiliado/login",
        json={"correo": afiliado_sin_cuenta.correo, "password": "NuevaPass123!"},
    )
    assert r_login.status_code == 200
    assert "access_token" in r_login.json()


def test_registro_fails_with_wrong_correo(client, afiliado_sin_cuenta):
    r = client.post(
        "/api/auth/afiliado/registro",
        json={
            "documento": afiliado_sin_cuenta.documento,
            "correo": "correo-equivocado@beetticket.test",
            "password": "NuevaPass123!",
            "confirmar_password": "NuevaPass123!",
        },
    )
    assert r.status_code == 400


def test_registro_fails_with_wrong_documento(client, afiliado_sin_cuenta):
    r = client.post(
        "/api/auth/afiliado/registro",
        json={
            "documento": "0000000000",
            "correo": afiliado_sin_cuenta.correo,
            "password": "NuevaPass123!",
            "confirmar_password": "NuevaPass123!",
        },
    )
    assert r.status_code == 400


def test_registro_fails_when_already_claimed(client, afiliado_a):
    # afiliado_a already has a password_hash set by the fixture.
    r = client.post(
        "/api/auth/afiliado/registro",
        json={
            "documento": afiliado_a.documento,
            "correo": afiliado_a.correo,
            "password": "OtraPass123!",
            "confirmar_password": "OtraPass123!",
        },
    )
    assert r.status_code == 400


def test_registro_fails_when_passwords_dont_match(client, afiliado_sin_cuenta):
    r = client.post(
        "/api/auth/afiliado/registro",
        json={
            "documento": afiliado_sin_cuenta.documento,
            "correo": afiliado_sin_cuenta.correo,
            "password": "NuevaPass123!",
            "confirmar_password": "Distinta123!",
        },
    )
    assert r.status_code == 422


def test_login_success(client, afiliado_a):
    r = client.post("/api/auth/afiliado/login", json={"correo": afiliado_a.correo, "password": AFILIADO_A_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["afiliado"]["documento"] == afiliado_a.documento
    assert "password_hash" not in body["afiliado"]


def test_login_wrong_password_fails(client, afiliado_a):
    r = client.post("/api/auth/afiliado/login", json={"correo": afiliado_a.correo, "password": "wrong"})
    assert r.status_code == 401


def test_login_inactive_affiliate_fails(client, db_session, afiliado_a):
    afiliado_a.estado = False
    db_session.commit()
    r = client.post("/api/auth/afiliado/login", json={"correo": afiliado_a.correo, "password": AFILIADO_A_PASSWORD})
    assert r.status_code == 401


def test_me_includes_cooperativa_nombre(client, afiliado_a, cooperativa_a):
    token = afiliado_token(afiliado_a)
    r = client.get("/api/auth/afiliado/me", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["cooperativa_nombre"] == cooperativa_a.nombre
    assert "password_hash" not in body


def test_self_update_only_touches_correo_and_telefono(client, afiliado_a):
    token = afiliado_token(afiliado_a)
    r = client.patch(
        "/api/afiliados/me",
        json={"correo": "actualizado@beetticket.test", "telefono": "3001234567", "documento": "hacked"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["correo"] == "actualizado@beetticket.test"
    assert body["telefono"] == "3001234567"
    assert body["documento"] == afiliado_a.documento  # unaffected by the extra field
