"""
Seeds the three development/test admin accounts required for this
integration pass. Safe to run multiple times (idempotent: an existing
correo has its password/role/estado refreshed rather than being
duplicated or erroring out).

Usage (from backend/, with the virtualenv active and DATABASE_URL set):

    python -m scripts.seed_admin_users

Creates, if none exists yet, a `cooperativas` row to attach the users to
(reuses the first existing cooperativa otherwise — e.g. the "Cooperativa
Demo" row already present in the provided backup). Does NOT touch any
other table and never drops/truncates anything.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base, SessionLocal, engine
from app.models.cooperativa import Cooperativa
from app.models.enums import RolAdmin
from app.models.usuario_admin import UsuarioAdmin

TEST_ADMINS = [
    {"correo": "superadmin@beetticket.test", "password": "SuperAdmin123!", "rol": RolAdmin.SUPER_ADMIN, "nombre": "Super Admin (dev)"},
    {"correo": "admin@beetticket.test", "password": "Admin123!", "rol": RolAdmin.ADMIN, "nombre": "Admin (dev)"},
    {"correo": "lector@beetticket.test", "password": "Lector123!", "rol": RolAdmin.LECTOR, "nombre": "Lector (dev)"},
]


def _ensure_metadata() -> None:
    # No-op if the tables already exist (they do, once the provided
    # backup is restored) — create_all only creates what's missing, it
    # never drops or alters an existing table.
    Base.metadata.create_all(bind=engine, checkfirst=True)


def _get_or_create_cooperativa(db) -> Cooperativa:
    cooperativa = db.execute(select(Cooperativa).order_by(Cooperativa.id).limit(1)).scalar_one_or_none()
    if cooperativa is not None:
        return cooperativa

    cooperativa = Cooperativa(nombre="Cooperativa Demo", nit="900000000-1", estado=True)
    db.add(cooperativa)
    db.flush()
    print(f"Created cooperativa id={cooperativa.id} ({cooperativa.nombre!r}) — none existed yet.")
    return cooperativa


def main() -> None:
    _ensure_metadata()
    db = SessionLocal()
    try:
        cooperativa = _get_or_create_cooperativa(db)

        for spec in TEST_ADMINS:
            usuario = db.execute(
                select(UsuarioAdmin).where(UsuarioAdmin.correo == spec["correo"])
            ).scalar_one_or_none()

            if usuario is None:
                usuario = UsuarioAdmin(
                    cooperativa_id=cooperativa.id,
                    nombre=spec["nombre"],
                    correo=spec["correo"],
                    rol=spec["rol"],
                    estado=True,
                    password_hash=hash_password(spec["password"]),
                )
                db.add(usuario)
                print(f"Created {spec['rol'].value} user: {spec['correo']}")
            else:
                usuario.nombre = spec["nombre"]
                usuario.rol = spec["rol"]
                usuario.estado = True
                usuario.password_hash = hash_password(spec["password"])
                print(f"Updated {spec['rol'].value} user: {spec['correo']}")

        db.commit()
        print("\nDone. Test admin credentials:")
        for spec in TEST_ADMINS:
            print(f"  {spec['rol'].value:<12} {spec['correo']:<28} {spec['password']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
