"""usuarios_admin.cooperativa_id nullable

Revision ID: 3d7e5b1a9f22
Revises: 8f3a1c2d9e10
Create Date: 2026-08-27

Documents a real, additive/relaxing change made to the real database for
this phase: `usuarios_admin.cooperativa_id` was changed from NOT NULL to
NULLable, so a SUPER_ADMIN — who administers every cooperativa, not one
in particular — can exist without being tied to a single cooperativa_id.
ADMIN/LECTOR rows must still always have a cooperativa_id; that rule is
enforced at the application layer (see app/schemas/usuario_admin.py),
since the database has no way to make a NOT NULL constraint conditional
on another column's value.

Always applied via `alembic upgrade head` — see the initial migration
(`26b8314392ca_*.py`) for why that single command is correct whether
you're migrating a freshly restored `beet_ticket.backup` or a genuinely
empty database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3d7e5b1a9f22'
down_revision: Union[str, None] = '8f3a1c2d9e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('usuarios_admin', 'cooperativa_id', existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column('usuarios_admin', 'cooperativa_id', existing_type=sa.BigInteger(), nullable=False)
