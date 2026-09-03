"""add afiliados.password_hash

Revision ID: 8f3a1c2d9e10
Revises: 26b8314392ca
Create Date: 2026-08-27

Documents a real, additive change made to the real database for this
phase: `afiliados.password_hash` (nullable varchar(255), same shape as
`usuarios_admin.password_hash`) was added by hand so real affiliate
authentication becomes possible — see ../../SCHEMA_NOTES.md and
app/models/afiliado.py.

Always applied via `alembic upgrade head` — see the initial migration
(`26b8314392ca_*.py`) for why that single command is correct whether
you're migrating a freshly restored `beet_ticket.backup` or a genuinely
empty database. (An earlier version of this docstring told you to run
`alembic stamp head` instead on a restored database — that was the actual
bug that left this column missing and broke affiliate account
activation; see backend/README.md.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f3a1c2d9e10'
down_revision: Union[str, None] = '26b8314392ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('afiliados', sa.Column('password_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('afiliados', 'password_hash')
