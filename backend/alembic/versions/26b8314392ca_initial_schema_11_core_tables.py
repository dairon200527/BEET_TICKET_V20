"""initial schema: 11 core tables

Revision ID: 26b8314392ca
Revises:
Create Date: 2026-08-25 20:01:44.155490

This migration was REWRITTEN during the admin-module integration pass to
match the REAL, provided PostgreSQL schema exactly (see
../../SCHEMA_NOTES.md) — it no longer reflects the earlier, incorrect
schema this backend originally shipped with. It exists so that a brand
new, EMPTY database can be brought up to the same structure the provided
`beet_ticket.backup` dump already contains.

IDEMPOTENT BY DESIGN — `upgrade()` checks whether `cooperativas` (a stand-in
for "have these 11 tables already been created") exists before doing
anything, and returns immediately if so. This means the exact same command,
`alembic upgrade head`, is now correct in BOTH cases:
  * a genuinely empty database — all 11 tables get created here, then the
    two follow-up migrations run on top;
  * a database freshly restored from `beet_ticket.backup` (which creates
    the same 11 tables directly via raw DDL, bypassing Alembic) — this
    migration's own CREATE TABLE calls are skipped, but Alembic still
    records this revision as applied so the two follow-up migrations
    (which the raw backup does NOT include) run correctly.

Older revisions of this file instead told you to run `alembic stamp head`
after restoring the backup — that command is now WRONG: it marks every
migration as applied, including the two follow-up ones, WITHOUT running
their DDL, silently leaving `afiliados.password_hash` and
`usuarios_admin.cooperativa_id` (nullable) missing from a freshly restored
database. That gap is exactly what broke affiliate account activation
(`POST /api/auth/afiliado/registro`) when tested against a clean restore of
the original backup — see README.md / backend/README.md for the full
write-up. Always use `alembic upgrade head`, never `stamp head`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26b8314392ca'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration creates all 11 tables from scratch, atomically as a
    # single unit — either none of them exist yet (a genuinely empty
    # database) or all of them already do (a `psql -f beet_ticket.backup`
    # restore, which creates the same 11 tables directly via raw DDL,
    # bypassing Alembic entirely). Checking for just one of them is
    # therefore enough to safely skip on a restored backup, so the SAME
    # single command — `alembic upgrade head` — works unconditionally in
    # both cases. There is no longer a `stamp head` vs `upgrade head`
    # decision to get right by hand (see README.md / backend/README.md).
    if sa.inspect(op.get_bind()).has_table('cooperativas'):
        return

    op.create_table(
        'cooperativas',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('nit', sa.String(length=30), nullable=False),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nit'),
    )

    op.create_table(
        'usuarios_admin',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('cooperativa_id', sa.BigInteger(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('correo', sa.String(length=255), nullable=False),
        sa.Column('rol', sa.String(length=30), nullable=False),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("rol IN ('SUPER_ADMIN', 'ADMIN', 'LECTOR')", name='ck_usuarios_admin_rol'),
        sa.ForeignKeyConstraint(['cooperativa_id'], ['cooperativas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correo'),
    )
    op.create_index(op.f('ix_usuarios_admin_cooperativa_id'), 'usuarios_admin', ['cooperativa_id'], unique=False)
    op.create_index(op.f('ix_usuarios_admin_correo'), 'usuarios_admin', ['correo'], unique=True)

    op.create_table(
        'afiliados',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('cooperativa_id', sa.BigInteger(), nullable=False),
        sa.Column('documento', sa.String(length=30), nullable=False),
        sa.Column('nombres', sa.String(length=100), nullable=False),
        sa.Column('apellidos', sa.String(length=100), nullable=False),
        sa.Column('correo', sa.String(length=255), nullable=False),
        sa.Column('telefono', sa.String(length=30), nullable=True),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cooperativa_id'], ['cooperativas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cooperativa_id', 'documento', name='uq_afiliados_cooperativa_documento'),
    )
    op.create_index(op.f('ix_afiliados_cooperativa_id'), 'afiliados', ['cooperativa_id'], unique=False)
    op.create_index(op.f('ix_afiliados_documento'), 'afiliados', ['documento'], unique=False)

    op.create_table(
        'convenios',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('cooperativa_id', sa.BigInteger(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('precio_publico', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('precio_beet', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_fin', sa.Date(), nullable=True),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('fecha_fin IS NULL OR fecha_fin >= fecha_inicio', name='ck_convenios_fecha_fin_valida'),
        sa.CheckConstraint('precio_publico >= 0 AND precio_beet >= 0', name='ck_convenios_precios_no_negativos'),
        sa.ForeignKeyConstraint(['cooperativa_id'], ['cooperativas.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_convenios_cooperativa_id'), 'convenios', ['cooperativa_id'], unique=False)

    op.create_table(
        'plantillas',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('convenio_id', sa.BigInteger(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('version > 0', name='chk_plantillas_version'),
        sa.ForeignKeyConstraint(['convenio_id'], ['convenios.id'], name='fk_plantillas_convenio'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('convenio_id', 'version', name='uq_plantillas_version'),
    )
    op.create_index(op.f('ix_plantillas_convenio_id'), 'plantillas', ['convenio_id'], unique=False)

    op.create_table(
        'unidades_inventario',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('convenio_id', sa.BigInteger(), nullable=False),
        sa.Column('codigo', sa.String(length=100), nullable=False),
        # NOTE: the real database's own DEFAULT here is 'DISPONIBLE'
        # (uppercase), which mismatches its own lowercase-only CHECK below —
        # a disclosed, pre-existing schema quirk (see SCHEMA_NOTES.md). This
        # migration reproduces the real DB byte-for-byte rather than
        # "fixing" it; the application never relies on this default (see
        # models/unidad_inventario.py).
        sa.Column('estado', sa.String(length=30), server_default=sa.text("'DISPONIBLE'"), nullable=False),
        sa.Column('fecha_ingreso', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('contenido', sa.Text(), nullable=True),
        sa.Column('grupo', sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "estado IN ('disponible', 'bloqueada', 'entregada', 'redimida', 'cancelada', 'vencida')",
            name='ck_unidades_inventario_estado',
        ),
        sa.ForeignKeyConstraint(['convenio_id'], ['convenios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('codigo'),
    )
    op.create_index(op.f('ix_unidades_inventario_convenio_id'), 'unidades_inventario', ['convenio_id'], unique=False)
    op.create_index(op.f('ix_unidades_inventario_estado'), 'unidades_inventario', ['estado'], unique=False)

    op.create_table(
        'cupos_credito',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('afiliado_id', sa.BigInteger(), nullable=False),
        sa.Column('cupo_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cupo_disponible', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('estado', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            'cupo_total >= 0 AND cupo_disponible >= 0 AND cupo_disponible <= cupo_total',
            name='ck_cupos_credito_montos_validos',
        ),
        sa.ForeignKeyConstraint(['afiliado_id'], ['afiliados.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('afiliado_id'),
    )

    op.create_table(
        'transacciones',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('afiliado_id', sa.BigInteger(), nullable=False),
        sa.Column('convenio_id', sa.BigInteger(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('metodo_pago', sa.String(length=30), nullable=False),
        sa.Column('numero_cuotas', sa.Integer(), nullable=True),
        sa.Column('estado', sa.String(length=30), server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column('referencia_pago', sa.String(length=150), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('cantidad > 0', name='ck_transacciones_cantidad_positiva'),
        sa.CheckConstraint('subtotal >= 0 AND total >= 0', name='ck_transacciones_montos_no_negativos'),
        sa.CheckConstraint('numero_cuotas IS NULL OR numero_cuotas > 0', name='ck_transacciones_cuotas_positivas'),
        sa.CheckConstraint("metodo_pago IN ('TARJETA', 'CUPO')", name='ck_transacciones_metodo_pago'),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')",
            name='ck_transacciones_estado',
        ),
        sa.ForeignKeyConstraint(['afiliado_id'], ['afiliados.id']),
        sa.ForeignKeyConstraint(['convenio_id'], ['convenios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transacciones_afiliado_id'), 'transacciones', ['afiliado_id'], unique=False)
    op.create_index(op.f('ix_transacciones_convenio_id'), 'transacciones', ['convenio_id'], unique=False)
    op.create_index(op.f('ix_transacciones_estado'), 'transacciones', ['estado'], unique=False)

    op.create_table(
        'transaccion_unidades',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('transaccion_id', sa.BigInteger(), nullable=False),
        sa.Column('unidad_id', sa.BigInteger(), nullable=False),
        sa.Column('ticket_storage_path', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(length=30), server_default=sa.text("'ASIGNADA'"), nullable=False),
        sa.Column('fecha_entrega', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('ASIGNADA', 'ENTREGADA', 'UTILIZADA', 'CANCELADA')",
            name='ck_transaccion_unidades_estado',
        ),
        sa.ForeignKeyConstraint(['transaccion_id'], ['transacciones.id']),
        sa.ForeignKeyConstraint(['unidad_id'], ['unidades_inventario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unidad_id'),
    )
    op.create_index(op.f('ix_transaccion_unidades_transaccion_id'), 'transaccion_unidades', ['transaccion_id'], unique=False)

    op.create_table(
        'documentos_asuncion_deuda',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('transaccion_id', sa.BigInteger(), nullable=False),
        sa.Column('documento_storage_path', sa.Text(), nullable=False),
        sa.Column('firma_storage_path', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(length=30), server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column('fecha_generacion', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('fecha_firma', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estado IN ('PENDIENTE', 'FIRMADO', 'CANCELADO')", name='ck_documentos_asuncion_deuda_estado'),
        sa.ForeignKeyConstraint(['transaccion_id'], ['transacciones.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaccion_id'),
    )

    op.create_table(
        'logs_auditoria',
        sa.Column('id', sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column('usuario_admin_id', sa.BigInteger(), nullable=True),
        sa.Column('accion', sa.String(length=50), nullable=False),
        sa.Column('tabla_afectada', sa.String(length=100), nullable=False),
        sa.Column('registro_id', sa.BigInteger(), nullable=True),
        sa.Column('detalles', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_admin_id'], ['usuarios_admin.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_logs_auditoria_usuario_admin_id'), 'logs_auditoria', ['usuario_admin_id'], unique=False)
    op.create_index(op.f('ix_logs_auditoria_created_at'), 'logs_auditoria', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('logs_auditoria')
    op.drop_table('documentos_asuncion_deuda')
    op.drop_table('transaccion_unidades')
    op.drop_table('transacciones')
    op.drop_table('cupos_credito')
    op.drop_table('unidades_inventario')
    op.drop_table('plantillas')
    op.drop_table('convenios')
    op.drop_table('afiliados')
    op.drop_table('usuarios_admin')
    op.drop_table('cooperativas')
