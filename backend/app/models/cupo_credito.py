from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CupoCredito(Base):
    """One active credit quota per affiliate. `cupo_disponible` stores the
    remaining/available balance DIRECTLY (it is decremented as it's spent) —
    unlike an earlier design assumption (`monto_usado`, an accumulated
    consumed amount), there is no "total minus used" arithmetic needed here;
    `cupo_disponible` IS the available balance."""

    __tablename__ = "cupos_credito"
    __table_args__ = (
        CheckConstraint(
            "cupo_total >= 0 AND cupo_disponible >= 0 AND cupo_disponible <= cupo_total",
            name="ck_cupos_credito_montos_validos",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    afiliado_id: Mapped[int] = mapped_column(ForeignKey("afiliados.id"), nullable=False, unique=True, index=True)

    cupo_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cupo_disponible: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    afiliado = relationship("Afiliado", back_populates="cupo_credito")
