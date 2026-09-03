from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoTransaccion, MetodoPago


class Transaccion(Base):
    """A purchase. NOTE: unlike an earlier design assumption, this table has
    no denormalized `cooperativa_id` in the real schema — the cooperativa
    must be derived via `afiliado_id -> afiliados.cooperativa_id`."""

    __tablename__ = "transacciones"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_transacciones_cantidad_positiva"),
        CheckConstraint("subtotal >= 0 AND total >= 0", name="ck_transacciones_montos_no_negativos"),
        CheckConstraint("numero_cuotas IS NULL OR numero_cuotas > 0", name="ck_transacciones_cuotas_positivas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    afiliado_id: Mapped[int] = mapped_column(ForeignKey("afiliados.id"), nullable=False, index=True)
    convenio_id: Mapped[int] = mapped_column(ForeignKey("convenios.id"), nullable=False, index=True)

    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    metodo_pago: Mapped[MetodoPago] = mapped_column(Enum(MetodoPago, name="metodo_pago", native_enum=False, length=30), nullable=False)
    numero_cuotas: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estado: Mapped[EstadoTransaccion] = mapped_column(
        Enum(EstadoTransaccion, name="estado_transaccion", native_enum=False, length=30),
        nullable=False,
        default=EstadoTransaccion.PENDIENTE,
        index=True,
    )
    referencia_pago: Mapped[str | None] = mapped_column(String(150), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    afiliado = relationship("Afiliado", back_populates="transacciones")
    convenio = relationship("Convenio", back_populates="transacciones")
    unidades = relationship("TransaccionUnidad", back_populates="transaccion")
    documento_asuncion_deuda = relationship("DocumentoAsuncionDeuda", back_populates="transaccion", uselist=False)
