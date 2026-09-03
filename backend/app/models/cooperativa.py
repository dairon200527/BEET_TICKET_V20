from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Cooperativa(Base):
    """The tenant root. Every other business table hangs off this one,
    directly or indirectly, through cooperativa_id (or, for tables that
    don't carry it directly — transacciones, logs_auditoria — through a
    join to a table that does)."""

    __tablename__ = "cooperativas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nit: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    afiliados = relationship("Afiliado", back_populates="cooperativa")
    usuarios_admin = relationship("UsuarioAdmin", back_populates="cooperativa")
    convenios = relationship("Convenio", back_populates="cooperativa")
