"""Scenarios: usuarios_admin.cooperativa_id is nullable (a SUPER_ADMIN
administers every cooperativa, not one in particular) but still required
for ADMIN/LECTOR at the application layer; SUPER_ADMIN can assign a
specific cooperativa to a new user and list/filter usuarios across every
cooperativa (see ../app/routers/admin.py, ../app/schemas/usuario_admin.py)."""
from __future__ import annotations

from app.core.security import hash_password
from app.models.enums import RolAdmin
from app.models.usuario_admin import UsuarioAdmin
from tests.conftest import admin_token, auth_headers


def test_super_admin_can_have_no_cooperativa(db_session, cooperativa_a):
    # This is the schema-level assertion: the column accepts NULL.
    super_admin = UsuarioAdmin(
        cooperativa_id=None, nombre="Global", correo="global.super@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.SUPER_ADMIN,
    )
    db_session.add(super_admin)
    db_session.commit()
    db_session.refresh(super_admin)
    assert super_admin.cooperativa_id is None


def test_crear_admin_requires_cooperativa(client, superadmin_a):
    token = admin_token(superadmin_a)
    r = client.post(
        "/api/admin/usuarios",
        json={"nombre": "Sin Coop", "correo": "sincoop@beetticket.test", "password": "Password123!", "rol": "ADMIN"},
        headers=auth_headers(token),
    )
    assert r.status_code == 422


def test_crear_lector_requires_cooperativa(client, superadmin_a):
    token = admin_token(superadmin_a)
    r = client.post(
        "/api/admin/usuarios",
        json={"nombre": "Sin Coop", "correo": "sincoop2@beetticket.test", "password": "Password123!", "rol": "LECTOR"},
        headers=auth_headers(token),
    )
    assert r.status_code == 422


def test_crear_super_admin_does_not_require_cooperativa(client, superadmin_a):
    token = admin_token(superadmin_a)
    r = client.post(
        "/api/admin/usuarios",
        json={"nombre": "Otro Super", "correo": "otrosuper@beetticket.test", "password": "Password123!", "rol": "SUPER_ADMIN"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    assert r.json()["cooperativa_id"] is None


def test_crear_admin_with_explicit_cooperativa(client, superadmin_a, cooperativa_b):
    token = admin_token(superadmin_a)
    r = client.post(
        "/api/admin/usuarios",
        json={
            "nombre": "Admin Coop B", "correo": "adminb@beetticket.test", "password": "Password123!",
            "rol": "ADMIN", "cooperativa_id": cooperativa_b.id,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["cooperativa_id"] == cooperativa_b.id
    assert body["cooperativa_nombre"] == cooperativa_b.nombre


def test_crear_admin_with_nonexistent_cooperativa_fails(client, superadmin_a):
    token = admin_token(superadmin_a)
    r = client.post(
        "/api/admin/usuarios",
        json={
            "nombre": "X", "correo": "x@beetticket.test", "password": "Password123!",
            "rol": "ADMIN", "cooperativa_id": 999999,
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 400


def test_listar_usuarios_is_cross_cooperativa_by_default(client, superadmin_a, cooperativa_b, db_session):
    token = admin_token(superadmin_a)
    otro = UsuarioAdmin(
        cooperativa_id=cooperativa_b.id, nombre="En Coop B", correo="encoopb@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.ADMIN,
    )
    db_session.add(otro)
    db_session.commit()

    r = client.get("/api/admin/usuarios", headers=auth_headers(token))
    assert r.status_code == 200
    correos = {u["correo"] for u in r.json()}
    assert {superadmin_a.correo, "encoopb@beetticket.test"} <= correos


def test_listar_usuarios_filters_by_cooperativa(client, superadmin_a, cooperativa_b, db_session):
    token = admin_token(superadmin_a)
    otro = UsuarioAdmin(
        cooperativa_id=cooperativa_b.id, nombre="En Coop B", correo="filtrocoopb@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.ADMIN,
    )
    db_session.add(otro)
    db_session.commit()

    r = client.get(f"/api/admin/usuarios?cooperativa_id={cooperativa_b.id}", headers=auth_headers(token))
    assert r.status_code == 200
    correos = {u["correo"] for u in r.json()}
    assert correos == {"filtrocoopb@beetticket.test"}


def test_listar_usuarios_filtra_por_estado(client, superadmin_a, cooperativa_a, db_session):
    inactivo = UsuarioAdmin(
        cooperativa_id=cooperativa_a.id, nombre="Inactivo Test", correo="inactivo.estado@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.LECTOR, estado=False,
    )
    db_session.add(inactivo)
    db_session.commit()

    token = admin_token(superadmin_a)
    r = client.get("/api/admin/usuarios?estado=false", headers=auth_headers(token))
    assert r.status_code == 200
    correos = {u["correo"] for u in r.json()}
    assert correos == {"inactivo.estado@beetticket.test"}

    r = client.get("/api/admin/usuarios?estado=true", headers=auth_headers(token))
    assert "inactivo.estado@beetticket.test" not in {u["correo"] for u in r.json()}


def test_listar_usuarios_busqueda_por_texto_matches_nombre_de_cooperativa(client, superadmin_a, cooperativa_b, db_session):
    """Regression test for the reported bug: searching by the
    COOPERATIVA's name (not the usuario's own nombre/correo) must scope
    results to that cooperativa only — never mix in admins from other
    cooperativas that merely share no text overlap."""
    en_b = UsuarioAdmin(
        cooperativa_id=cooperativa_b.id, nombre="Zoraida Perez", correo="zoraida@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.ADMIN,
    )
    db_session.add(en_b)
    db_session.commit()

    token = admin_token(superadmin_a)
    r = client.get(f"/api/admin/usuarios?q={cooperativa_b.nombre}", headers=auth_headers(token))
    assert r.status_code == 200
    correos = {u["correo"] for u in r.json()}
    assert correos == {"zoraida@beetticket.test"}


def test_listar_usuarios_busqueda_por_texto_matches_nombre_propio(client, superadmin_a, db_session):
    r_token = admin_token(superadmin_a)
    r = client.get(f"/api/admin/usuarios?q={superadmin_a.nombre[:4]}", headers=auth_headers(r_token))
    assert r.status_code == 200
    assert superadmin_a.correo in {u["correo"] for u in r.json()}


def test_actualizar_usuario_clearing_cooperativa_on_non_super_admin_fails(client, superadmin_a, db_session, cooperativa_a):
    admin_b = UsuarioAdmin(
        cooperativa_id=cooperativa_a.id, nombre="Admin", correo="clearcoop@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.ADMIN,
    )
    db_session.add(admin_b)
    db_session.commit()

    token = admin_token(superadmin_a)
    r = client.patch(f"/api/admin/usuarios/{admin_b.id}", json={"cooperativa_id": None}, headers=auth_headers(token))
    assert r.status_code == 422


def test_listar_cooperativas_for_selector(client, superadmin_a, cooperativa_a, cooperativa_b):
    token = admin_token(superadmin_a)
    r = client.get("/api/admin/cooperativas", headers=auth_headers(token))
    assert r.status_code == 200
    nombres = {c["nombre"] for c in r.json()}
    assert {cooperativa_a.nombre, cooperativa_b.nombre} <= nombres
