"""
Credit quotas (`/api/cupos`) — admin endpoints scoped to
`admin.cooperativa_id` through the owning affiliate, plus the affiliate's
own read-only `/me`. NOTE: unlike an earlier design assumption,
`cupo_disponible` stores the available balance DIRECTLY (not an
accumulated "used" amount) — see models/cupo_credito.py. `/me` is
registered BEFORE `/{afiliado_id}` — see afiliados.py for why the
ordering matters.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import (
    get_current_affiliate,
    require_write_access,
    resolve_cooperativa_scope,
    resolve_cooperativa_scope_write,
)
from app.models.afiliado import Afiliado
from app.models.cupo_credito import CupoCredito
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.common import Message
from app.schemas.cupo import CupoAsignacionMasivaRequest, CupoCreditoOut, CupoCreditoUpdate
from app.services import audit_service
from app.services.cupo_service import ajustar_cupo_total

router = APIRouter(prefix="/api/cupos", tags=["cupos"])


def _get_scoped_afiliado_or_404(db: Session, cooperativa_id: int, afiliado_id: int) -> Afiliado:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None or afiliado.cooperativa_id != cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Afiliado no encontrado.")
    return afiliado


@router.get("/me", response_model=CupoCreditoOut)
def mi_cupo(afiliado: Afiliado = Depends(get_current_affiliate), db: Session = Depends(get_db)) -> CupoCreditoOut:
    cupo = db.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado.id)).scalar_one_or_none()
    if cupo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes un cupo de crédito asignado.")
    return CupoCreditoOut.model_validate(cupo)


@router.get("/{afiliado_id}", response_model=CupoCreditoOut)
def obtener(
    afiliado_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> CupoCreditoOut:
    _get_scoped_afiliado_or_404(db, cooperativa_id, afiliado_id)
    cupo = db.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado_id)).scalar_one_or_none()
    if cupo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este afiliado no tiene un cupo de crédito asignado.")
    return CupoCreditoOut.model_validate(cupo)


@router.patch("/{afiliado_id}", response_model=CupoCreditoOut)
def actualizar(
    afiliado_id: int,
    payload: CupoCreditoUpdate,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CupoCreditoOut:
    afiliado = _get_scoped_afiliado_or_404(db, cooperativa_id, afiliado_id)
    cupo = db.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado.id)).scalar_one_or_none()
    if cupo is None:
        cupo = CupoCredito(afiliado_id=afiliado.id, cupo_total=0, cupo_disponible=0)
        db.add(cupo)
        db.flush()

    data = payload.model_dump(exclude_unset=True)
    if "cupo_disponible" in data:
        # An explicit cupo_disponible always wins over the automatic
        # delta-adjustment below.
        nuevo_total = data.get("cupo_total", cupo.cupo_total)
        nuevo_disponible = data["cupo_disponible"]
        if nuevo_disponible > nuevo_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cupo disponible no puede ser mayor al cupo total.")
        cupo.cupo_total = nuevo_total
        cupo.cupo_disponible = nuevo_disponible
        for field, value in data.items():
            if field not in ("cupo_total", "cupo_disponible"):
                setattr(cupo, field, value)
    else:
        for field, value in data.items():
            if field == "cupo_total":
                ajustar_cupo_total(cupo, value)
            else:
                setattr(cupo, field, value)

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="cupo_actualizado", tabla_afectada="cupos_credito", registro_id=cupo.id,
        detalles=data,
    )
    db.commit()
    db.refresh(cupo)
    return CupoCreditoOut.model_validate(cupo)


@router.post("/asignacion-masiva", response_model=Message)
def asignacion_masiva(
    payload: CupoAsignacionMasivaRequest,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> Message:
    afiliados = (
        db.execute(
            select(Afiliado).where(Afiliado.id.in_(payload.afiliado_ids), Afiliado.cooperativa_id == cooperativa_id)
        )
        .scalars()
        .all()
    )
    asignados = 0
    for afiliado in afiliados:
        cupo = db.execute(select(CupoCredito).where(CupoCredito.afiliado_id == afiliado.id)).scalar_one_or_none()
        if cupo is None:
            cupo = CupoCredito(afiliado_id=afiliado.id, cupo_total=payload.cupo_total, cupo_disponible=payload.cupo_total)
            db.add(cupo)
        else:
            cupo.cupo_total = payload.cupo_total
            cupo.cupo_disponible = payload.cupo_total
        asignados += 1

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="cupo_asignacion_masiva", tabla_afectada="cupos_credito",
        detalles={"afiliado_ids": payload.afiliado_ids, "cupo_total": str(payload.cupo_total), "asignados": asignados},
    )
    db.commit()
    return Message(detail=f"Cupo asignado a {asignados} afiliado(s).")
