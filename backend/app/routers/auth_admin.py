"""
Admin authentication (`/api/auth/admin`).

Issues an "admin"-typed JWT — see app/dependencies/auth.py for why that
type tag matters. Role/state are never taken from the request — only
ever from the freshly-loaded `UsuarioAdmin` row.

NOTE: password recovery (forgot/reset-password) is intentionally NOT
implemented this pass — it requires a real email provider, which is
explicitly out of scope for this integration (see SCHEMA_NOTES.md /
README.md). Logout is a client-side operation (discarding the stored
JWT) since these tokens are stateless — there is no server-side session
to invalidate.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.usuario_admin import UsuarioAdmin
from app.schemas.auth import AdminLoginRequest, AdminLoginResponse, AdminOut

router = APIRouter(prefix="/api/auth/admin", tags=["auth-admin"])


@router.post("/login", response_model=AdminLoginResponse)
def login(payload: AdminLoginRequest, db: Session = Depends(get_db)) -> AdminLoginResponse:
    usuario = db.execute(
        select(UsuarioAdmin).where(func.lower(UsuarioAdmin.correo) == payload.correo.lower())
    ).scalar_one_or_none()

    # Identical error for "no such user", "inactive user", and "wrong
    # password" — never confirms whether an email exists.
    if (
        usuario is None
        or not usuario.estado
        or not usuario.password_hash
        or not verify_password(payload.password, usuario.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")

    token = create_access_token(subject=str(usuario.id), extra_claims={"type": "admin"})
    return AdminLoginResponse(access_token=token, usuario=AdminOut.model_validate(usuario))


@router.get("/me", response_model=AdminOut)
def me(usuario: UsuarioAdmin = Depends(get_current_admin_user)) -> AdminOut:
    return AdminOut.model_validate(usuario)
