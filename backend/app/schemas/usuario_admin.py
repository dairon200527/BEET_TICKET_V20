from pydantic import BaseModel, Field, model_validator

from app.models.enums import RolAdmin
from app.schemas.auth import _CORREO_PATTERN


class UsuarioAdminOut(BaseModel):
    id: int
    cooperativa_id: int | None
    cooperativa_nombre: str | None = None
    nombre: str
    correo: str
    rol: RolAdmin
    estado: bool

    model_config = {"from_attributes": True}


class UsuarioAdminCreate(BaseModel):
    """Only a SUPER_ADMIN may create admin users — enforced in the
    router/dependency layer, not just by hiding the button in the UI.

    `cooperativa_id` is REQUIRED for `ADMIN`/`LECTOR` (they always belong
    to exactly one cooperativa, and every other endpoint in this app
    scopes their access by it) and OPTIONAL for `SUPER_ADMIN` (who
    administers every cooperativa, not one in particular)."""

    nombre: str = Field(min_length=1, max_length=200)
    correo: str = Field(pattern=_CORREO_PATTERN)
    password: str = Field(min_length=8)
    rol: RolAdmin = RolAdmin.LECTOR
    cooperativa_id: int | None = None

    @model_validator(mode="after")
    def cooperativa_requerida_salvo_super_admin(self) -> "UsuarioAdminCreate":
        if self.rol != RolAdmin.SUPER_ADMIN and self.cooperativa_id is None:
            raise ValueError("cooperativa_id es obligatorio para los roles ADMIN y LECTOR.")
        return self


class UsuarioAdminUpdate(BaseModel):
    """Partial update — an absent field means "leave unchanged". The
    required-unless-SUPER_ADMIN rule can't be validated on this schema
    alone (either field might be omitted while the other changes), so the
    router re-checks it after merging `model_dump(exclude_unset=True)`
    onto the row's *current* values."""

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    rol: RolAdmin | None = None
    estado: bool | None = None
    cooperativa_id: int | None = None
