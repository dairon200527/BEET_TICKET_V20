from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.auth import TokenResponse, _CORREO_PATTERN


class AfiliadoOut(BaseModel):
    id: int
    cooperativa_id: int
    cooperativa_nombre: str | None = None
    documento: str
    nombres: str
    apellidos: str
    correo: str
    telefono: str | None
    estado: bool
    # Only populated by GET /api/afiliados (the admin listing) via a
    # single outerjoin against cupos_credito, so the cupo is visible at a
    # glance without opening each row — never fetched per-row (that would
    # be an N+1 query). `None` for an afiliado with no cupo assigned yet.
    cupo_total: Decimal | None = None
    cupo_disponible: Decimal | None = None

    model_config = {"from_attributes": True}


class AfiliadoCreate(BaseModel):
    """Used by the admin bulk-load flow (Excel/CSV) — one row per
    affiliate."""

    documento: str = Field(min_length=1, max_length=30)
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    correo: str = Field(pattern=_CORREO_PATTERN)
    telefono: str | None = Field(default=None, max_length=30)


class AfiliadoCargaMasivaRow(BaseModel):
    """One row of the afiliados bulk upload/upsert
    (POST /api/afiliados/carga-masiva). `cupo_total` is required — every
    row creates or updates BOTH the `afiliados` row and its `cupos_credito`
    row together. `estado` is intentionally NOT included here: it's parsed
    separately with `bulk_upload.parse_bool_or_none` because a blank cell
    must mean "leave unchanged" on an update, which a single always-a-bool
    field can't represent.

    `cupo_disponible` is OPTIONAL — a blank cell means "same as
    cupo_total" (a freshly-created cupo starts fully unspent). It is only
    ever used when CREATING a new afiliado; on an update, the existing
    delta-based `ajustar_cupo_total` policy already decides how
    cupo_disponible moves when cupo_total changes (see routers/afiliados.py),
    so a cupo_disponible value on an update row is not applied directly —
    consistent with how the manual `PATCH /api/cupos/{id}` endpoint works."""

    documento: str = Field(min_length=1, max_length=30)
    nombres: str = Field(min_length=1, max_length=100)
    apellidos: str = Field(min_length=1, max_length=100)
    correo: str = Field(pattern=_CORREO_PATTERN)
    telefono: str | None = Field(default=None, max_length=30)
    cupo_total: Decimal = Field(ge=0)
    cupo_disponible: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def cupo_disponible_no_mayor_al_total(self) -> "AfiliadoCargaMasivaRow":
        if self.cupo_disponible is not None and self.cupo_disponible > self.cupo_total:
            raise ValueError("cupo_disponible no puede ser mayor a cupo_total.")
        return self


class AfiliadoAdminUpdate(BaseModel):
    """Fields an administrator may change about an affiliate."""

    nombres: str | None = Field(default=None, min_length=1, max_length=100)
    apellidos: str | None = Field(default=None, min_length=1, max_length=100)
    correo: str | None = Field(default=None, pattern=_CORREO_PATTERN)
    telefono: str | None = Field(default=None, max_length=30)
    estado: bool | None = None


class AfiliadoSelfUpdate(BaseModel):
    """Fields the affiliate may change about themselves — deliberately
    excludes documento, nombres, apellidos, cooperativa_id, and estado,
    which stay under the cooperative's administration."""

    correo: str | None = Field(default=None, pattern=_CORREO_PATTERN)
    telefono: str | None = Field(default=None, max_length=30)


class AffiliateLoginResponse(TokenResponse):
    afiliado: AfiliadoOut
