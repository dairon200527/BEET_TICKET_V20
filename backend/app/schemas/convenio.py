from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ConvenioBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    descripcion: str | None = None
    precio_publico: Decimal = Field(ge=0)
    precio_beet: Decimal = Field(ge=0)
    fecha_inicio: date
    fecha_fin: date | None = None
    estado: bool = True

    @field_validator("precio_beet")
    @classmethod
    def beet_no_mayor_que_publico(cls, v: Decimal, info):
        publico = info.data.get("precio_publico")
        if publico is not None and v > publico:
            raise ValueError("El precio BEET no puede ser mayor al precio público.")
        return v

    @field_validator("fecha_fin")
    @classmethod
    def fecha_fin_valida(cls, v: date | None, info):
        inicio = info.data.get("fecha_inicio")
        if v is not None and inicio is not None and v < inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la fecha de inicio.")
        return v


class ConvenioCreate(ConvenioBase):
    pass


class ConvenioUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = None
    precio_publico: Decimal | None = Field(default=None, ge=0)
    precio_beet: Decimal | None = Field(default=None, ge=0)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    estado: bool | None = None

    # One of app.services.plantillas_catalogo.CATALOGO's keys, or `None`
    # to clear the selection — validated in routers/convenios.py's
    # `actualizar()` against that dict, never against a database table.
    plantilla_catalogo_clave: str | None = None


class ConvenioOut(BaseModel):
    id: int
    cooperativa_id: int
    nombre: str
    descripcion: str | None
    precio_publico: Decimal
    precio_beet: Decimal
    fecha_inicio: date
    fecha_fin: date | None
    estado: bool
    plantilla_catalogo_clave: str | None

    # The `nombre` of whichever plantilla (catalog design OR active
    # per-convenio HTML plantilla) `pdf_service.generar_ticket` would
    # actually use for this convenio RIGHT NOW — `None` when there's
    # genuinely no selection at all, in which case the frontend shows
    # "Sin plantilla seleccionada". Computed by routers/convenios.py, not
    # a real column — never populated by plain `model_validate`.
    plantilla_en_uso: str | None = None

    # Only populated by the affiliate-facing catalog (GET /convenios/catalogo)
    # — every convenio returned there already has at least 1 unit, since
    # that endpoint filters out zero-inventory convenios entirely. Left
    # `None` on the admin listing/detail, which must keep showing every
    # convenio (with or without stock) so the admin can restock it.
    unidades_disponibles: int | None = None

    # A relative API path (never a raw storage key/bucket path) to
    # GET /api/convenios/{id}/imagen-marca. Resolves the convenio's
    # SELECTED catalog design's real brand logo first (see
    # routers/convenios.py's `_imagen_marca_url_o_none`), then falls back
    # to any legacy per-convenio plantilla's uploaded logo
    # (services/pdf_service.plantilla_activa). `None` only when neither
    # exists — the frontend shows its generic placeholder in that case,
    # never a broken image.
    imagen_marca_url: str | None = None

    model_config = {"from_attributes": True}
