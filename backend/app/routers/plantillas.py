"""
Plantillas (`/api/plantillas`) — three things live under this prefix:

1. `GET /catalogo` and `GET /catalogo/{clave}/preview` — the 4 fixed,
   code-owned ticket designs (see app/services/plantillas_catalogo.py),
   listed and previewed read-only, straight from code — no database
   involved at all.

2. `GET /disponibles?convenio_id=X` — the UNIFIED list the "Seleccionar
   plantilla" screen renders for one convenio: the 4 catalog designs
   PLUS every real per-convenio plantilla ever created for it (via
   `POST ""` below), each tagged `en_uso` if it's the one
   `pdf_service.generar_ticket` would actually pick right now. Selecting
   either kind — `PATCH /api/convenios/{id}` for a catalog design,
   `PATCH /{plantilla_id}` (`{"estado": true}`) for a real one — always
   deactivates every OTHER option for that convenio first, so at most
   one is ever "in effect" (see `_plantilla_en_uso_nombre` in
   routers/convenios.py, same tier order everywhere).

3. `POST /preview` and `POST ""` — create a real, per-convenio plantilla
   by pasting raw HTML/Jinja2 source directly (no visual editor, no
   manual positioning, no logo upload, no content-form fields — see
   services/template_engine.py's `validar_y_renderizar`, which both
   endpoints share so "preview" and "what actually gets saved" can never
   disagree). `/preview` never persists anything; `POST ""` does, as a
   new versioned row in the real `plantillas` table
   (`plantillas.convenio_id`), immediately becoming the one in effect
   for that convenio (every sibling row is deactivated at the same
   time).

4. `GET ""`, `GET /{id}`, `PATCH /{id}`, `GET /{id}/preview`,
   `GET /{id}/config`, `GET /{id}/imagenes/{key}` — the real per-convenio
   `plantillas` rows: list/read/preview freely, but `PATCH` (activate or
   deactivate) requires write access.

PERMISSIONS: listing/reading/previewing is available to any authenticated
admin (including LECTOR); creating and toggling (`POST /preview`,
`POST ""`, `PATCH /{id}`) require write access (ADMIN/SUPER_ADMIN).
"""
from __future__ import annotations

import json
import mimetypes

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user, require_write_access, resolve_cooperativa_scope, resolve_cooperativa_scope_write
from app.models.convenio import Convenio
from app.models.plantilla import Plantilla
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.plantilla import PlantillaCatalogoOut, PlantillaDisponibleOut, PlantillaOut
from app.services import audit_service, plantillas_catalogo, storage_service, template_engine

router = APIRouter(prefix="/api/plantillas", tags=["plantillas"])


def _get_scoped_plantilla_or_404(db: Session, cooperativa_id: int, plantilla_id: int) -> Plantilla:
    plantilla = db.get(Plantilla, plantilla_id)
    if plantilla is None or plantilla.convenio.cooperativa_id != cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada.")
    return plantilla


def _get_scoped_convenio_or_404(db: Session, cooperativa_id: int, convenio_id: int) -> Convenio:
    convenio = db.get(Convenio, convenio_id)
    if convenio is None or convenio.cooperativa_id != cooperativa_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convenio no encontrado.")
    return convenio


def _desactivar_hermanas(db: Session, convenio_id: int) -> None:
    """Every OTHER real plantilla for this convenio stops being 'in
    effect' — called whenever one is created or explicitly activated, so
    at most one is ever active at a time (mirrors how a catalog
    selection is a single value, never a set)."""
    db.execute(update(Plantilla).where(Plantilla.convenio_id == convenio_id).values(estado=False))


# --- Catalog: the 4 fixed designs — list + real-PDF preview ---------------

@router.get("/catalogo", response_model=list[PlantillaCatalogoOut])
def listar_catalogo(admin=Depends(get_current_admin_user)) -> list[PlantillaCatalogoOut]:
    """The 4 fixed designs, straight from code — no database read at
    all. Global (not cooperativa-scoped: every cooperativa shares the
    same 4 designs), so any authenticated admin can list them."""
    return [
        PlantillaCatalogoOut(clave=clave, nombre=entrada["nombre"])
        for clave, entrada in plantillas_catalogo.CATALOGO.items()
    ]


@router.get("/catalogo/{clave}/preview")
def previsualizar_catalogo(
    clave: str,
    admin=Depends(get_current_admin_user),
) -> Response:
    """A real PDF of the design, rendered with the SAME fixture data (a
    test afiliado, a real QR/barcode of a placeholder code) any other
    preview in this app has used — via the exact function
    `pdf_service.generar_ticket` calls for a real purchase, so this can
    never drift from what a real ticket looks like. Nothing is persisted."""
    if not plantillas_catalogo.existe(clave):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada.")
    contexto = template_engine.contexto_preview(
        convenio_nombre=plantillas_catalogo.nombre_de(clave), convenio_descripcion=None, n_unidades=4,
    )
    pdf_bytes = plantillas_catalogo.generar_pdf(clave, contexto)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="preview-plantilla.pdf"'})


# --- Unified list for one convenio: catalog designs + real plantillas -----

@router.get("/disponibles", response_model=list[PlantillaDisponibleOut])
def listar_disponibles(
    convenio_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> list[PlantillaDisponibleOut]:
    convenio = _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    catalogo_en_uso = bool(convenio.plantilla_catalogo_clave and plantillas_catalogo.existe(convenio.plantilla_catalogo_clave))

    resultado = [
        PlantillaDisponibleOut(
            tipo="catalogo", clave=clave, nombre=entrada["nombre"],
            en_uso=(catalogo_en_uso and convenio.plantilla_catalogo_clave == clave),
        )
        for clave, entrada in plantillas_catalogo.CATALOGO.items()
    ]

    filas = db.execute(
        select(Plantilla).where(Plantilla.convenio_id == convenio_id).order_by(Plantilla.version.desc())
    ).scalars().all()
    resultado.extend(
        PlantillaDisponibleOut(
            tipo="personalizada", id=fila.id, nombre=fila.nombre, version=fila.version,
            en_uso=(not catalogo_en_uso and fila.estado),
        )
        for fila in filas
    )
    return resultado


# --- Create a plantilla from raw HTML/Jinja2 source (no visual editor) ----

@router.post("/preview")
async def previsualizar_html(
    convenio_id: int = Form(...),
    html: str = Form(...),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> Response:
    """Dry-runs the EXACT same validation + WeasyPrint render `POST ""`
    below would persist — real HTML/Jinja2 syntax, every required
    variable present (`convenio`, `items`, `afiliado`, `transaccion_id`,
    `fecha_emision`, `fecha_vencimiento`), and an actual successful PDF
    render with fixture data — so a broken template is caught here,
    never on a real purchase. Nothing is ever saved by this endpoint."""
    convenio = _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    contexto = template_engine.contexto_preview(convenio_nombre=convenio.nombre, convenio_descripcion=convenio.descripcion, n_unidades=1)
    try:
        pdf_bytes = template_engine.validar_y_renderizar(html, contexto)
    except template_engine.PlantillaInvalida as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="preview-plantilla.pdf"'})


@router.post("", response_model=PlantillaOut, status_code=status.HTTP_201_CREATED)
async def crear(
    convenio_id: int = Form(...),
    html: str = Form(...),
    nombre: str | None = Form(None),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> PlantillaOut:
    """Creates a new versioned row in the real `plantillas` table
    directly from pasted HTML/Jinja2 source — no visual editor, no
    manual positioning. Goes through the EXACT same validation as
    `POST /preview` above before anything is persisted (never a broken
    template saved only to fail on the first real purchase).

    Becomes THE plantilla in effect for this convenio immediately: every
    other real plantilla for this convenio is deactivated in the same
    transaction (`_desactivar_hermanas`), so exactly one is ever active.
    Does NOT touch `Convenio.plantilla_catalogo_clave` — if a catalog
    design is selected, it still wins at ticket time (see
    `pdf_service.generar_ticket`'s tier order); clear it from
    "Seleccionar plantilla" for this one to actually take effect."""
    convenio = _get_scoped_convenio_or_404(db, cooperativa_id, convenio_id)
    contexto = template_engine.contexto_preview(convenio_nombre=convenio.nombre, convenio_descripcion=convenio.descripcion, n_unidades=1)
    try:
        template_engine.validar_y_renderizar(html, contexto)
    except template_engine.PlantillaInvalida as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    config = {"html": html}
    config_key = storage_service.generate_object_key("plantillas", cooperativa_id, "convenio", convenio_id, ".json")
    storage_path = storage_service.upload_bytes(config_key, json.dumps(config).encode("utf-8"), "application/json")

    siguiente_version = (
        db.execute(
            select(Plantilla.version).where(Plantilla.convenio_id == convenio_id).order_by(Plantilla.version.desc())
        ).scalars().first() or 0
    ) + 1
    _desactivar_hermanas(db, convenio_id)
    plantilla = Plantilla(
        convenio_id=convenio_id, nombre=nombre or convenio.nombre, version=siguiente_version,
        storage_path=storage_path, estado=True,
    )
    db.add(plantilla)
    db.flush()
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="plantilla_html_creada", tabla_afectada="plantillas", registro_id=plantilla.id,
        detalles={"convenio_id": convenio_id, "version": siguiente_version},
    )
    db.commit()
    db.refresh(plantilla)
    return PlantillaOut.model_validate(plantilla)


# --- Real per-convenio plantillas: list/read/preview/activate-deactivate --

@router.get("", response_model=list[PlantillaOut])
def listar(
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> list[PlantillaOut]:
    rows = (
        db.execute(select(Plantilla).join(Convenio).where(Convenio.cooperativa_id == cooperativa_id))
        .scalars()
        .all()
    )
    return [PlantillaOut.model_validate(r) for r in rows]


@router.get("/{plantilla_id}", response_model=PlantillaOut)
def obtener(
    plantilla_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> PlantillaOut:
    return PlantillaOut.model_validate(_get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id))


@router.patch("/{plantilla_id}", response_model=PlantillaOut)
def actualizar_estado(
    plantilla_id: int,
    estado: bool = Body(..., embed=True),
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> PlantillaOut:
    """Activating (`estado: true`) makes this THE plantilla in effect for
    its convenio: every sibling real plantilla is deactivated, and any
    catalog selection is cleared (it would otherwise still win). Called
    from "Seleccionar plantilla" to (re)select a previously-created
    plantilla, or from a "Dejar de usar" button to deactivate the one
    currently in effect (`estado: false`, nothing else touched)."""
    plantilla = _get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id)
    if estado:
        _desactivar_hermanas(db, plantilla.convenio_id)
        plantilla.estado = True
        plantilla.convenio.plantilla_catalogo_clave = None
    else:
        plantilla.estado = False
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="plantilla_estado_actualizado", tabla_afectada="plantillas", registro_id=plantilla.id,
        detalles={"estado": estado},
    )
    db.commit()
    db.refresh(plantilla)
    return PlantillaOut.model_validate(plantilla)


@router.delete("/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def eliminar(
    plantilla_id: int,
    admin: UsuarioAdmin = Depends(require_write_access),
    cooperativa_id: int = Depends(resolve_cooperativa_scope_write),
    db: Session = Depends(get_db),
) -> None:
    """Permanently removes a real per-convenio plantilla — never a
    catalog design (those aren't rows to begin with, so they're never
    reachable through this id-based endpoint). If this happens to be the
    one currently in effect, the convenio simply falls back to the next
    tier (any OTHER active plantilla, then the generic ticket) on the
    very next ticket — nothing else needs updating, and the item just
    disappears from `GET /disponibles` since the row is gone."""
    plantilla = _get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id)
    storage_service.delete_object(plantilla.storage_path)
    audit_service.record(
        db, usuario_admin_id=admin.id,
        accion="plantilla_eliminada", tabla_afectada="plantillas", registro_id=plantilla.id,
        detalles={"convenio_id": plantilla.convenio_id, "version": plantilla.version},
    )
    db.delete(plantilla)
    db.commit()


@router.get("/{plantilla_id}/preview")
def previsualizar_por_id(
    plantilla_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    """Same real-PDF-with-fixture-data preview as `POST /preview`, for a
    plantilla that already exists — used by "Ver muestra" on an item in
    the unified `/disponibles` list. Only plantillas created via
    `POST ""` above (a bare `{"html": ...}` config) can be previewed this
    way; any other legacy format is a 400, never a guess."""
    plantilla = _get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id)
    contenido = storage_service.download_bytes(plantilla.storage_path)
    config = None
    if contenido is not None:
        try:
            config = json.loads(contenido.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            config = None
    if not isinstance(config, dict) or "html" not in config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Esta plantilla no se puede previsualizar.")
    contexto = template_engine.contexto_preview(
        convenio_nombre=plantilla.convenio.nombre, convenio_descripcion=plantilla.convenio.descripcion, n_unidades=1,
    )
    pdf_bytes = template_engine.generar_pdf_desde_plantilla(config["html"], contexto)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="preview-plantilla.pdf"'})


@router.get("/{plantilla_id}/config")
def obtener_config(
    plantilla_id: int,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> dict:
    """Legacy inspection endpoint — returns the content fields (never the
    raw storage key) of an old per-convenio plantilla. Legacy formats
    this doesn't recognize return an empty dict."""
    plantilla = _get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id)
    contenido = storage_service.download_bytes(plantilla.storage_path)
    if contenido is None:
        return {}
    try:
        config = json.loads(contenido.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if config.get("type") == "layout":
        return {
            "type": "layout",
            "layout": config.get("layout"),
            "imagenes_keys": list((config.get("imagenes") or {}).keys()),
        }
    if "template_key" not in config:
        return {}
    return {campo: config.get(campo, "") for campo in template_engine.CAMPOS_CONTENIDO_OPCIONALES} | {
        "template_key": config["template_key"],
        "tiene_logo": bool(config.get("logo_storage_path")),
        "tiene_logo_cooperativa": bool(config.get("logo_cooperativa_storage_path")),
    }


@router.get("/{plantilla_id}/imagenes/{key}")
def obtener_imagen_layout(
    plantilla_id: int,
    key: str,
    cooperativa_id: int = Depends(resolve_cooperativa_scope),
    db: Session = Depends(get_db),
) -> Response:
    """Streams one background/logo/graphic image belonging to a LEGACY
    per-convenio layout plantilla — scoped exactly like every other
    plantilla endpoint here; a plantilla from another cooperativa is a
    404, never distinguishable from "doesn't exist"."""
    plantilla = _get_scoped_plantilla_or_404(db, cooperativa_id, plantilla_id)
    contenido = storage_service.download_bytes(plantilla.storage_path)
    if contenido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    try:
        config = json.loads(contenido.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    storage_path = (config.get("imagenes") or {}).get(key)
    if not storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    imagen_bytes = storage_service.download_bytes(storage_path)
    if imagen_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    content_type, _ = mimetypes.guess_type(storage_path)
    return Response(content=imagen_bytes, media_type=content_type or "application/octet-stream")
