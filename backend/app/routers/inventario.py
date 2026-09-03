"""
Inventory (`/api/inventario`) — every unit is scoped through its
convenio's cooperativa_id. Bloqueo/desbloqueo are the ONLY admin-triggered
state transitions exposed here.

NOTE: unlike an earlier design assumption, `unidades_inventario` has no
`fecha_carga`/`fecha_vencimiento` columns in the real schema, so the bulk
upload only takes a `codigo`, and there is no "mark expired" maintenance
endpoint (nothing to compare against). `codigo` is also GLOBALLY unique
(not per-convenio) per the real schema's UNIQUE constraint.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_write_access, resolve_cooperativa_scope, resolve_cooperativa_scope_write
from app.models.convenio import Convenio
from app.models.enums import EstadoUnidadInventario
from app.models.unidad_inventario import UnidadInventario
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.common import CargaMasivaResultado, Message, Page
from app.schemas.inventario import (
    BloqueoInventarioRequest,
    InventarioResumenOut,
    UnidadInventarioCreate,
    UnidadInventarioOut,
)
from app.services import audit_service
from app.utils.bulk_upload import parse_rows, require_columns, summarize_validation_error
from app.utils.file_validation import ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES, validate_size, validate_upload
from app.utils.query_params import clamp_pagination

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


def _get_scoped_convenio_or_404(db: Session, cooperativa_id: int, convenio_id: int) -> Convenio:
    convenio = db.get(Convenio, convenio_id)
    if convenio is None or convenio.cooperativa_id != cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convenio no encontrado.")
    return convenio


@router.get("", response_model=Page[UnidadInventarioOut])
def listar(
    convenio_id: int = Query(...),
    estado: EstadoUnidadInventario | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[UnidadInventarioOut]:
    _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    page, page_size = clamp_pagination(page, page_size)

    stmt = select(UnidadInventario).where(UnidadInventario.convenio_id == convenio_id)
    if estado is not None:
        stmt = stmt.where(UnidadInventario.estado == estado)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(UnidadInventario.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[UnidadInventarioOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/resumen", response_model=InventarioResumenOut)
def resumen(
    convenio_id: int = Query(...),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> InventarioResumenOut:
    _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    conteos = dict(
        db.execute(
            select(UnidadInventario.estado, func.count())
            .where(UnidadInventario.convenio_id == convenio_id)
            .group_by(UnidadInventario.estado)
        ).all()
    )
    return InventarioResumenOut(
        convenio_id=convenio_id,
        total=sum(conteos.values()),
        disponible=conteos.get(EstadoUnidadInventario.DISPONIBLE, 0),
        bloqueada=conteos.get(EstadoUnidadInventario.BLOQUEADA, 0),
        entregada=conteos.get(EstadoUnidadInventario.ENTREGADA, 0),
        redimida=conteos.get(EstadoUnidadInventario.REDIMIDA, 0),
        cancelada=conteos.get(EstadoUnidadInventario.CANCELADA, 0),
        vencida=conteos.get(EstadoUnidadInventario.VENCIDA, 0),
    )


@router.post("/carga", response_model=CargaMasivaResultado)
async def carga(
    convenio_id: int = Query(...),
    file: UploadFile = File(...),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CargaMasivaResultado:
    """Bulk unit load from CSV/XLSX for ONE already-selected convenio.
    Expected column: codigo. `codigo` is globally unique — the DB's own
    UNIQUE constraint is the final backstop even if this check were ever
    bypassed."""
    convenio = _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    validate_upload(file, ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES)
    content = await file.read()
    validate_size(len(content))
    headers, rows = parse_rows(file.filename or "", content)
    require_columns(headers, ["codigo"])

    creados = duplicados = invalidos = 0
    errores: list[str] = []
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            data = UnidadInventarioCreate(codigo=row.get("codigo", ""))
        except ValidationError as exc:
            invalidos += 1
            errores.append(f"Fila {idx}: {summarize_validation_error(exc)}")
            continue

        existente = db.execute(select(UnidadInventario).where(UnidadInventario.codigo == data.codigo)).scalar_one_or_none()
        if existente is not None:
            duplicados += 1
            errores.append(f"Fila {idx}: el código '{data.codigo}' ya existe.")
            continue

        db.add(UnidadInventario(convenio_id=convenio.id, codigo=data.codigo))
        creados += 1

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="inventario_carga_masiva", tabla_afectada="unidades_inventario", registro_id=convenio.id,
        detalles={"creados": creados, "duplicados": duplicados, "invalidos": invalidos},
    )
    db.commit()
    return CargaMasivaResultado(
        detail=(
            f"Convenio: {convenio.nombre} · {len(rows)} registros procesados · "
            f"{creados} agregados, {duplicados} duplicados, {invalidos} inválidos. "
            "El inventario existente no fue modificado."
        ),
        creados=creados, omitidos=duplicados, invalidos=invalidos, errores=errores,
    )


@router.post("/carga-masiva", response_model=CargaMasivaResultado)
async def carga_masiva(
    file: UploadFile = File(...),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CargaMasivaResultado:
    """Bulk unit load across MULTIPLE convenios in one file — unlike
    `/carga` above (which loads codes into one already-selected convenio),
    each row here names its own convenio by `nombre` (exact match, scoped
    to the effective cooperativa — never a client-supplied convenio_id).
    Expected columns: convenio, codigo.

    A row is invalid if its convenio name doesn't match any convenio in
    that cooperativa, or if its codigo is missing/malformed; a row is a
    duplicate if its codigo already exists anywhere (codigo is GLOBALLY
    unique, not per-convenio — see models/unidad_inventario.py). Neither
    stops the rest of the file from loading."""
    validate_upload(file, ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES)
    content = await file.read()
    validate_size(len(content))
    headers, rows = parse_rows(file.filename or "", content)
    require_columns(headers, ["convenio", "codigo"])

    convenios_por_nombre = {
        c.nombre: c for c in db.execute(select(Convenio).where(Convenio.cooperativa_id == cooperativa_id)).scalars().all()
    }

    creados = duplicados = invalidos = 0
    errores: list[str] = []
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        nombre_convenio = (row.get("convenio") or "").strip()
        convenio = convenios_por_nombre.get(nombre_convenio)
        if convenio is None:
            invalidos += 1
            errores.append(f"Fila {idx}: el convenio '{nombre_convenio}' no existe en tu cooperativa.")
            continue

        try:
            data = UnidadInventarioCreate(codigo=row.get("codigo", ""))
        except ValidationError as exc:
            invalidos += 1
            errores.append(f"Fila {idx}: {summarize_validation_error(exc)}")
            continue

        existente = db.execute(select(UnidadInventario).where(UnidadInventario.codigo == data.codigo)).scalar_one_or_none()
        if existente is not None:
            duplicados += 1
            errores.append(f"Fila {idx}: el código '{data.codigo}' ya existe.")
            continue

        db.add(UnidadInventario(convenio_id=convenio.id, codigo=data.codigo))
        creados += 1

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="inventario_carga_masiva_multiconvenio", tabla_afectada="unidades_inventario",
        detalles={"creados": creados, "duplicados": duplicados, "invalidos": invalidos},
    )
    db.commit()
    return CargaMasivaResultado(
        detail=f"Carga completada: {creados} creadas, {duplicados} duplicadas, {invalidos} inválidas.",
        creados=creados, omitidos=duplicados, invalidos=invalidos, errores=errores,
    )


@router.post("/bloquear", response_model=Message)
def bloquear(
    payload: BloqueoInventarioRequest,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> Message:
    rows = (
        db.execute(
            select(UnidadInventario)
            .join(Convenio)
            .where(UnidadInventario.id.in_(payload.unidad_ids), Convenio.cooperativa_id == cooperativa_id)
        )
        .scalars()
        .all()
    )
    bloqueadas = 0
    for unidad in rows:
        if unidad.estado == EstadoUnidadInventario.DISPONIBLE:
            unidad.estado = EstadoUnidadInventario.BLOQUEADA
            bloqueadas += 1

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="inventario_bloqueado", tabla_afectada="unidades_inventario",
        detalles={"unidad_ids": payload.unidad_ids, "motivo": payload.motivo, "bloqueadas": bloqueadas},
    )
    db.commit()
    return Message(detail=f"{bloqueadas} unidad(es) bloqueada(s).")


@router.post("/desbloquear", response_model=Message)
def desbloquear(
    payload: BloqueoInventarioRequest,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> Message:
    rows = (
        db.execute(
            select(UnidadInventario)
            .join(Convenio)
            .where(UnidadInventario.id.in_(payload.unidad_ids), Convenio.cooperativa_id == cooperativa_id)
        )
        .scalars()
        .all()
    )
    desbloqueadas = 0
    for unidad in rows:
        if unidad.estado == EstadoUnidadInventario.BLOQUEADA:
            unidad.estado = EstadoUnidadInventario.DISPONIBLE
            desbloqueadas += 1

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="inventario_desbloqueado", tabla_afectada="unidades_inventario",
        detalles={"unidad_ids": payload.unidad_ids, "motivo": payload.motivo, "desbloqueadas": desbloqueadas},
    )
    db.commit()
    return Message(detail=f"{desbloqueadas} unidad(es) desbloqueada(s).")
