"""
Convenios (`/api/convenios`) — admin CRUD scoped via
`resolve_cooperativa_scope`/`_write` (see app/dependencies/auth.py), plus
the affiliate-facing read-only catalog (`/catalogo`).

`/catalogo` is registered BEFORE `/{convenio_id}` — FastAPI matches routes
in registration order, and a dynamic `/{convenio_id}` registered first
would swallow `/catalogo` as a (numeric-parse-failing) id instead of
matching the static route (same rule as afiliados.py / cupos.py).
"""
from __future__ import annotations

import mimetypes
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.dependencies.auth import (
    get_current_affiliate,
    require_write_access,
    resolve_cooperativa_scope,
    resolve_cooperativa_scope_write,
)
from app.models.afiliado import Afiliado
from app.models.convenio import Convenio
from app.models.enums import EstadoUnidadInventario
from app.models.unidad_inventario import UnidadInventario
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.common import CargaMasivaResultado, Message, Page
from app.schemas.convenio import ConvenioCreate, ConvenioOut, ConvenioUpdate
from app.services import audit_service, pdf_service, plantillas_catalogo, storage_service
from app.services.xlsx_export import XLSX_MEDIA_TYPE, build_xlsx, dated_filename
from app.utils.bulk_upload import parse_bool, parse_rows, require_columns, summarize_validation_error
from app.utils.file_validation import ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES, validate_size, validate_upload
from app.utils.query_params import clamp_pagination, resolve_sort_column

router = APIRouter(prefix="/api/convenios", tags=["convenios"])

_SORTABLE_FIELDS = {"nombre", "fecha_inicio", "fecha_fin", "precio_beet"}


def _get_scoped_or_404(db: Session, cooperativa_id: int, convenio_id: int) -> Convenio:
    convenio = db.get(Convenio, convenio_id)
    if convenio is None or convenio.cooperativa_id != cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convenio no encontrado.")
    return convenio


@router.get("/catalogo", response_model=list[ConvenioOut])
def catalogo(afiliado: Afiliado = Depends(get_current_affiliate), db: Session = Depends(get_db)) -> list[ConvenioOut]:
    """The exact eligibility rule for a convenio to appear in an
    afiliado's catalog — a convenio appears IF AND ONLY IF ALL of:
      1. `convenio.cooperativa_id == afiliado.cooperativa_id` — the
         afiliado's cooperativa is ALWAYS derived from the authenticated
         JWT (`get_current_affiliate`), never a client-supplied
         parameter. Covered by a dedicated isolation test
         (test_catalogo_nunca_mezcla_convenios_de_otra_cooperativa in
         tests/test_catalogo_afiliado.py) treated as a security control,
         not just a business rule — no other cooperativa's convenio must
         EVER be reachable here, regardless of its own estado/vigencia/
         stock.
      2. `convenio.estado is True`.
      3. In vigencia: `fecha_inicio <= hoy <= fecha_fin` (or `fecha_fin`
         is NULL — no expiry).
      4. At least 1 `unidades_inventario` row with estado='disponible'
         for the convenio — a convenio that sold out must disappear
         entirely, not just show a "sin inventario" label, until
         restocked.

    Condition 4 does NOT apply to the admin-facing listing
    (`GET /convenios`), which must keep showing every convenio regardless
    of stock so the admin can manage/restock the ones sitting at 0."""
    hoy = date.today()
    rows = db.execute(
        select(Convenio, func.count(UnidadInventario.id))
        .join(
            UnidadInventario,
            (UnidadInventario.convenio_id == Convenio.id)
            & (UnidadInventario.estado == EstadoUnidadInventario.DISPONIBLE),
        )
        .where(
            Convenio.cooperativa_id == afiliado.cooperativa_id,
            Convenio.estado.is_(True),
            Convenio.fecha_inicio <= hoy,
            (Convenio.fecha_fin.is_(None)) | (Convenio.fecha_fin >= hoy),
        )
        .options(selectinload(Convenio.plantillas))
        .group_by(Convenio.id)
        .having(func.count(UnidadInventario.id) > 0)
    ).all()
    resultado = []
    for convenio, disponibles in rows:
        out = ConvenioOut.model_validate(convenio)
        out.unidades_disponibles = disponibles
        out.imagen_marca_url = _imagen_marca_url_o_none(convenio)
        resultado.append(out)
    return resultado


def _imagen_marca_url_o_none(convenio: Convenio) -> str | None:
    """The relative API path for this convenio's branding image, or
    `None` if there's genuinely nothing to show — never a raw storage
    key, and never an error: a convenio with no logo yet is a completely
    normal, expected state. Prefers the SELECTED catalog design's real
    brand logo (a static asset, always present); falls back to any
    legacy per-convenio plantilla's uploaded logo."""
    if convenio.plantilla_catalogo_clave and plantillas_catalogo.existe(convenio.plantilla_catalogo_clave):
        return f"/api/convenios/{convenio.id}/imagen-marca"
    plantilla = pdf_service.plantilla_activa(convenio)
    if plantilla is None:
        return None
    if pdf_service.logo_storage_path_de_plantilla(plantilla) is None:
        return None
    return f"/api/convenios/{convenio.id}/imagen-marca"


def _plantilla_en_uso_nombre(convenio: Convenio) -> str | None:
    """The `nombre` of whichever plantilla `pdf_service.generar_ticket`
    would actually pick for this convenio right now — same tier order
    (catalog clave, then any active legacy row), so this label can never
    disagree with what a real ticket actually renders. `None` means
    genuinely nothing is selected — the frontend shows "Sin plantilla
    seleccionada" rather than silently guessing."""
    if convenio.plantilla_catalogo_clave and plantillas_catalogo.existe(convenio.plantilla_catalogo_clave):
        return plantillas_catalogo.nombre_de(convenio.plantilla_catalogo_clave)
    plantilla = pdf_service.plantilla_activa(convenio)
    return plantilla.nombre if plantilla is not None else None


@router.get("/{convenio_id}/imagen-marca")
def imagen_marca(
    convenio_id: int,
    afiliado: Afiliado = Depends(get_current_affiliate),
    db: Session = Depends(get_db),
) -> Response:
    """The same branding image already used atop the convenio's ticket PDF
    — streamed here so the catalog card (and the benefit detail page,
    which reuses the same catalog data) can show it too. Scoped exactly
    like `/catalogo`: a convenio belonging to another cooperativa is
    indistinguishable from one that doesn't exist — convenio_id is never
    trusted on its own, only after re-verifying it against the
    authenticated afiliado's own cooperativa_id.

    Resolution order matches `pdf_service.generar_ticket`: the SELECTED
    catalog design's real logo (a static asset shipped with the code)
    first, then any legacy per-convenio plantilla's uploaded logo."""
    convenio = db.get(Convenio, convenio_id)
    if convenio is None or convenio.cooperativa_id != afiliado.cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convenio no encontrado.")

    if convenio.plantilla_catalogo_clave:
        logo = plantillas_catalogo.logo_bytes(convenio.plantilla_catalogo_clave)
        if logo is not None:
            return Response(content=logo, media_type="image/png")

    plantilla = pdf_service.plantilla_activa(convenio)
    logo_path = pdf_service.logo_storage_path_de_plantilla(plantilla) if plantilla is not None else None
    if logo_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este convenio no tiene imagen de marca.")

    contenido = storage_service.download_bytes(logo_path)
    if contenido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este convenio no tiene imagen de marca.")

    content_type, _ = mimetypes.guess_type(logo_path)
    return Response(content=contenido, media_type=content_type or "application/octet-stream")


@router.post("/carga-masiva", response_model=CargaMasivaResultado)
async def carga_masiva(
    file: UploadFile = File(...),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> CargaMasivaResultado:
    """Bulk convenio load from CSV/XLSX — creates a new convenio, or
    UPDATES an existing one, matched by exact `nombre` within the
    uploading admin's own cooperativa (the real schema has no other
    natural business key for a convenio besides its surrogate id — see
    ../../README.md for this decision). Expected columns: nombre,
    descripcion (optional), precio_publico, precio_beet, fecha_inicio
    (YYYY-MM-DD), fecha_fin (optional), estado (optional, default true;
    "false"/"0"/"no"/"inactivo" all count as false). Same
    validate-per-row / never-all-or-nothing pattern as
    `POST /api/afiliados/carga-masiva`."""
    validate_upload(file, ALLOWED_INVENTORY_EXTENSIONS, ALLOWED_INVENTORY_MIME_TYPES)
    content = await file.read()
    validate_size(len(content))
    headers, rows = parse_rows(file.filename or "", content)
    require_columns(headers, ["nombre", "precio_publico", "precio_beet", "fecha_inicio"])

    creados = actualizados = omitidos = invalidos = 0
    errores: list[str] = []
    cambios: list[str] = []
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            data = ConvenioCreate(
                nombre=row.get("nombre", ""),
                descripcion=row.get("descripcion") or None,
                precio_publico=row.get("precio_publico") or "0",
                precio_beet=row.get("precio_beet") or "0",
                fecha_inicio=row.get("fecha_inicio") or "",
                fecha_fin=row.get("fecha_fin") or None,
                estado=parse_bool(row.get("estado")),
            )
        except ValidationError as exc:
            invalidos += 1
            errores.append(f"Fila {idx}: {summarize_validation_error(exc)}")
            continue
        except ValueError as exc:
            invalidos += 1
            errores.append(f"Fila {idx}: {exc}")
            continue

        existente = db.execute(
            select(Convenio).where(Convenio.cooperativa_id == cooperativa_id, Convenio.nombre == data.nombre)
        ).scalar_one_or_none()
        if existente is not None:
            # Field-by-field, not a blind `data.model_dump()` overwrite —
            # that used to reset `descripcion`/`fecha_fin` to blank and
            # `estado` to Activo on ANY re-upload where the row left those
            # optional cells empty, even though the file's intent for a
            # blank optional cell on an UPDATE is "leave it as it is", not
            # "clear it" (same convention already used for `estado` in
            # afiliados carga-masiva). Required columns (precio_publico,
            # precio_beet, fecha_inicio) always carry a real value, so
            # they're always compared straight.
            fila_cambios: list[str] = []

            def _set(field: str, nuevo, tocar: bool = True):
                if not tocar:
                    return
                actual = getattr(existente, field)
                if actual != nuevo:
                    fila_cambios.append(f"Fila {idx}: {field} cambió de {actual!r} a {nuevo!r}.")
                    setattr(existente, field, nuevo)

            _set("precio_publico", data.precio_publico)
            _set("precio_beet", data.precio_beet)
            _set("fecha_inicio", data.fecha_inicio)
            _set("descripcion", data.descripcion, tocar=bool(row.get("descripcion")))
            _set("fecha_fin", data.fecha_fin, tocar=bool(row.get("fecha_fin")))
            _set("estado", data.estado, tocar=row.get("estado") is not None and str(row.get("estado")).strip() != "")

            if fila_cambios:
                cambios.extend(fila_cambios)
                actualizados += 1
            else:
                omitidos += 1
        else:
            db.add(Convenio(cooperativa_id=cooperativa_id, **data.model_dump()))
            creados += 1

    audit_service.record(
        db,
        usuario_admin_id=admin.id,
        accion="convenios_carga_masiva",
        tabla_afectada="convenios",
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


@router.get("", response_model=Page[ConvenioOut])
def listar(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    estado: bool | None = Query(default=None),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Page[ConvenioOut]:
    page, page_size = clamp_pagination(page, page_size)
    stmt = select(Convenio).where(Convenio.cooperativa_id == cooperativa_id)
    if estado is not None:
        stmt = stmt.where(Convenio.estado == estado)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = resolve_sort_column(Convenio, sort_by, _SORTABLE_FIELDS, default="nombre")
    rows = db.execute(stmt.order_by(column).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return Page(items=[ConvenioOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/exportar")
def exportar(
    estado: bool | None = Query(default=None),
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    """Every convenio of the effective cooperativa as a real .xlsx —
    same resolve_cooperativa_scope pattern as every other export in this
    app (rendimiento-convenios/exportar, afiliados/exportar). Unlike the
    affiliate-facing catalog, this lists ALL convenios regardless of
    stock — the admin needs to see (and export) the ones sitting at 0
    too, not just the ones currently sellable."""
    stmt = select(Convenio).where(Convenio.cooperativa_id == cooperativa_id)
    if estado is not None:
        stmt = stmt.where(Convenio.estado == estado)
    convenios = db.execute(stmt.order_by(Convenio.nombre)).scalars().all()

    disponibles_por_convenio = dict(
        db.execute(
            select(UnidadInventario.convenio_id, func.count())
            .where(
                UnidadInventario.convenio_id.in_([c.id for c in convenios]),
                UnidadInventario.estado == EstadoUnidadInventario.DISPONIBLE,
            )
            .group_by(UnidadInventario.convenio_id)
        ).all()
    )

    headers = ["Nombre", "Descripción", "Precio publico", "Precio beet", "Fecha inicio", "Fecha fin", "Estado", "Unidades disponibles"]
    rows = [
        [
            c.nombre,
            c.descripcion or "",
            float(c.precio_publico),
            float(c.precio_beet),
            c.fecha_inicio.isoformat(),
            c.fecha_fin.isoformat() if c.fecha_fin else "",
            "Activo" if c.estado else "Inactivo",
            disponibles_por_convenio.get(c.id, 0),
        ]
        for c in convenios
    ]
    contenido = build_xlsx("Convenios", headers, rows)
    nombre_archivo = dated_filename("convenios")
    return Response(
        content=contenido,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@router.get("/{convenio_id}", response_model=ConvenioOut)
def obtener(
    convenio_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> ConvenioOut:
    convenio = _get_scoped_or_404(db, cooperativa_id, convenio_id)
    out = ConvenioOut.model_validate(convenio)
    out.plantilla_en_uso = _plantilla_en_uso_nombre(convenio)
    return out


@router.post("", response_model=ConvenioOut, status_code=status.HTTP_201_CREATED)
def crear(
    payload: ConvenioCreate,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> ConvenioOut:
    convenio = Convenio(cooperativa_id=cooperativa_id, **payload.model_dump())
    db.add(convenio)
    db.flush()
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="convenio_creado", tabla_afectada="convenios", registro_id=convenio.id,
    )
    db.commit()
    db.refresh(convenio)
    return ConvenioOut.model_validate(convenio)


@router.patch("/{convenio_id}", response_model=ConvenioOut)
def actualizar(
    convenio_id: int,
    payload: ConvenioUpdate,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> ConvenioOut:
    convenio = _get_scoped_or_404(db, cooperativa_id, convenio_id)
    data = payload.model_dump(exclude_unset=True)
    if "precio_beet" in data or "precio_publico" in data:
        nuevo_publico = data.get("precio_publico", convenio.precio_publico)
        nuevo_beet = data.get("precio_beet", convenio.precio_beet)
        if nuevo_beet > nuevo_publico:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio BEET no puede ser mayor al precio público.")
    if "plantilla_catalogo_clave" in data and data["plantilla_catalogo_clave"] is not None:
        if not plantillas_catalogo.existe(data["plantilla_catalogo_clave"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La plantilla seleccionada no existe.")
    for field, value in data.items():
        setattr(convenio, field, value)
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="convenio_actualizado", tabla_afectada="convenios", registro_id=convenio.id, detalles=data,
    )
    db.commit()
    db.refresh(convenio)
    out = ConvenioOut.model_validate(convenio)
    out.plantilla_en_uso = _plantilla_en_uso_nombre(convenio)
    return out
