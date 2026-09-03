from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoDocumento


class DocumentoAsuncionDeuda(Base):
    """One per transaction (enforced unique). Stores only metadata and a
    Firebase Storage reference — never the raw signature image or the PDF
    binary itself. NOTE: unlike an earlier design assumption, this table has
    no `afiliado_id`, `valor`, or `cuotas` columns — those are derived by
    joining through `transaccion_id` to the transacciones/afiliados tables."""

    __tablename__ = "documentos_asuncion_deuda"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaccion_id: Mapped[int] = mapped_column(ForeignKey("transacciones.id"), nullable=False, unique=True, index=True)

    documento_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    firma_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[EstadoDocumento] = mapped_column(
        Enum(EstadoDocumento, name="estado_documento", native_enum=False, length=30),
        nullable=False,
        default=EstadoDocumento.PENDIENTE,
    )

    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_firma: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaccion = relationship("Transaccion", back_populates="documento_asuncion_deuda")
