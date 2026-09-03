from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Convenio(Base):
    """A benefit agreement with a merchant. NOTE: unlike an earlier design
    assumption, the real schema has no `marca`, `categoria`, `tope`, or
    `tope_periodicidad` columns — those UI fields have no backing column and
    are not part of this integration pass's data model."""

    __tablename__ = "convenios"
    __table_args__ = (
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin >= fecha_inicio",
            name="ck_convenios_fecha_fin_valida",
        ),
        CheckConstraint(
            "precio_publico >= 0 AND precio_beet >= 0",
            name="ck_convenios_precios_no_negativos",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cooperativa_id: Mapped[int] = mapped_column(ForeignKey("cooperativas.id"), nullable=False, index=True)

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    precio_publico: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_beet: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)

    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Which of the 4 fixed, code-owned catalog designs (see
    # app.services.plantillas_catalogo.CATALOGO) this convenio uses for
    # its tickets — a plain string, never a foreign key: these designs
    # aren't real per-convenio `plantillas` rows, so there's nothing to
    # point a FK at. NULL means "no selection" — pdf_service falls back
    # to any legacy per-convenio plantilla, then the generic ticket.
    # Never constrained at the DB level (only validated in Python against
    # CATALOGO's keys — see routers/convenios.py) so a new design can be
    # added without touching the schema.
    plantilla_catalogo_clave: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cooperativa = relationship("Cooperativa", back_populates="convenios")
    plantillas = relationship("Plantilla", back_populates="convenio")
    unidades_inventario = relationship("UnidadInventario", back_populates="convenio")
    transacciones = relationship("Transaccion", back_populates="convenio")
