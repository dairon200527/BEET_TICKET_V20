from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Plantilla(Base):
    """Exactly the real, existing columns — no `clave`, no `slug`, no
    schema change of any kind. A per-convenio, versioned uploaded/
    visual-editor design (`convenio_id`/`version` unique together; the
    highest `version` with estado=true is "in effect" for that convenio
    — see `pdf_service.plantilla_activa()`).

    There is currently NO column anywhere linking a convenio to one of
    the 4 fixed brand designs in `app.services.plantillas_catalogo` —
    those remain purely code-side constants for now (listed read-only
    via `GET /api/plantillas/catalogo`), with no persistence and no FK
    of any kind into this table. That link is deferred to a later stage
    once its real design is settled — see that module's docstring."""

    __tablename__ = "plantillas"
    __table_args__ = (
        UniqueConstraint("convenio_id", "version", name="uq_plantillas_version"),
        CheckConstraint("version > 0", name="chk_plantillas_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    convenio_id: Mapped[int] = mapped_column(ForeignKey("convenios.id"), nullable=False, index=True)

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Reference only — never a raw file path supplied by a client.
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)

    estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    convenio = relationship("Convenio", back_populates="plantillas")
