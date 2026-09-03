"""
Back-office administration (`/api/admin`): admin-user management,
cooperativa configuration, and read access to the audit log. Everything
here is scoped to `current_admin.cooperativa_id`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies.auth import require_roles, resolve_cooperativa_scope, resolve_cooperativa_scope_write
from app.models.cooperativa import Cooperativa
from app.models.enums import RolAdmin
from app.models.log_auditoria import LogAuditoria
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.common import Page
from app.schemas.cooperativa import CooperativaCreate, CooperativaOut, CooperativaResumenOut, CooperativaUpdate
from app.schemas.usuario_admin import UsuarioAdminCreate, UsuarioAdminOut, UsuarioAdminUpdate
from app.services import audit_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Cooperativas: SUPER_ADMIN only, for the cross-cooperativa selector/
# filter on the usuarios screen (the only place a bare list of every
# cooperativa is needed — every other screen is scoped to the requesting
# admin's own cooperativa_id and never needs to enumerate the rest). ------
@router.get("/cooperativas", response_model=list[CooperativaResumenOut])
def listar_cooperativas(admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)), db: Session = Depends(get_db)) -> list[CooperativaResumenOut]:
    rows = db.execute(select(Cooperativa).order_by(Cooperativa.nombre)).scalars().all()
    return [CooperativaResumenOut.model_validate(r) for r in rows]


@router.post("/cooperativas", response_model=CooperativaOut, status_code=status.HTTP_201_CREATED)
def crear_cooperativa(
    payload: CooperativaCreate,
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> CooperativaOut:
    existente = db.execute(select(Cooperativa).where(Cooperativa.nit == payload.nit)).scalar_one_or_none()
    if existente is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una cooperativa con ese NIT.")

    cooperativa = Cooperativa(nombre=payload.nombre, nit=payload.nit, estado=payload.estado)
    db.add(cooperativa)
    db.flush()
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="cooperativa_creada", tabla_afectada="cooperativas", registro_id=cooperativa.id,
    )
    db.commit()
    db.refresh(cooperativa)
    return CooperativaOut.model_validate(cooperativa)


# --- Admin users: SUPER_ADMIN only ---------------------------------------
# A SUPER_ADMIN administers every cooperativa, not one in particular — so
# this listing is cross-cooperativa by default (unlike every other
# admin-facing listing in this app, which is always scoped to
# `admin.cooperativa_id`). `?cooperativa_id=` narrows it to one.
def _usuario_out(usuario: UsuarioAdmin) -> UsuarioAdminOut:
    out = UsuarioAdminOut.model_validate(usuario)
    out.cooperativa_nombre = usuario.cooperativa.nombre if usuario.cooperativa is not None else None
    return out


@router.get("/usuarios", response_model=list[UsuarioAdminOut])
def listar_usuarios(
    cooperativa_id: int | None = Query(default=None),
    estado: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> list[UsuarioAdminOut]:
    stmt = select(UsuarioAdmin).outerjoin(Cooperativa, Cooperativa.id == UsuarioAdmin.cooperativa_id)
    if cooperativa_id is not None:
        stmt = stmt.where(UsuarioAdmin.cooperativa_id == cooperativa_id)
    if estado is not None:
        stmt = stmt.where(UsuarioAdmin.estado == estado)
    if q:
        # A single free-text box matches either the usuario's own
        # nombre/correo OR the name of the cooperativa it belongs to —
        # searching "Cooperativa Norte" and searching "Ana" are both
        # legitimate ways to find the same row, so one search box covers
        # both instead of requiring the separate cooperativa dropdown for
        # one and this box for the other.
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            UsuarioAdmin.nombre.ilike(like) | UsuarioAdmin.correo.ilike(like) | Cooperativa.nombre.ilike(like)
        )
    rows = db.execute(stmt.order_by(UsuarioAdmin.nombre)).scalars().all()
    return [_usuario_out(r) for r in rows]


@router.post("/usuarios", response_model=UsuarioAdminOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: UsuarioAdminCreate,
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> UsuarioAdminOut:
    existente = db.execute(select(UsuarioAdmin).where(func.lower(UsuarioAdmin.correo) == payload.correo.lower())).scalar_one_or_none()
    if existente is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo.")

    if payload.cooperativa_id is not None and db.get(Cooperativa, payload.cooperativa_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cooperativa indicada no existe.")

    # The new user's cooperativa comes from the FORM, never from the
    # creating SUPER_ADMIN's own cooperativa_id (which may itself be NULL)
    # — a SUPER_ADMIN explicitly assigns which cooperativa an ADMIN/LECTOR
    # belongs to.
    nuevo = UsuarioAdmin(
        cooperativa_id=payload.cooperativa_id,
        nombre=payload.nombre,
        correo=payload.correo,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
    )
    db.add(nuevo)
    db.flush()
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="usuario_admin_creado", tabla_afectada="usuarios_admin", registro_id=nuevo.id,
        detalles={"rol": payload.rol.value, "cooperativa_id": payload.cooperativa_id},
    )
    db.commit()
    db.refresh(nuevo)
    return _usuario_out(nuevo)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
def actualizar_usuario(
    usuario_id: int,
    payload: UsuarioAdminUpdate,
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> UsuarioAdminOut:
    # No cooperativa scoping on the lookup itself — a SUPER_ADMIN manages
    # usuarios_admin across every cooperativa.
    usuario = db.get(UsuarioAdmin, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    data = payload.model_dump(exclude_unset=True)

    if "cooperativa_id" in data and data["cooperativa_id"] is not None and db.get(Cooperativa, data["cooperativa_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cooperativa indicada no existe.")

    # Re-check the required-unless-SUPER_ADMIN rule against the EFFECTIVE
    # values (existing row's values merged with whatever this partial
    # update actually changes) — a request could change only `rol` (e.g.
    # LECTOR -> ADMIN, still needs a cooperativa) or only `cooperativa_id`
    # (e.g. clearing it), and either alone must still leave the row valid.
    rol_efectivo = data.get("rol", usuario.rol)
    cooperativa_id_efectivo = data.get("cooperativa_id", usuario.cooperativa_id)
    if rol_efectivo != RolAdmin.SUPER_ADMIN and cooperativa_id_efectivo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="cooperativa_id es obligatorio para los roles ADMIN y LECTOR.")

    for field, value in data.items():
        setattr(usuario, field, value)

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="usuario_admin_actualizado", tabla_afectada="usuarios_admin", registro_id=usuario.id, detalles=data,
    )
    db.commit()
    db.refresh(usuario)
    return _usuario_out(usuario)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def eliminar_usuario(
    usuario_id: int,
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    """Real, permanent DELETE from `usuarios_admin` — not the `estado`
    soft-disable `PATCH` above (that endpoint is unchanged and still the
    right tool for "revoke access but keep the record"). The only FK
    pointing at this table is `logs_auditoria.usuario_admin_id`, which is
    nullable precisely so a deleted admin's PAST actions can stay in the
    audit trail: those rows are detached (set to NULL) rather than
    deleted, then the usuarios_admin row itself is removed for real."""
    usuario = db.get(UsuarioAdmin, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    if usuario.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes eliminar tu propio usuario.")

    nombre_eliminado = usuario.nombre
    correo_eliminado = usuario.correo

    db.execute(
        update(LogAuditoria).where(LogAuditoria.usuario_admin_id == usuario_id).values(usuario_admin_id=None)
    )
    db.delete(usuario)
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="usuario_admin_eliminado", tabla_afectada="usuarios_admin", registro_id=usuario_id,
        detalles={"nombre": nombre_eliminado, "correo": correo_eliminado},
    )
    db.commit()


# --- Cooperativa configuration --------------------------------------------
# For ADMIN/LECTOR this is always their own cooperativa. For SUPER_ADMIN
# (who has no cooperativa of its own) it is whichever cooperativa is
# currently selected via `?cooperativa_id=` — same rule as every other
# module (see resolve_cooperativa_scope).
@router.get("/cooperativa", response_model=CooperativaOut)
def obtener_cooperativa(
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> CooperativaOut:
    cooperativa = db.get(Cooperativa, cooperativa_id)
    return CooperativaOut.model_validate(cooperativa)


@router.patch("/cooperativa", response_model=CooperativaOut)
def actualizar_cooperativa(
    payload: CooperativaUpdate,
    admin: UsuarioAdmin = Depends(require_roles(RolAdmin.SUPER_ADMIN, RolAdmin.ADMIN)),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CooperativaOut:
    cooperativa = db.get(Cooperativa, cooperativa_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(cooperativa, field, value)

    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="cooperativa_actualizada", tabla_afectada="cooperativas", registro_id=cooperativa.id, detalles=data,
    )
    db.commit()
    db.refresh(cooperativa)
    return CooperativaOut.model_validate(cooperativa)


# --- Audit log: read-only for every admin role, including LECTOR --------
@router.get("/logs", response_model=Page[dict])
def listar_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[dict]:
    stmt = (
        select(LogAuditoria)
        .join(UsuarioAdmin, UsuarioAdmin.id == LogAuditoria.usuario_admin_id)
        .where(UsuarioAdmin.cooperativa_id == cooperativa_id)
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(LogAuditoria.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    items = [
        {
            "id": r.id,
            "usuario_admin_id": r.usuario_admin_id,
            "accion": r.accion,
            "tabla_afectada": r.tabla_afectada,
            "registro_id": r.registro_id,
            "detalles": r.detalles,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)
