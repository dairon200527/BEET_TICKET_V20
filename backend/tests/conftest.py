"""
Test fixtures.

Every test runs against a REAL PostgreSQL database (configured via
DATABASE_URL — see backend/README.md; point it at a disposable/dev
database, never production). This matters: unique/check constraints and
the boolean/string `estado` columns all behave differently — or don't
exist at all — under SQLite.

Each test gets a real, independent session (`TestingSessionLocal()`) and
every table is TRUNCATEd after the test finishes.

"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base, engine
from app.db.session import get_db
from app.main import app as fastapi_app
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.cooperativa import Cooperativa
from app.models.cupo_credito import CupoCredito
from app.models.enums import RolAdmin
from app.models.unidad_inventario import UnidadInventario
from app.models.usuario_admin import UsuarioAdmin

settings = get_settings()
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if settings.is_production:
        raise RuntimeError("Refusing to run the test suite against a database configured as production.")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _no_gateway_latency(monkeypatch):
    """The mock card gateway sleeps 1-2s per call to simulate real
    latency (see services/payment_gateway.py) — zeroed out here so the
    suite doesn't pay that cost on every card-purchase test."""
    from app.services import payment_gateway

    monkeypatch.setattr(payment_gateway, "LATENCY_RANGE_SECONDS", (0.0, 0.0))


def _truncate_all_tables() -> None:
    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        _truncate_all_tables()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


# --- Reusable fixture data --------------------------------------------
@pytest.fixture()
def cooperativa_a(db_session):
    coop = Cooperativa(nombre="Cooperativa A", nit="900000000-1")
    db_session.add(coop)
    db_session.commit()
    db_session.refresh(coop)
    return coop


@pytest.fixture()
def cooperativa_b(db_session):
    coop = Cooperativa(nombre="Cooperativa B", nit="900000000-2")
    db_session.add(coop)
    db_session.commit()
    db_session.refresh(coop)
    return coop


def _crear_admin(db_session, cooperativa, rol, correo):
    admin = UsuarioAdmin(cooperativa_id=cooperativa.id, nombre="Admin", correo=correo, password_hash=hash_password("Password123!"), rol=rol)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture()
def superadmin_a(db_session, cooperativa_a):
    return _crear_admin(db_session, cooperativa_a, RolAdmin.SUPER_ADMIN, "superadmin.a@beetticket.test")


@pytest.fixture()
def lector_a(db_session, cooperativa_a):
    return _crear_admin(db_session, cooperativa_a, RolAdmin.LECTOR, "lector.a@beetticket.test")


@pytest.fixture()
def admin_a(db_session, cooperativa_a):
    """A plain ADMIN of cooperativa_a — for the many tests that just need
    a write-capable admin scoped to ONE cooperativa (as opposed to
    `superadmin_a`, which is SUPER_ADMIN and, since the cooperativa-scope
    selector work, requires an explicit `?cooperativa_id=` on every
    request — see test_cooperativa_scope.py)."""
    return _crear_admin(db_session, cooperativa_a, RolAdmin.ADMIN, "admin.a@beetticket.test")


@pytest.fixture()
def admin_b(db_session, cooperativa_b):
    """A plain ADMIN of cooperativa_b — used only as the "other tenant" in
    cross-cooperativa isolation tests (never for genuine cross-cooperativa
    SUPER_ADMIN management, which stays on `superadmin_a`/`superadmin_sin_cooperativa`)."""
    return _crear_admin(db_session, cooperativa_b, RolAdmin.ADMIN, "admin.b@beetticket.test")


@pytest.fixture()
def superadmin_sin_cooperativa(db_session):
    """A SUPER_ADMIN with NO cooperativa of its own (cooperativa_id=None)
    — the realistic shape for this role now that a SUPER_ADMIN administers
    every cooperativa rather than belonging to one. `superadmin_a` (SUPER_ADMIN
    but WITH a cooperativa_id set) is kept as-is for backward-compatible tests
    that predate the cooperativa-scope selector."""
    admin = UsuarioAdmin(
        cooperativa_id=None, nombre="Super Admin", correo="superadmin.sc@beetticket.test",
        password_hash=hash_password("Password123!"), rol=RolAdmin.SUPER_ADMIN,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def admin_token(admin: UsuarioAdmin) -> str:
    return create_access_token(subject=str(admin.id), extra_claims={"type": "admin"})


def afiliado_token(afiliado: Afiliado) -> str:
    # Crafting a correctly-typed JWT directly (bypassing login) is what's
    # needed for authorization tests that only care about token type/scope,
    # not the login flow itself (see test_auth_afiliado.py for that).
    return create_access_token(subject=str(afiliado.id), extra_claims={"type": "afiliado"})


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


AFILIADO_A_PASSWORD = "AfiliadoPass123!"


@pytest.fixture()
def afiliado_a(db_session, cooperativa_a):
    # `password_hash` is set here so the same fixture serves both the
    # already-registered-affiliate login tests AND the authorization tests
    # that only need a valid "afiliado"-typed token (via afiliado_token()
    # above, which never touches the password).
    afiliado = Afiliado(
        cooperativa_id=cooperativa_a.id,
        documento="1000000001",
        nombres="Afiliado",
        apellidos="A",
        correo="afiliado.a@beetticket.test",
        password_hash=hash_password(AFILIADO_A_PASSWORD),
    )
    db_session.add(afiliado)
    db_session.flush()
    cupo = CupoCredito(afiliado_id=afiliado.id, cupo_total=500000, cupo_disponible=500000)
    db_session.add(cupo)
    db_session.commit()
    db_session.refresh(afiliado)
    return afiliado


@pytest.fixture()
def afiliado_sin_cuenta(db_session, cooperativa_a):
    # A roster row an admin loaded but which has never registered — no
    # password_hash yet — exactly the state /registro expects to act on.
    afiliado = Afiliado(
        cooperativa_id=cooperativa_a.id,
        documento="1000000002",
        nombres="Nuevo",
        apellidos="SinCuenta",
        correo="nuevo.sincuenta@beetticket.test",
    )
    db_session.add(afiliado)
    db_session.commit()
    db_session.refresh(afiliado)
    return afiliado


@pytest.fixture()
def convenio_a(db_session, cooperativa_a):
    convenio = Convenio(
        cooperativa_id=cooperativa_a.id,
        nombre="Convenio A",
        precio_publico=10000,
        precio_beet=8000,
        fecha_inicio="2024-01-01",
    )
    db_session.add(convenio)
    db_session.commit()
    db_session.refresh(convenio)
    return convenio


def crear_unidades(db_session, convenio, cantidad=3):
    unidades = [UnidadInventario(convenio_id=convenio.id, codigo=f"COD-{convenio.id}-{i}") for i in range(cantidad)]
    db_session.add_all(unidades)
    db_session.commit()
    return unidades
