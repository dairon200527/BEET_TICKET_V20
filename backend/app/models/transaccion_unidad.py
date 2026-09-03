from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoTransaccionUnidad


class TransaccionUnidad(Base):
    """Junction table: which inventory unit a transaction assigned, and that
    unit's fulfillment state WITHIN this transaction (separate from the
    unit's own lifecycle state in unidades_inventario.estado). `unidad_id`
    is UNIQUE — the database refuses to let the same unit be linked to two
    transactions."""

    __tablename__ = "transaccion_unidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaccion_id: Mapped[int] = mapped_column(ForeignKey("transacciones.id"), nullable=False, index=True)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_inventario.id"), nullable=False, unique=True)

    ticket_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[EstadoTransaccionUnidad] = mapped_column(
        Enum(EstadoTransaccionUnidad, name="estado_transaccion_unidad", native_enum=False, length=30),
        nullable=False,
        default=EstadoTransaccionUnidad.ASIGNADA,
    )
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaccion = relationship("Transaccion", back_populates="unidades")
    unidad = relationship("UnidadInventario", back_populates="transaccion_unidad")
