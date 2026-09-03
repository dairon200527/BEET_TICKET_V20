"""
Append-only audit logging (`logs_auditoria`).

Every mutating admin action routes through `record()` here — nothing else
in the codebase should construct a `LogAuditoria` row directly. There is
no update/delete path for this table anywhere in the API.

NOTE: unlike an earlier design assumption, the real `logs_auditoria` table
has no `cooperativa_id` or `afiliado_relacionado_id` columns — tenant
scoping for reading these logs back goes through `usuario_admin_id ->
usuarios_admin.cooperativa_id` (see routers/admin.py), not a column on
this table itself.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.log_auditoria import LogAuditoria


def _json_safe(value: Any) -> Any:
    """Recursively converts a value into something PostgreSQL's JSON codec
    can serialize. Callers routinely build `detalles` from
    `payload.model_dump(exclude_unset=True)`, which can contain raw
    `Decimal`/enum/`date` values that Python's default JSON encoder
    rejects — sanitizing here, once, means no call site has to remember to."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def record(
    db: Session,
    *,
    accion: str,
    tabla_afectada: str,
    usuario_admin_id: int | None = None,
    registro_id: int | None = None,
    detalles: dict | None = None,
) -> LogAuditoria:
    """Adds (and flushes) the log row on the CALLER's existing session/
    transaction — it does not commit. This lets an audit entry live or
    die atomically with the business change it documents."""
    log = LogAuditoria(
        usuario_admin_id=usuario_admin_id,
        accion=accion,
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        detalles=_json_safe(detalles) if detalles is not None else None,
    )
    db.add(log)
    db.flush()
    return log
