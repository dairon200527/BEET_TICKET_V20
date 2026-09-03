"""
Identity resolution for every protected endpoint.

The rule enforced everywhere in this file: a request's authorization is
NEVER decided from anything the client sends in the query string, body,
or path — only from the JWT's `sub`/`type` claims, re-resolved against a
freshly loaded database row on every single request. If an admin's role
changes or an affiliate is deactivated mid-session, the very next request
reflects that immediately, because we never trust a cached/embedded claim
for authorization — only for identifying *who* is asking.
"""
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.afiliado import Afiliado
from app.models.cooperativa import Cooperativa
from app.models.enums import RolAdmin
from app.models.usuario_admin import UsuarioAdmin

bearer_scheme = HTTPBearer(auto_error=False)


def _decode_or_401(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado.")
    return payload


def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UsuarioAdmin:
    payload = _decode_or_401(credentials)
    if payload.get("type") != "admin":
        # An affiliate token (or any other token type) must never work here.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido para este recurso.")
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    user = db.get(UsuarioAdmin, user_id)
    if user is None or not user.estado:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no autorizado.")
    return user


def require_roles(*allowed_roles: RolAdmin):
    """Dependency factory: `Depends(require_roles(RolAdmin.SUPERADMIN))`.
    Role comes from the DB row loaded above, never from the JWT claims or
    anything the frontend's dev-only role switcher could influence."""

    def _dependency(user: UsuarioAdmin = Depends(get_current_admin_user)) -> UsuarioAdmin:
        if user.rol not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta acción.")
        return user

    return _dependency


def require_write_access(user: UsuarioAdmin = Depends(get_current_admin_user)) -> UsuarioAdmin:
    """Lector is read-only everywhere (§8) — this dependency guards every
    mutating admin endpoint (POST/PUT/PATCH/DELETE)."""
    if user.rol == RolAdmin.LECTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu rol es de solo lectura.")
    return user


def _effective_cooperativa_id(admin: UsuarioAdmin, cooperativa_id: int | None, db: Session) -> int:
    """SUPER_ADMIN has no cooperativa_id of its own (it administers every
    cooperativa), so it must select one explicitly via `?cooperativa_id=`
    on each request — missing is a 400, nonexistent is a 404. ADMIN/LECTOR
    always resolve to their own `admin.cooperativa_id`; any cooperativa_id
    they send is silently ignored, never trusted for scoping."""
    if admin.rol != RolAdmin.SUPER_ADMIN:
        return admin.cooperativa_id
    if cooperativa_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona una cooperativa.")
    if db.get(Cooperativa, cooperativa_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La cooperativa indicada no existe.")
    return cooperativa_id


def resolve_cooperativa_scope(
    cooperativa_id: int | None = Query(default=None),
    admin: UsuarioAdmin = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> int:
    """Effective cooperativa_id for read (and role-agnostic) endpoints —
    see `_effective_cooperativa_id`."""
    return _effective_cooperativa_id(admin, cooperativa_id, db)


def resolve_cooperativa_scope_write(
    cooperativa_id: int | None = Query(default=None),
    admin: UsuarioAdmin = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> int:
    """Same as `resolve_cooperativa_scope`, but also enforces write access
    (blocks LECTOR) — use on every POST/PATCH/carga-masiva endpoint."""
    return _effective_cooperativa_id(admin, cooperativa_id, db)


def get_current_affiliate(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Afiliado:
    """Real, active dependency for every afiliado-facing route (e.g.
    `GET /api/convenios/catalogo`, `GET /api/tickets/me`) — decodes the
    afiliado-typed JWT (see routers/auth_afiliado.py, which is what
    actually issues it once `afiliados.password_hash` is set) and loads
    the fresh row from PostgreSQL. An admin token is rejected here too:
    `type` must be exactly `"afiliado"`, keeping the two identity spaces
    fully disjoint."""
    payload = _decode_or_401(credentials)
    if payload.get("type") != "afiliado":
        # An admin token must never work here either — the two identity
        # spaces are fully disjoint.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido para este recurso.")
    try:
        afiliado_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    afiliado = db.get(Afiliado, afiliado_id)
    if afiliado is None or not afiliado.estado:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Afiliado no autorizado.")
    return afiliado
