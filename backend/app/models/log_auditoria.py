from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LogAuditoria(Base):
    """Append-only. Nothing in the application ever updates or deletes a row
    here. NOTE: unlike an earlier design assumption, this table has no
    `cooperativa_id` or `afiliado_relacionado_id` — tenant-scoping for audit
    logs must go through `usuario_admin_id -> usuarios_admin.cooperativa_id`."""

    __tablename__ = "logs_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_admin_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios_admin.id"), nullable=True, index=True)

    accion: Mapped[str] = mapped_column(String(50), nullable=False)
    tabla_afectada: Mapped[str] = mapped_column(String(100), nullable=False)
    registro_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detalles: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    usuario_admin = relationship("UsuarioAdmin")
