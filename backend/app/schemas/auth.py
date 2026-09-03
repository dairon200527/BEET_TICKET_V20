from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import RolAdmin

# NOTE: plain `str` (not pydantic's `EmailStr`), not `str` for convenience —
# `EmailStr`'s underlying `email-validator` library rejects addresses on
# special-use/reserved TLDs (e.g. `.test`, per RFC 2606), which would
# reject this task's own mandated test accounts
# (`superadmin@beetticket.test` etc.). A lightweight shape check is enough
# here since the value is only ever matched against the database, never
# used to actually send mail.
_CORREO_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class AdminLoginRequest(BaseModel):
    correo: str = Field(pattern=_CORREO_PATTERN)
    password: str


class AdminOut(BaseModel):
    id: int
    # Nullable: a SUPER_ADMIN belongs to no single cooperativa (see
    # models/usuario_admin.py). This was `int` (non-nullable) until now,
    # which made POST /api/auth/admin/login and GET /api/auth/admin/me
    # raise an unhandled ResponseValidationError for EXACTLY that case —
    # every SUPER_ADMIN created without a cooperativa_id (the normal,
    # documented shape for that role) could never log in. The same
    # nullable-typing fix was already applied to `UsuarioAdminOut` (in
    # schemas/usuario_admin.py) but this second, separate definition was
    # missed.
    cooperativa_id: int | None
    nombre: str
    correo: str
    rol: RolAdmin
    estado: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminLoginResponse(TokenResponse):
    usuario: AdminOut


# --- Affiliate auth ---------------------------------------------------------
# `AffiliateLoginResponse` (which nests `AfiliadoOut`) lives in
# schemas/afiliado.py instead of here, to avoid a circular import —
# schemas/afiliado.py already imports `_CORREO_PATTERN` from this module.
class AffiliateLoginRequest(BaseModel):
    correo: str = Field(pattern=_CORREO_PATTERN)
    password: str


class AffiliateRegisterRequest(BaseModel):
    """Account creation for an EXISTING roster row an admin already
    loaded — never creates a new `afiliados` row itself.

    `documento` alone doesn't identify a single row (it's only unique per
    cooperativa — see SCHEMA_NOTES.md), so this also requires `correo` to
    match the same row. Requiring both together, rather than adding a new
    "cooperativa NIT" field to the form, keeps the registration screen to
    the two pieces of information an affiliate already knows about
    themselves. See backend/README.md for the full reasoning."""

    documento: str = Field(min_length=1, max_length=30)
    correo: str = Field(pattern=_CORREO_PATTERN)
    password: str = Field(min_length=8)
    confirmar_password: str

    @field_validator("documento")
    @classmethod
    def documento_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El documento es obligatorio.")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "AffiliateRegisterRequest":
        if self.password != self.confirmar_password:
            raise ValueError("Las contraseñas no coinciden.")
        return self
