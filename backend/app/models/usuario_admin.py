from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RolAdmin


class UsuarioAdmin(Base):
    """Cooperative back-office user. `rol` is the ONLY source of truth for
    authorization — it is read from this row (via the JWT built at login
    time), never from anything the frontend sends on a request."""

    __tablename__ = "usuarios_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable in the real schema — a SUPER_ADMIN belongs to no single
    # cooperativa (they administer all of them). ADMIN/LECTOR must always
    # have one; that's enforced at the application layer (see
    # schemas/usuario_admin.py), not by a DB-level CHECK, since the DB has
    # no way to make a NOT NULL constraint conditional on another column.
    cooperativa_id: Mapped[int | None] = mapped_column(ForeignKey("cooperativas.id"), nullable=True, index=True)

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    correo: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    rol: Mapped[RolAdmin] = mapped_column(Enum(RolAdmin, name="rol_admin", native_enum=False, length=30), nullable=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Nullable in the real schema — an admin row can exist before a password
    # is ever set. Never returned in API responses.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cooperativa = relationship("Cooperativa", back_populates="usuarios_admin")
