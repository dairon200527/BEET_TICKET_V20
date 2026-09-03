# Schema notes — the real database is the source of truth

This file previously documented an **inferred** schema (the backend was
first built from table/relationship names only, before a real database
backup existed). That inferred schema is now **obsolete and wrong**. This
integration pass replaced it entirely: the backend's models, schemas,
routers, and Alembic migration were rewritten to match, column-by-column,
the real PostgreSQL database restored from the provided
`beet_ticket.backup` dump. Nothing in `backend/app/models/` is guesswork
anymore — it is a direct mapping of the real tables below.

## The 11 real tables

| Table | Columns | Notes |
|---|---|---|
| `cooperativas` | `id, nombre, nit (unique), estado (boolean), created_at, updated_at` | Tenant root. No `correo_contacto`, `logo_url`, payment-method toggles, or legal text — those don't exist in the real schema. |
| `usuarios_admin` | `id, cooperativa_id (nullable, relaxed this pass), nombre, correo (unique), rol, estado (boolean), password_hash (nullable), created_at, updated_at` | `rol` is a `varchar(30)` CHECK-constrained to exactly `SUPER_ADMIN`, `ADMIN`, `LECTOR` — uppercase. No `ultimo_acceso` column. `cooperativa_id` was `NOT NULL` when this table was first documented; it was relaxed to nullable (`ALTER TABLE usuarios_admin ALTER COLUMN cooperativa_id DROP NOT NULL`) so a `SUPER_ADMIN` — who administers every cooperativa, not one in particular — can exist without being tied to a single one. `ADMIN`/`LECTOR` still always require it; enforced at the application layer (`app/schemas/usuario_admin.py`), since a NOT NULL constraint conditional on another column's value has no direct SQL equivalent. |
| `afiliados` | `id, cooperativa_id, documento, nombres, apellidos, correo, telefono (nullable), estado (boolean), created_at, updated_at, password_hash (nullable, added this pass)` | Unique on `(cooperativa_id, documento)`. `password_hash` did **not** exist when this table was first documented — it was added as a nullable, additive column (`ALTER TABLE afiliados ADD COLUMN password_hash character varying(255) NULL`) so real affiliate authentication could be implemented; see "Affiliate authentication" below. `correo` has **no** unique constraint (only `(cooperativa_id, documento)` does) — the same email can legitimately appear on rows in different cooperativas. No `ciudad`, no `fecha_ingreso`. |
| `convenios` | `id, cooperativa_id, nombre, descripcion (nullable), precio_publico, precio_beet, fecha_inicio, fecha_fin (nullable), estado (boolean), created_at, updated_at` | No `marca`, `categoria`, `tope`, or `tope_periodicidad`. |
| `plantillas` | `id, convenio_id, nombre, version (int, default 1), storage_path (required text), estado (boolean), created_at, updated_at` | Unique on `(convenio_id, version)` — **a convenio can have several versioned plantillas**, unlike an earlier one-per-convenio assumption. The highest `version` with `estado=true` is the one in effect. |
| `unidades_inventario` | `id, convenio_id, codigo (globally unique), estado, fecha_ingreso` | `estado` is `varchar(30)` CHECK-constrained to lowercase `disponible/bloqueada/entregada/redimida/cancelada/vencida`. No `fecha_carga`/`fecha_vencimiento`. See the DEFAULT/CHECK quirk below. |
| `cupos_credito` | `id, afiliado_id (unique), cupo_total, cupo_disponible, estado (boolean), created_at, updated_at` | `cupo_disponible` is the **remaining balance directly** (decremented as spent) — not an accumulated "used" amount. `CHECK(cupo_disponible <= cupo_total)`. No `periodicidad`. |
| `transacciones` | `id, afiliado_id, convenio_id, cantidad, subtotal, total, metodo_pago, numero_cuotas (nullable), estado, referencia_pago (nullable), created_at, updated_at` | `metodo_pago` CHECK: `TARJETA`/`CUPO`. `estado` CHECK: `PENDIENTE/APROBADA/RECHAZADA/CANCELADA/COMPLETADA` — uppercase, and **does** include `CANCELADA` at the transaction level. **No denormalized `cooperativa_id`** — derive it via `afiliado_id → afiliados.cooperativa_id`. |
| `transaccion_unidades` | `id, transaccion_id, unidad_id (unique, FK → unidades_inventario.id), ticket_storage_path (nullable), estado, fecha_entrega (nullable)` | `estado` CHECK: `ASIGNADA/ENTREGADA/UTILIZADA/CANCELADA` — the unit's fulfillment state *within this transaction*, separate from `unidades_inventario.estado`. Column is `unidad_id`, not `unidad_inventario_id`. |
| `documentos_asuncion_deuda` | `id, transaccion_id (unique), documento_storage_path (required), firma_storage_path (nullable), estado, fecha_generacion, fecha_firma (nullable)` | `estado` CHECK: `PENDIENTE/FIRMADO/CANCELADO`. **No `afiliado_id`, `valor`, or `cuotas`** — derived by joining through `transaccion_id`. |
| `logs_auditoria` | `id, usuario_admin_id (nullable), accion, tabla_afectada, registro_id (nullable), detalles (jsonb), created_at` | Append-only. **No `cooperativa_id` or `afiliado_relacionado_id`** — scoping reads goes through `usuario_admin_id → usuarios_admin.cooperativa_id`. |

All FK constraints have **no `ON DELETE` clause** (default `NO ACTION`) —
the models reflect this: no ORM-level cascading delete is configured.

## Additive columns since this table was first documented

- **`convenios.plantilla_catalogo_clave`** (nullable `varchar(50)`) — how
  a convenio selects one of the 4 fixed, code-owned catalog ticket
  designs (`app/services/plantillas_catalogo.py`). A plain string, never
  a foreign key — those 4 designs are not rows in `plantillas`, so
  there's nothing for a FK to reference, and this way any number of
  convenios can share the same design without touching `plantillas`'
  real `UNIQUE(convenio_id, version)` constraint at all. See
  `backend/README.md`'s "Plantillas" section for the full mechanism.
- **`unidades_inventario.contenido`** (nullable `text`) and **`.grupo`**
  (nullable `varchar(100)`) — these two columns exist in the real table
  and always did; an earlier round's model simply didn't map them (and
  incorrectly documented them as absent). Now mapped for accuracy;
  nothing in the app writes to them yet, so this is a read-only
  correction, not new functionality.

## Booleans, not string enums

Unlike an earlier (incorrect) design, `estado` on `cooperativas`,
`usuarios_admin`, `afiliados`, `convenios`, `cupos_credito`, and
`plantillas` is a **plain PostgreSQL boolean** — `true`/`false`, not an
`"activo"/"inactivo"` string. Only `unidades_inventario.estado`,
`transacciones.estado`, `transaccion_unidades.estado`, and
`documentos_asuncion_deuda.estado` are real string-enum columns
(CHECK-constrained `varchar`, not native Postgres `ENUM` types).

## A disclosed, un-"fixed" schema quirk

`unidades_inventario.estado` has a database-level
`DEFAULT 'DISPONIBLE'` (uppercase) but its own `CHECK` constraint only
allows **lowercase** values. Relying on that default for an INSERT would
violate the table's own CHECK constraint. Per the instruction not to
redesign the provided database, this was **not** changed at the schema
level. Instead, `app/models/unidad_inventario.py` never relies on it: the
SQLAlchemy column's Python-side `default=` is set explicitly to the
lowercase value, so every INSERT issued by this application sends an
explicit, valid `estado` and never touches the broken default.

## Affiliate authentication (added this pass)

`afiliados` now has a nullable `password_hash` column (see the table
above) — added specifically so real affiliate authentication could be
implemented. `auth_afiliado.py`, `tickets.py`, and the purchase-flow
endpoint (`POST /api/transacciones/comprar`) are all mounted and working
against the real database. See `backend/README.md` for the full
authentication/registration flow and the design decision behind how
`/registro` identifies which cooperativa a registering affiliate belongs
to (since `documento` is only unique *per* cooperativa, not globally).

## Payments and generated documents — real-schema constraints that shaped this pass

- **No per-cooperativa payment-method toggle.** `cooperativas` has no
  `tarjeta_habilitada`/`cupo_habilitado` columns — both payment methods
  (`TARJETA`, `CUPO`) are always available to every affiliate; there is
  no schema-level way to disable one per cooperativa.
- **No per-cooperativa legal text.** `cooperativas` has no
  `texto_asuncion_deuda` (or similar) column, so the debt-assumption
  document uses one fixed, generic Spanish text
  (`pdf_service.TEXTO_ASUNCION_DEUDA_GENERICO`) rather than a
  per-cooperativa customizable one.
- **`logs_auditoria` has no `afiliado_id`/`cooperativa_id` column at
  all** (see the table below) — it was designed around admin-initiated
  actions only. An affiliate-initiated purchase is logged with
  `usuario_admin_id = NULL` and the affiliate/convenio/amount context
  recorded inside `detalles` (JSON) instead — the closest honest fit the
  real schema allows without adding an unauthorized column.
- **`unidades_inventario` has no `fecha_vencimiento`** — a purchased
  ticket has no per-unit expiration date to show or check.
- **`convenios` has no `marca`, `categoria`, or `tope`** — there is no
  schema-level per-convenio purchase cap; the purchase UI enforces only
  a UI-side sane default (10 units per transaction), not a real backend
  limit sourced from the convenio.

## What changed from the earlier (wrong) version of this file

Every one of the following assumptions in the original schema notes was
**wrong** and has been corrected throughout `app/models/`, `app/schemas/`,
`app/routers/`, the Alembic migration, and the seed script:

- Role vocabulary: `superadmin/administrador/lector` → `SUPER_ADMIN/ADMIN/LECTOR`.
- Most `estado` columns: string enum → boolean.
- `afiliados`: `nombre/cedula/ciudad/fecha_ingreso/password_hash` → `nombres/apellidos/documento` (no ciudad, no fecha_ingreso, no password_hash).
- `convenios`: `marca/categoria/tope/tope_periodicidad/vigencia_hasta` → `descripcion/fecha_inicio/fecha_fin` (marca/categoria/tope removed).
- `plantillas`: one-per-convenio → versioned, `storage_path` required, no `formato_entrega`/`variables_dependientes`.
- `unidades_inventario`: `fecha_carga/fecha_vencimiento` removed; `codigo` is globally unique, not per-convenio.
- `cupos_credito`: `monto_total/monto_usado/periodicidad` → `cupo_total/cupo_disponible` (available balance stored directly; no periodicidad).
- `transacciones`: `cantidad_unidades/valor_total/cuotas/fecha` → `cantidad/subtotal+total/numero_cuotas/created_at`; denormalized `cooperativa_id` removed; `estado` gained `CANCELADA` and lost `FALLIDA`.
- `transaccion_unidades`: `unidad_inventario_id` → `unidad_id`; gained a per-unit `estado`.
- `documentos_asuncion_deuda`: lost `afiliado_id/valor/cuotas`.
- `logs_auditoria`: `entidad/entidad_id/detalle/creado_en/cooperativa_id/afiliado_relacionado_id` → `tabla_afectada/registro_id/detalles/created_at` (the last two columns removed entirely).

This file is now a description of reality, verified by restoring the
provided backup into a local PostgreSQL instance and querying it directly
— not a proposal awaiting verification.
