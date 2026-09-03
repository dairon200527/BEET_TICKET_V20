"""
Transactions (`/api/transacciones`) — admin READ-ONLY listing, plus the
affiliate-facing purchase flow (`POST /comprar`) and the affiliate's own
`/me` listing/detail.

`/comprar`, `/me`, and `/me/{transaccion_id}` are all registered BEFORE
`/{transaccion_id}` — see afiliados.py for why the ordering matters (a
dynamic `/{transaccion_id}` registered first would swallow "me" as a
literal path segment before Pydantic even gets a chance to reject it as
a non-numeric id).

Unlike an earlier design assumption, `transacciones` has no denormalized
`cooperativa_id` — it is derived here via a join through `afiliados`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_affiliate, resolve_cooperativa_scope
from app.models.afiliado import Afiliado
from app.models.enums import EstadoTransaccion
from app.models.transaccion import Transaccion
from app.models.transaccion_unidad import TransaccionUnidad
from app.models.unidad_inventario import UnidadInventario
from app.schemas.common import Page
from app.schemas.transaccion import CompraRequest, TransaccionDetalleOut, TransaccionOut
from app.services import transaction_service
from app.utils.query_params import clamp_pagination

router = APIRouter(prefix="/api/transacciones", tags=["transacciones"])


def _codigos_de(db: Session, transaccion_id: int) -> list[str]:
    rows = (
        db.execute(
            select(UnidadInventario.codigo)
            .join(TransaccionUnidad, TransaccionUnidad.unidad_id == UnidadInventario.id)
            .where(TransaccionUnidad.transaccion_id == transaccion_id)
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.post("/comprar", response_model=TransaccionDetalleOut, status_code=201)
def comprar(
    payload: CompraRequest,
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> TransaccionDetalleOut:
    transaccion, resultado_pago = transaction_service.procesar_compra(db, afiliado, payload)
    out = TransaccionDetalleOut.model_validate(transaccion)
    out.codigos = _codigos_de(db, transaccion.id)
    if resultado_pago is not None and not resultado_pago.aprobado:
        out.resultado_pago = resultado_pago.tipo
        out.motivo_rechazo = resultado_pago.motivo_rechazo
    return out


@router.get("/me", response_model=Page[TransaccionOut])
def mis_transacciones(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> Page[TransaccionOut]:
    page, page_size = clamp_pagination(page, page_size)
    stmt = select(Transaccion).where(Transaccion.afiliado_id == afiliado.id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Transaccion.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[TransaccionOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/me/{transaccion_id}", response_model=TransaccionDetalleOut)
def mi_transaccion(transaccion_id: int, afiliado: Afiliado = Depends(get_current_affiliate), db: Session = Depends(get_db)) -> TransaccionDetalleOut:
    transaccion = db.execute(
        select(Transaccion).where(Transaccion.id == transaccion_id, Transaccion.afiliado_id == afiliado.id)
    ).scalar_one_or_none()
    if transaccion is None:
        raise HTTPException(status_code=404, detail="Transacción no encontrada.")
    out = TransaccionDetalleOut.model_validate(transaccion)
    out.codigos = _codigos_de(db, transaccion.id)
    return out


@router.get("", response_model=Page[TransaccionOut])
def listar(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    estado: EstadoTransaccion | None = Query(default=None),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[TransaccionOut]:
    page, page_size = clamp_pagination(page, page_size)
    stmt = (
        select(Transaccion)
        .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
        .where(Afiliado.cooperativa_id == cooperativa_id)
    )
    if estado is not None:
        stmt = stmt.where(Transaccion.estado == estado)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Transaccion.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[TransaccionOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/{transaccion_id}", response_model=TransaccionDetalleOut)
def obtener(
    transaccion_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> TransaccionDetalleOut:
    transaccion = (
        db.execute(
            select(Transaccion)
            .join(Afiliado, Afiliado.id == Transaccion.afiliado_id)
            .where(Transaccion.id == transaccion_id, Afiliado.cooperativa_id == cooperativa_id)
        )
        .scalar_one_or_none()
    )
    if transaccion is None:
        raise HTTPException(status_code=404, detail="Transacción no encontrada.")
    out = TransaccionDetalleOut.model_validate(transaccion)
    out.codigos = _codigos_de(db, transaccion.id)
    return out
