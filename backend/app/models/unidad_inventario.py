from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoUnidadInventario


class UnidadInventario(Base):
    """One redeemable code/QR/unit. Assignment to an affiliate happens
    exclusively through transaccion_unidades.

    KNOWN SCHEMA QUIRK (documented, not "fixed" — see SCHEMA_NOTES.md): the
    real database column has `DEFAULT 'DISPONIBLE'` (uppercase) but its own
    CHECK constraint only allows lowercase values, so relying on the
    database's own default would violate its own CHECK. This model never
    relies on that default — `default=` below is set client-side in Python
    to the correct lowercase value, so every INSERT issued by this app
    always sends an explicit, valid `estado`.
    """

    __tablename__ = "unidades_inventario"

    id: Mapped[int] = mapped_column(primary_key=True)
    convenio_id: Mapped[int] = mapped_column(ForeignKey("convenios.id"), nullable=False, index=True)

    codigo: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    estado: Mapped[EstadoUnidadInventario] = mapped_column(
        # values_callable is required here: this enum's member NAMES are
        # uppercase (DISPONIBLE) but its member VALUES — and the real DB's
        # stored strings — are lowercase (disponible). SQLAlchemy's Enum
        # type reads/writes by member .name by default, not .value; without
        # values_callable it would look for "DISPONIBLE" in the database
        # and never match the real lowercase rows.
        Enum(
            EstadoUnidadInventario,
            name="estado_unidad_inventario",
            native_enum=False,
            length=30,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EstadoUnidadInventario.DISPONIBLE,
        index=True,
    )
    fecha_ingreso: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Real columns, currently unused by any endpoint/UI — mapped here so
    # the model matches the real table exactly, nothing more.
    contenido: Mapped[str | None] = mapped_column(Text, nullable=True)
    grupo: Mapped[str | None] = mapped_column(String(100), nullable=True)

    convenio = relationship("Convenio", back_populates="unidades_inventario")
    transaccion_unidad = relationship("TransaccionUnidad", back_populates="unidad", uselist=False)
