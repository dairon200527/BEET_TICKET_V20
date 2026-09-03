"""
Regression test for the real root cause behind "no me deja activar mi
cuenta" (400/500 on POST /api/auth/afiliado/registro) when a fresh
`beet_ticket.backup` restore is migrated by hand.

The normal pytest suite NEVER exercises Alembic — `conftest.py` builds the
schema directly via `Base.metadata.create_all()` — so a real bug in the
migration chain itself could pass 100% of the rest of the suite and still
break for every real user following the documented setup steps. This test
closes that gap by actually running `alembic upgrade head` (the real
Alembic API, not just importing the revision module) against a throwaway
database pre-seeded with the exact pre-Alembic shape of `afiliados` /
`usuarios_admin` that `beet_ticket.backup` produces: no
`afiliados.password_hash` column, and `usuarios_admin.cooperativa_id` as
NOT NULL. See alembic/versions/26b8314392ca_initial_schema_11_core_tables.py
for the fix (an idempotent `upgrade()` that no-ops its own CREATE TABLE
calls when `cooperativas` already exists, so `alembic upgrade head` is
correct unconditionally — no more `stamp head` vs `upgrade head` decision).
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


@contextmanager
def _database_url_override(url: str):
    """alembic/env.py always calls `get_settings().database_url` itself
    (so migrations and the app can never drift onto different databases
    by accident) — it ignores any `sqlalchemy.url` set on the `Config`
    object beforehand. To point a real `alembic upgrade` at a throwaway
    database from inside a test, the underlying env var has to change
    instead, with the `lru_cache`d settings singleton cleared before and
    after so the override is invisible to every other test."""
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()

# Minimal raw DDL matching the SHAPE `beet_ticket.backup` actually
# produces for these two tables — no password_hash, cooperativa_id NOT
# NULL — everything else about the 11-table schema is irrelevant to this
# specific bug, so it is intentionally not reproduced here.
RAW_BACKUP_SCHEMA_DDL = """
CREATE TABLE cooperativas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    nit VARCHAR(30) NOT NULL UNIQUE,
    estado BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE usuarios_admin (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cooperativa_id BIGINT NOT NULL REFERENCES cooperativas(id),
    nombre VARCHAR(200) NOT NULL,
    correo VARCHAR(255) NOT NULL UNIQUE,
    rol VARCHAR(30) NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE afiliados (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cooperativa_id BIGINT NOT NULL REFERENCES cooperativas(id),
    documento VARCHAR(30) NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    correo VARCHAR(255) NOT NULL,
    telefono VARCHAR(30),
    estado BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE convenios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cooperativa_id BIGINT NOT NULL REFERENCES cooperativas(id),
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    precio_publico NUMERIC(12,2) NOT NULL,
    precio_beet NUMERIC(12,2) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE,
    estado BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE plantillas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    convenio_id BIGINT NOT NULL REFERENCES convenios(id),
    nombre VARCHAR(200) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    storage_path TEXT NOT NULL,
    estado BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (convenio_id, version)
);
"""


def _admin_dsn_and_throwaway_name() -> tuple[str, str]:
    url = get_settings().database_url  # postgresql+psycopg2://user:pass@host:port/dbname
    m = re.match(r"postgresql\+psycopg2://([^:]+):([^@]*)@([^:/]+):?(\d*)/(\w+)", url)
    assert m, f"Unexpected DATABASE_URL shape for this test: {url}"
    user, password, host, port, _dbname = m.groups()
    port = port or "5432"
    admin_dsn = f"dbname=postgres user={user} password={password} host={host} port={port}"
    throwaway = "beet_ticket_alembic_migration_check"
    return admin_dsn, throwaway


def test_alembic_upgrade_head_es_idempotente_sobre_esquema_del_backup_real():
    """The exact reproduction that found the bug: restore-shaped schema
    (no password_hash, cooperativa_id NOT NULL) + `alembic upgrade head`
    must succeed AND actually add both missing pieces — not silently
    no-op the way the old documented `alembic stamp head` did."""
    admin_dsn, throwaway = _admin_dsn_and_throwaway_name()

    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{throwaway}"')
            cur.execute(f'CREATE DATABASE "{throwaway}"')

        throwaway_url = re.sub(r"/\w+$", f"/{throwaway}", get_settings().database_url)
        engine = create_engine(throwaway_url)
        with engine.begin() as conn:
            conn.execute(text(RAW_BACKUP_SCHEMA_DDL))
        engine.dispose()

        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        with _database_url_override(throwaway_url):
            command.upgrade(alembic_cfg, "head")  # must not raise DuplicateTable

        check_engine = create_engine(throwaway_url)
        with check_engine.connect() as conn:
            afiliados_cols = {
                row[0]
                for row in conn.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'afiliados'")
                )
            }
            assert "password_hash" in afiliados_cols

            nullable = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'usuarios_admin' AND column_name = 'cooperativa_id'"
                )
            ).scalar_one()
            assert nullable == "YES"
        check_engine.dispose()
    finally:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (throwaway,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{throwaway}"')
        admin_conn.close()


def test_alembic_upgrade_head_crea_las_11_tablas_en_bd_vacia():
    """The other half of the same guarantee: a genuinely empty database
    must still get the full schema from this same single command — the
    idempotency fix must not accidentally turn this into a no-op too."""
    admin_dsn, throwaway = _admin_dsn_and_throwaway_name()
    throwaway = throwaway + "_empty"

    admin_conn = psycopg2.connect(admin_dsn)
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{throwaway}"')
            cur.execute(f'CREATE DATABASE "{throwaway}"')

        throwaway_url = re.sub(r"/\w+$", f"/{throwaway}", get_settings().database_url)

        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        with _database_url_override(throwaway_url):
            command.upgrade(alembic_cfg, "head")

        check_engine = create_engine(throwaway_url)
        with check_engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
            }
        check_engine.dispose()
        expected = {
            "cooperativas", "usuarios_admin", "afiliados", "convenios", "plantillas",
            "unidades_inventario", "cupos_credito", "transacciones", "transaccion_unidades",
            "documentos_asuncion_deuda", "logs_auditoria", "alembic_version",
        }
        assert expected.issubset(tables)
    finally:
        with admin_conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (throwaway,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{throwaway}"')
        admin_conn.close()
