"""
Affiliate directory (`/api/afiliados`) — admin CRUD, plus the affiliate's
own self-service `/me` endpoints.

Admin endpoints are scoped via `resolve_cooperativa_scope`/`_write`
(ADMIN/LECTOR: always their own `admin.cooperativa_id`; SUPER_ADMIN: the
cooperativa explicitly selected via `?cooperativa_id=`). The `/me`
endpoints never accept or
trust a client-supplied `afiliado_id`; the identity comes exclusively from
`get_current_affiliate`. NOTE: `/me` routes are registered BEFORE
`/{afiliado_id}` — FastAPI matches routes in registration order, and a
dynamic `/{afiliado_id}` registered first would swallow `/me` as a
(numeric-parse-failing) id instead of matching the static route.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
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
from app.schemas.afiliado import AfiliadoAdminUpdate, AfiliadoCargaMasivaRow, AfiliadoCreate, AfiliadoOut, AfiliadoSelfUpdate
from app.schemas.common import CargaMasivaResultado, Message, Page
from app.services import audit_service
from app.services.cupo_service import ajustar_cupo_total
from app.utils.bulk_upload import parse_bool_or_none, parse_rows, require_columns, summarize_validation_error
from app.utils.file_validation import ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES, validate_size, validate_upload
from app.utils.query_params import clamp_pagination, resolve_sort_column

router = APIRouter(prefix="/api/afiliados", tags=["afiliados"])


@router.get("/me", response_model=AfiliadoOut)
def mi_perfil(afiliado: Afiliado = Depends(get_current_affiliate)) -> AfiliadoOut:
    return AfiliadoOut.model_validate(afiliado)


@router.patch("/me", response_model=AfiliadoOut)
def actualizar_mi_perfil(
    payload: AfiliadoSelfUpdate,
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> AfiliadoOut:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(afiliado, field, value)
    db.commit()
    db.refresh(afiliado)
    return AfiliadoOut.model_validate(afiliado)

_SORTABLE_FIELDS = {"nombres", "apellidos", "documento", "correo", "created_at"}


def _get_scoped_or_404(db: Session, cooperativa_id: int, afiliado_id: int) -> Afiliado:
    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None or afiliado.cooperativa_id != cooperativa_id:
        # 404, not 403 — never confirm a cross-tenant affiliate exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Afiliado no encontrado.")
    return afiliado


@router.get("", response_model=Page[AfiliadoOut])
def listar(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    estado: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[AfiliadoOut]:
    page, page_size = clamp_pagination(page, page_size)
    stmt = select(Afiliado).where(Afiliado.cooperativa_id == cooperativa_id)
    if estado is not None:
        stmt = stmt.where(Afiliado.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (Afiliado.nombres.ilike(like))
            | (Afiliado.apellidos.ilike(like))
            | (Afiliado.documento.ilike(like))
            | (Afiliado.correo.ilike(like))
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = resolve_sort_column(Afiliado, sort_by, _SORTABLE_FIELDS, default="nombres")

    # Cupo shown directly in the list (not just on "Ver detalle") — via a
    # single outerjoin in the SAME query, never a per-row lookup (N+1).
    rows = db.execute(
        stmt.outerjoin(CupoCredito, CupoCredito.afiliado_id == Afiliado.id)
        .add_columns(CupoCredito.cupo_total, CupoCredito.cupo_disponible)
        .order_by(column)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for afiliado, cupo_total, cupo_disponible in rows:
        out = AfiliadoOut.model_validate(afiliado)
        out.cupo_total = cupo_total
        out.cupo_disponible = cupo_disponible
        items.append(out)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/carga-masiva", response_model=CargaMasivaResultado)
async def carga_masiva(
    file: UploadFile = File(...),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CargaMasivaResultado:
    """Bulk affiliate roster load from CSV/XLSX — a real UPSERT, not
    create-only. Expected columns: documento, nombres, apellidos, correo,
    telefono (optional), cupo_total (required), estado (optional,
    accepts true/false/1/0/activo/inactivo/si/no).

    - New `documento` (scoped to the uploading admin's own cooperativa —
      the file never supplies a cooperativa_id): creates the afiliado AND
      its cupos_credito row (`cupo_disponible = cupo_total`, a fresh,
      unspent cupo).
    - Existing `documento`: UPDATES nombres/apellidos/correo/telefono
      unconditionally, `estado` only if the column has a value for this
      row (blank leaves it unchanged), and `cupo_total` only if it
      actually differs from the current value — using the exact same
      delta-adjustment policy as the manual `PATCH /api/cupos/{id}`
      endpoint (see cupo_service.ajustar_cupo_total) so raising/lowering
      a limit via Excel behaves identically to doing it by hand.
    - An afiliado that exists in the database but does NOT appear in the
      uploaded file is never touched — this bulk load only ever acts on
      rows explicitly present in the file, by design (it must not be
      possible to deactivate or drain someone's cupo by omission)."""
    validate_upload(file, ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES)
    content = await file.read()
    validate_size(len(content))
    headers, rows = parse_rows(file.filename or "", content)
    require_columns(headers, ["documento", "nombres", "apellidos", "correo", "cupo_total"])

    creados = actualizados = omitidos = invalidos = 0
    errores: list[str] = []
    cambios: list[str] = []
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            data = AfiliadoCargaMasivaRow(
                documento=row.get("documento", ""),
                nombres=row.get("nombres", ""),
                apellidos=row.get("apellidos", ""),
                correo=row.get("correo", ""),
                telefono=row.get("telefono") or None,
                cupo_total=row.get("cupo_total") or "0",
                cupo_disponible=row.get("cupo_disponible") or None,
            )
        except ValidationError as exc:
            invalidos += 1
            errores.append(f"Fila {idx}: {summarize_validation_error(exc)}")
            continue
        estado_val = parse_bool_or_none(row.get("estado"))

        existente = db.execute(
            select(Afiliado).where(Afiliado.cooperativa_id == cooperativa_id, Afiliado.documento == data.documento)
        ).scalar_one_or_none()

        if existente is not None:
            # Only fields that actually DIFFER from the current value are
            # written and counted — a row that matches an existing
            # documento with byte-for-byte identical values everywhere
            # (the common case when the same file, or one with only a
            # handful of real edits, gets re-uploaded) must report as
            # "sin cambios" (`omitidos`), never inflate `actualizados` —
            # that's what let a 1-field edit get misreported as "the
            # whole file was updated again".
            fila_cambios: list[str] = []

            def _set(field: str, nuevo):
                actual = getattr(existente, field)
                if actual != nuevo:
                    fila_cambios.append(f"Fila {idx}: {field} cambió de {actual!r} a {nuevo!r}.")
                    setattr(existente, field, nuevo)

            _set("nombres", data.nombres)
            _set("apellidos", data.apellidos)
            _set("correo", data.correo)
            _set("telefono", data.telefono)
            if estado_val is not None:
                _set("estado", estado_val)

            # `db.execute(select(...))` never auto-flushes on this session
            # (autoflush=False — see app/db/base.py); WITHOUT the explicit
            # `db.flush()` below, a duplicate `documento` within the SAME
            # uploaded file used to crash the whole batch here: row N
            # creates the afiliado and adds its CupoCredito to the session
            # but never flushes it, so row N+1's "does a cupo already
            # exist for this afiliado_id" query below never sees it,
            # concludes `cupo is None`, and adds a SECOND CupoCredito for
            # the same afiliado_id — violating cupos_credito's own
            # UNIQUE(afiliado_id) constraint at commit time and rolling
            # back every row in the file, not just the duplicate one.
            cupo = db.execute(select(CupoCredito).where(CupoCredito.afiliado_id == existente.id)).scalar_one_or_none()
            if cupo is None:
                cupo_disponible_inicial = data.cupo_disponible if data.cupo_disponible is not None else data.cupo_total
                db.add(CupoCredito(afiliado_id=existente.id, cupo_total=data.cupo_total, cupo_disponible=cupo_disponible_inicial))
                db.flush()
                fila_cambios.append(f"Fila {idx}: cupo_credito creado (cupo_total={data.cupo_total}).")
            elif data.cupo_total != cupo.cupo_total:
                anterior = cupo.cupo_total
                ajustar_cupo_total(cupo, data.cupo_total)
                fila_cambios.append(f"Fila {idx}: cupo_total cambió de {anterior!r} a {data.cupo_total!r}.")

            if fila_cambios:
                cambios.extend(fila_cambios)
                actualizados += 1
            else:
                omitidos += 1
        else:
            nuevo = Afiliado(
                cooperativa_id=cooperativa_id,
                documento=data.documento,
                nombres=data.nombres,
                apellidos=data.apellidos,
                correo=data.correo,
                telefono=data.telefono,
                estado=estado_val if estado_val is not None else True,
            )
            db.add(nuevo)
            db.flush()
            cupo_disponible_inicial = data.cupo_disponible if data.cupo_disponible is not None else data.cupo_total
            db.add(CupoCredito(afiliado_id=nuevo.id, cupo_total=data.cupo_total, cupo_disponible=cupo_disponible_inicial))
            db.flush()
            creados += 1

    audit_service.record(
        db,
        usuario_admin_id=admin.id,
        accion="afiliados_carga_masiva",
        tabla_afectada="afiliados",
        detalles={"creados": creados, "actualizados": actualizados, "sin_cambios": omitidos, "invalidos": invalidos},
    )
    db.commit()
    return CargaMasivaResultado(
        detail=(
            f"Carga completada: {creados} creados, {actualizados} actualizados, "
            f"{omitidos} sin cambios, {invalidos} inválidos."
        ),
        creados=creados, actualizados=actualizados, omitidos=omitidos, invalidos=invalidos,
        errores=errores, cambios=cambios,
    )


@router.get("/{afiliado_id}", response_model=AfiliadoOut)
def obtener(
    afiliado_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> AfiliadoOut:
    return AfiliadoOut.model_validate(_get_scoped_or_404(db, cooperativa_id, afiliado_id))


@router.post("", response_model=AfiliadoOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: AfiliadoCreate,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> AfiliadoOut:
    existente = db.execute(
        select(Afiliado).where(Afiliado.cooperativa_id == cooperativa_id, Afiliado.documento == payload.documento)
    ).scalar_one_or_none()
    if existente is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un afiliado con ese documento en esta cooperativa.")

    afiliado = Afiliado(
        cooperativa_id=cooperativa_id,
        documento=payload.documento,
        nombres=payload.nombres,
        apellidos=payload.apellidos,
        correo=payload.correo,
        telefono=payload.telefono,
    )
    db.add(afiliado)
    db.flush()
    audit_service.record(
        db,
        usuario_admin_id=admin.id,
        accion="afiliado_creado",
        tabla_afectada="afiliados",
        registro_id=afiliado.id,
    )
    db.commit()
    db.refresh(afiliado)
    return AfiliadoOut.model_validate(afiliado)


@router.patch("/{afiliado_id}", response_model=AfiliadoOut)
def actualizar(
    afiliado_id: int,
    payload: AfiliadoAdminUpdate,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> AfiliadoOut:
    afiliado = _get_scoped_or_404(db, cooperativa_id, afiliado_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(afiliado, field, value)
    audit_service.record(
        db,
        usuario_admin_id=admin.id,
        accion="afiliado_actualizado",
        tabla_afectada="afiliados",
        registro_id=afiliado.id,
        detalles=data,
    )
    db.commit()
    db.refresh(afiliado)
    return AfiliadoOut.model_validate(afiliado)
