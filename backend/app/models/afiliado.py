from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Afiliado(Base):
    """A cooperativa's affiliate/member.

    `password_hash` was added to the real database by hand for this phase
    (nullable, same pattern as `usuarios_admin.password_hash`) specifically
    so real affiliate authentication becomes possible — see
    ../../../SCHEMA_NOTES.md and alembic/versions/ for the follow-up
    migration that documents this column for anyone provisioning a fresh
    database from scratch."""

    __tablename__ = "afiliados"
    __table_args__ = (
        UniqueConstraint("cooperativa_id", "documento", name="uq_afiliados_cooperativa_documento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cooperativa_id: Mapped[int] = mapped_column(ForeignKey("cooperativas.id"), nullable=False, index=True)

    documento: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(100), nullable=False)
    correo: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Nullable — set only once the affiliate completes self-registration
    # against a roster row an admin already loaded. Never returned in any
    # API response (see schemas/afiliado.py, which simply omits the field).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cooperativa = relationship("Cooperativa", back_populates="afiliados")
    cupo_credito = relationship("CupoCredito", back_populates="afiliado", uselist=False)
    transacciones = relationship("Transaccion", back_populates="afiliado")

    @property
    def cooperativa_nombre(self) -> str | None:
        """Convenience accessor so AfiliadoOut can expose the cooperative's
        display name without a dedicated public lookup endpoint — the
        affiliate-facing schema otherwise only carries `cooperativa_id`."""
        return self.cooperativa.nombre if self.cooperativa is not None else None
