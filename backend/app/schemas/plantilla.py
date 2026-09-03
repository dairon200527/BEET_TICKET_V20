from pydantic import BaseModel


class PlantillaOut(BaseModel):
    """The real, unmodified `plantillas` columns — no `clave` field here."""

    id: int
    convenio_id: int
    nombre: str
    version: int
    storage_path: str
    estado: bool

    model_config = {"from_attributes": True}


class PlantillaCatalogoOut(BaseModel):
    """One of the 4 fixed brand designs in
    app.services.plantillas_catalogo.CATALOGO — pure code, never backed
    by a database row (there is no column anywhere linking a convenio to
    one of these yet; see that module's docstring). `clave` is simply
    the dict key."""

    clave: str
    nombre: str


class PlantillaDisponibleOut(BaseModel):
    """One row of the unified list `GET /api/plantillas/disponibles`
    shows for a single convenio — a catalog design AND a real per-convenio
    HTML plantilla look the same here, so the "Seleccionar plantilla"
    screen can list and act on both without caring which is which.

    `tipo` is `"catalogo"` (identified by `clave`, `id` is `None`) or
    `"personalizada"` (identified by `id`, `clave` is `None`). `en_uso` marks
    the SINGLE item — across both types — `pdf_service.generar_ticket`
    would actually pick for this convenio right now (catalog wins over
    any active legacy row; never both at once)."""

    tipo: str
    id: int | None = None
    clave: str | None = None
    nombre: str
    version: int | None = None
    en_uso: bool
