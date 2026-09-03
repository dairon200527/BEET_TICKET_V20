"""Scenarios: mutating admin actions are recorded in logs_auditoria, and an
"afiliado"-typed token has no route to the audit log at all.

NOTE: unlike an earlier design assumption, `logs_auditoria` has no
`cooperativa_id` column — reading logs back is scoped via
`usuario_admin_id -> usuarios_admin.cooperativa_id` (see
routers/admin.py), which is what `test_admin_log_endpoint_is_scoped_to_own_cooperativa`
below actually exercises."""
from __future__ import annotations

from sqlalchemy import select

from app.models.log_auditoria import LogAuditoria
from tests.conftest import admin_token, afiliado_token, auth_headers


def test_creating_an_affiliate_writes_an_audit_log(client, db_session, admin_a):
    token = admin_token(admin_a)
    r = client.post(
        "/api/afiliados",
        json={"documento": "999999", "nombres": "Nuevo", "apellidos": "Afiliado", "correo": "nuevo@beetticket.test"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    afiliado_id = r.json()["id"]

    log = db_session.execute(
        select(LogAuditoria).where(LogAuditoria.tabla_afectada == "afiliados", LogAuditoria.registro_id == afiliado_id)
    ).scalar_one()
    assert log.usuario_admin_id == admin_a.id
    assert log.accion == "afiliado_creado"


def test_admin_log_endpoint_is_scoped_to_own_cooperativa(client, admin_a, admin_b, db_session):
    token_a = admin_token(admin_a)
    client.post(
        "/api/afiliados",
        json={"documento": "111", "nombres": "N", "apellidos": "N", "correo": "a1@beetticket.test"},
        headers=auth_headers(token_a),
    )

    token_b = admin_token(admin_b)
    r = client.get("/api/admin/logs", headers=auth_headers(token_b))
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_afiliado_token_has_no_route_to_the_audit_log(client, afiliado_a):
    token = afiliado_token(afiliado_a)
    r = client.get("/api/admin/logs", headers=auth_headers(token))
    assert r.status_code == 401


def test_audit_detalles_survives_non_json_native_field_types(client, db_session, admin_a, convenio_a):
    """Regression test: audit_service.record() is fed
    `payload.model_dump(exclude_unset=True)` verbatim by several routers,
    which can contain raw Decimal/date values that Python's default JSON
    encoder rejects — sanitized once in audit_service._json_safe()."""
    token = admin_token(admin_a)

    r = client.patch(
        f"/api/convenios/{convenio_a.id}",
        json={"precio_beet": "7500", "fecha_fin": "2027-06-30"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200

    log = db_session.execute(
        select(LogAuditoria).where(LogAuditoria.accion == "convenio_actualizado", LogAuditoria.registro_id == convenio_a.id)
    ).scalar_one()
    assert log.detalles["precio_beet"] == "7500"
    assert log.detalles["fecha_fin"] == "2027-06-30"
