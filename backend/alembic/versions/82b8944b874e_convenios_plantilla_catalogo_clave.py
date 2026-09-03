"""convenios.plantilla_catalogo_clave

Revision ID: 82b8944b874e
Revises: 3d7e5b1a9f22
Create Date: 2026-09-03

Adds ONE nullable column: `convenios.plantilla_catalogo_clave VARCHAR(50)`.

This is how a convenio selects one of the 4 fixed, code-owned ticket
designs in app/services/plantillas_catalogo.py (Cine Colombia, Mundo
Aventura, Wellness Spa, Salitre Mágico) — a plain string holding the
design's internal `clave` directly, never a foreign key. Those 4 designs
are NOT rows in `plantillas` (that table stays exactly as-is, real
per-convenio uploaded designs only, `convenio_id` still NOT NULL,
untouched by this migration) — they're code constants, so there's
nothing for a foreign key to point at, and no risk of colliding with
`plantillas`' real `UNIQUE(convenio_id, version)` constraint. The same
`clave` can be selected by any number of convenios with no duplication
of anything.

Not constrained at the database level (no CHECK, no FK) — validation
happens in Python against `plantillas_catalogo.CATALOGO`'s keys (see
routers/convenios.py's `actualizar()`) so a 5th design can be added
later without another migration.

Nullable: a convenio never had to have a plantilla before this feature
existed, and isn't required to now — NULL falls back to any legacy
per-convenio `plantillas` row, then the generic ticket
(pdf_service.generar_ticket).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '82b8944b874e'
down_revision: Union[str, None] = '3d7e5b1a9f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('convenios', sa.Column('plantilla_catalogo_clave', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('convenios', 'plantilla_catalogo_clave')
