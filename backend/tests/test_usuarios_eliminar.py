"""
DELETE /api/admin/usuarios/{id} — a REAL, permanent removal from
usuarios_admin (distinct from the existing PATCH .../{id} {"estado":
false} soft-disable, which stays unchanged and is still how you revoke
access without losing the record). See app/routers/admin.py.
"""
from __future__ import annotations

from app.core.security import hash_password
from app.models.enums import RolAdmin
from app.models.log_auditoria import LogAuditoria
from app.models.usuario_admin import UsuarioAdmin
from tests.conftest import admin_token, auth_headers


def _crear_usuario(db_session, cooperativa, rol=RolAdmin.ADMIN, correo="borrar.me@beetticket.test"):
    usuario = UsuarioAdmin(
        cooperativa_id=cooperativa.id if rol != RolAdmin.SUPER_ADMIN else None,
        nombre="Para Borrar", correo=correo,
        password_hash=hash_password("Password123!"), rol=rol,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def test_super_admin_elimina_usuario_realmente_de_postgres(client, superadmin_a, cooperativa_a, db_session):
    objetivo = _crear_usuario(db_session, cooperativa_a)
    objetivo_id = objetivo.id

    resp = client.delete(f"/api/admin/usuarios/{objetivo_id}", headers=auth_headers(admin_token(superadmin_a)))
    assert resp.status_code == 204
    assert resp.content == b""

    db_session.expire_all()
    assert db_session.get(UsuarioAdmin, objetivo_id) is None  # really gone, not just estado=false


def test_admin_no_puede_eliminar_usuarios(client, admin_a, cooperativa_a, db_session):
    objetivo = _crear_usuario(db_session, cooperativa_a, correo="otro.borrar@beetticket.test")
    resp = client.delete(f"/api/admin/usuarios/{objetivo.id}", headers=auth_headers(admin_token(admin_a)))
    assert resp.status_code == 403
    db_session.expire_all()
    assert db_session.get(UsuarioAdmin, objetivo.id) is not None  # untouched


def test_lector_no_puede_eliminar_usuarios(client, lector_a, cooperativa_a, db_session):
    objetivo = _crear_usuario(db_session, cooperativa_a, correo="tercero.borrar@beetticket.test")
    resp = client.delete(f"/api/admin/usuarios/{objetivo.id}", headers=auth_headers(admin_token(lector_a)))
    assert resp.status_code == 403


def test_eliminar_usuario_inexistente_da_404(client, superadmin_a):
    resp = client.delete("/api/admin/usuarios/999999", headers=auth_headers(admin_token(superadmin_a)))
    assert resp.status_code == 404


def test_super_admin_no_puede_eliminarse_a_si_mismo(client, superadmin_a):
    resp = client.delete(f"/api/admin/usuarios/{superadmin_a.id}", headers=auth_headers(admin_token(superadmin_a)))
    assert resp.status_code == 400


def test_eliminar_usuario_preserva_sus_logs_de_auditoria_con_referencia_nula(client, superadmin_a, cooperativa_a, db_session):
    """The one FK pointing at usuarios_admin (logs_auditoria.usuario_admin_id,
    nullable by design) must survive the DELETE — the audit trail entry
    stays, only detached from the now-gone user row."""
    objetivo = _crear_usuario(db_session, cooperativa_a, correo="con.historial@beetticket.test")
    objetivo_id = objetivo.id

    log_previo = LogAuditoria(usuario_admin_id=objetivo_id, accion="usuario_admin_actualizado", tabla_afectada="usuarios_admin", registro_id=objetivo_id, detalles={})
    db_session.add(log_previo)
    db_session.commit()
    log_id = log_previo.id

    resp = client.delete(f"/api/admin/usuarios/{objetivo_id}", headers=auth_headers(admin_token(superadmin_a)))
    assert resp.status_code == 204

    db_session.expire_all()
    log_recargado = db_session.get(LogAuditoria, log_id)
    assert log_recargado is not None  # the historical entry was NOT deleted
    assert log_recargado.usuario_admin_id is None  # only detached
