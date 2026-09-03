"""
Credit quota (cupo) balance mutation.

The one rule that matters: `cupo_disponible` is only ever changed here,
only ever inside a caller's open DB transaction, and only ever after
locking the row with `SELECT ... FOR UPDATE`. The frontend never supplies
(and this module never trusts) a balance — every check re-reads the row
fresh, under lock, immediately before deciding.

Unlike an earlier design assumption, `cupo_disponible` stores the
available balance DIRECTLY (it's decremented as it's spent), not an
accumulated "used" amount that has to be subtracted from a total — see
models/cupo_credito.py / SCHEMA_NOTES.md.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.afiliado import Afiliado
from app.models.cupo_credito import CupoCredito


def ajustar_cupo_total(cupo: CupoCredito, nuevo_total: Decimal) -> None:
    """Changes `cupo.cupo_total` and moves `cupo.cupo_disponible` by the
    SAME delta, clamped to a valid `[0, nuevo_total]` range, instead of
    leaving the available balance untouched (which would either silently
    grant/withhold credit on a raise, or violate the table's own
    `CHECK(cupo_disponible <= cupo_total)` on a cut). This is the one
    policy used everywhere `cupo_total` changes outside a purchase debit:
    the manual `PATCH /api/cupos/{afiliado_id}` endpoint and the afiliados
    bulk-upload upsert both call this so the behavior never drifts apart
    between the two."""
    delta = nuevo_total - cupo.cupo_total
    cupo.cupo_total = nuevo_total
    cupo.cupo_disponible = max(Decimal("0"), min(nuevo_total, cupo.cupo_disponible + delta))


def lock_cupo_for_afiliado(db: Session, afiliado_id: int) -> CupoCredito:
    """Must be called inside an already-open transaction. Blocks (rather
    than skipping) if another transaction is concurrently touching the
    same row, so two simultaneous purchases can never both read the
    balance before either has committed."""
    cupo = db.execute(
        select(CupoCredito).where(CupoCredito.afiliado_id == afiliado_id).with_for_update()
    ).scalar_one_or_none()
    if cupo is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tienes un cupo de crédito asignado.")
    return cupo


def verify_and_debit(db: Session, afiliado: Afiliado, monto: Decimal) -> CupoCredito:
    """Validates affiliate/cupo state and sufficient balance, then debits
    `cupo_disponible` atomically. Raises HTTPException(400) on any
    failure; the caller (transaction_service.procesar_compra) rolls back
    the entire purchase on this, never applying a partial debit."""
    if not afiliado.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El afiliado no está activo.")
    if monto <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El monto debe ser mayor a cero.")

    cupo = lock_cupo_for_afiliado(db, afiliado.id)
    if not cupo.estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cupo de crédito no está activo.")
    if cupo.cupo_disponible < monto:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Saldo de cupo insuficiente.")

    cupo.cupo_disponible = cupo.cupo_disponible - monto
    db.flush()
    return cupo
