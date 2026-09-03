"""
Password recovery — real token machinery, mock email delivery.

Tokens are unpredictable (`secrets.token_urlsafe`), single-use, and expire
after `settings.password_reset_token_expire_minutes`. Only a SHA-256 hash
of the token is ever kept in memory — never the raw token. Account
enumeration is prevented by the CALLER (routers/auth_*.py), which must
return the exact same response whether or not `identificador` matches a
real admin/affiliate; this module simply never gives the caller anything
that would let that response differ.

DISCLOSED LIMITATION: the 11 tables given by the spec have no column
reserved for reset tokens on `afiliados` or `usuarios_admin`, and this
first implementation pass was not authorized to add a new table without
explicit justification/approval. The store below is therefore an
in-memory, single-process dict — it does NOT survive a restart and is NOT
shared across multiple workers/replicas. That is acceptable for local
development and for exercising the full frontend<->backend flow, but a
real production deployment running more than one process MUST replace
this with a persistent store (a dedicated table or Redis) — see
SCHEMA_NOTES.md.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings

settings = get_settings()


@dataclass
class _ResetTokenRecord:
    identity_type: str  # "admin" | "afiliado"
    identity_id: int
    expires_at: datetime
    used: bool = False


_TOKENS: dict[str, _ResetTokenRecord] = {}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(identity_type: str, identity_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _TOKENS[_hash(token)] = _ResetTokenRecord(
        identity_type=identity_type,
        identity_id=identity_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    return token


def consume_token(token: str) -> tuple[str, int] | None:
    """Validates, single-uses, and invalidates a token in one step.
    Returns (identity_type, identity_id) on success, None on ANY failure
    (unknown, expired, or already-used) — callers must return the same
    generic error in every failure case, never distinguishing why."""
    record = _TOKENS.get(_hash(token))
    if record is None or record.used or record.expires_at < datetime.now(timezone.utc):
        return None
    record.used = True
    return record.identity_type, record.identity_id
