"""
Affiliate authentication (`/api/auth/afiliado`).

Issues an "afiliado"-typed JWT, fully disjoint from the admin token space
(see app/dependencies/auth.py). Account creation is only ever allowed for
an existing `afiliados` roster row an administrator already loaded, and
only once — never a client-chosen cooperativa or affiliate id.

Real affiliate authentication only became possible once `password_hash`
was added to the real `afiliados` table for this phase (see
../models/afiliado.py / ../../SCHEMA_NOTES.md) — this router was entirely
rewritten against the real column names (`documento`, `nombres`,
`apellidos`, boolean `estado`) and no longer imports the deleted
`EstadoAfiliado` enum or the old Cédula-only schemas.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.dependencies.auth import get_current_affiliate
from app.models.afiliado import Afiliado
from app.schemas.afiliado import AfiliadoOut, AffiliateLoginResponse
from app.schemas.auth import AffiliateLoginRequest, AffiliateRegisterRequest
from app.schemas.common import Message

router = APIRouter(prefix="/api/auth/afiliado", tags=["auth-afiliado"])


@router.post("/registro", response_model=Message, status_code=status.HTTP_201_CREATED)
def registro(payload: AffiliateRegisterRequest, db: Session = Depends(get_db)) -> Message:
    """`documento` alone does not identify a single row — it is only
    unique per cooperativa (see SCHEMA_NOTES.md) — so this also requires
    `correo` to match the SAME row. Zero matches, more than one match
    (an extremely unlikely `documento`+`correo` collision across two
    different cooperativas), an already-claimed account, or an inactive
    affiliate all fail with the identical generic message — this is what
    actually prevents roster enumeration, not a coincidence."""
    candidatos = (
        db.execute(
            select(Afiliado).where(
                Afiliado.documento == payload.documento,
                func.lower(Afiliado.correo) == payload.correo.lower(),
                Afiliado.password_hash.is_(None),
            )
        )
        .scalars()
        .all()
    )

    if len(candidatos) != 1 or not candidatos[0].estado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fue posible crear la cuenta con esos datos.")

    afiliado = candidatos[0]
    afiliado.password_hash = hash_password(payload.password)
    db.commit()
    return Message(detail="Cuenta creada correctamente. Ya puedes iniciar sesión.")


@router.post("/login", response_model=AffiliateLoginResponse)
def login(payload: AffiliateLoginRequest, db: Session = Depends(get_db)) -> AffiliateLoginResponse:
    # `correo` has no UNIQUE constraint in the real `afiliados` table (only
    # `(cooperativa_id, documento)` does) — so more than one row can share
    # an email address across different cooperativas. When that happens,
    # login-by-correo is genuinely ambiguous with no cooperativa selector
    # on this screen; we fail closed with the same generic message rather
    # than guessing which affiliate is logging in. See SCHEMA_NOTES.md.
    candidatos = db.execute(select(Afiliado).where(func.lower(Afiliado.correo) == payload.correo.lower())).scalars().all()

    if len(candidatos) != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")

    afiliado = candidatos[0]
    if not afiliado.estado or not afiliado.password_hash or not verify_password(payload.password, afiliado.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")

    token = create_access_token(subject=str(afiliado.id), extra_claims={"type": "afiliado"})
    return AffiliateLoginResponse(access_token=token, afiliado=AfiliadoOut.model_validate(afiliado))


@router.get("/me", response_model=AfiliadoOut)
def me(afiliado: Afiliado = Depends(get_current_affiliate)) -> AfiliadoOut:
    return AfiliadoOut.model_validate(afiliado)
