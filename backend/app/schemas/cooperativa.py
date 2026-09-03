from pydantic import BaseModel, Field


class CooperativaOut(BaseModel):
    id: int
    nombre: str
    nit: str
    estado: bool

    model_config = {"from_attributes": True}


class CooperativaResumenOut(BaseModel):
    """Minimal shape for the cross-cooperativa selector/filter a
    SUPER_ADMIN uses when creating a user or filtering the usuarios list —
    intentionally not the full `CooperativaOut` (a SUPER_ADMIN managing
    another cooperativa's user list has no reason to see its `nit`)."""

    id: int
    nombre: str
    estado: bool

    model_config = {"from_attributes": True}


class CooperativaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    nit: str = Field(min_length=1, max_length=30)
    estado: bool = True


class CooperativaUpdate(BaseModel):
    """The real schema's `cooperativas` table only carries `nombre`, `nit`,
    and `estado` — the earlier design's payment-method toggles and legal-text
    fields (`tarjeta_habilitada`, `cupo_habilitado`, `texto_asuncion_deuda`,
    `correo_contacto`, `logo_url`) have no backing column and are not part of
    this integration pass (see SCHEMA_NOTES.md)."""

    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    estado: bool | None = None
