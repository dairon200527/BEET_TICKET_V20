# BEET Ticket — Backend (Admin Module)

FastAPI + SQLAlchemy + PostgreSQL + Pydantic backend for BEET Ticket.
This README documents the **ADMIN MODULE integration pass**: the backend
was adapted to match the real, already-populated PostgreSQL database
(restored from the provided `beet_ticket.backup`) rather than the earlier,
inferred schema it originally shipped with. Read `../SCHEMA_NOTES.md`
first — it documents the real 11-table schema and every difference from
the earlier version of this backend.

## Scope of this pass

**In scope and fully working:**
- Admin login (JWT), role-based authorization
  (`SUPER_ADMIN`/`ADMIN`/`LECTOR`), and every admin back-office screen
  (afiliados, convenios, plantillas, inventario, cupos, transacciones,
  documentos, usuarios, dashboard, reportes, audit logging).
- **Real affiliate authentication** — registro (self-service account
  creation against an existing roster row), login, `/me`, and a
  self-service profile update (correo/telefono only). See "Affiliate
  authentication" below for the design decision behind `/registro`.
- **Bulk Excel/CSV upload for convenios** (`POST /api/convenios/carga-masiva`),
  matching the existing afiliados bulk-upload pattern.
- **The full purchase flow** (`POST /api/transacciones/comprar`) — card
  payment via a mock gateway, credit-quota (`cupo`) payment with a
  digital signature and generated debt-assumption document, atomic
  inventory locking, and ticket issuance.
- **Real, downloadable PDF tickets** (`GET /api/tickets/me/{id}/descarga`)
  — server-generated on every request via `reportlab`, never
  client-side.
- **File storage** via the existing Firebase-ready abstraction
  (`app/services/storage_service.py`), reused as-is in its local-disk
  fallback mode. See "File storage / activating Firebase" below.
- **Multi-tenancy for `usuarios_admin`** — a `SUPER_ADMIN` can now belong
  to NO cooperativa (administers all of them) and explicitly assigns a
  cooperativa when creating an `ADMIN`/`LECTOR`; the usuarios listing is
  cross-cooperativa with an optional filter. See "Multi-tenancy for
  usuarios_admin" below.
- **Real UPSERT for the afiliados bulk upload**, now including a
  `cupo_total` column that creates/adjusts the affiliate's `cupos_credito`
  row in the same pass. See "The afiliados bulk upload is now a real
  upsert" below.
- **Bulk inventory upload across multiple convenios in one file**
  (`POST /api/inventario/carga-masiva`), identifying each row's convenio
  by name rather than requiring one pre-selected convenio_id.
- **Real `.xlsx` report exports**
  (`GET /api/reportes/rendimiento-convenios/exportar`,
  `GET /api/reportes/afiliados/exportar`) — the "Excel/PDF" export
  buttons were previously a stub that told the user "not connected to
  the backend yet."

**Explicitly NOT implemented this pass:**
- **Real Firebase Storage credentials** — deliberately deferred to the
  end of the project, after everything else is tested (see "File
  storage / activating Firebase later" below for exactly what changes
  when real credentials are available; no code changes are needed,
  only environment variables).
- **A real card payment gateway** (Wompi/PayU/ePayco/etc.) —
  `app/services/payment_gateway.py` is a deterministic mock behind the
  same interface a real provider would implement; only that one file's
  body needs to change later.
- **Password recovery / email delivery** (admin or affiliate) — no
  email provider is configured.
- **Per-affiliate debt-document download endpoint** — the debt-assumption
  PDF is generated and stored during a cupo purchase, but only the
  admin-facing, read-only `GET /api/documentos` listing is mounted; no
  affiliate-facing download route exists yet (unlike tickets, which do
  have one).

## Python version

Written and tested against **Python 3.11/3.12**. `requirements.txt`
pins are the same as the original backend build.

## Stack

- **FastAPI** — HTTP layer, routers under `app/routers/`
- **SQLAlchemy 2.0** — ORM, `app/models/` (one file per real table, + `enums.py`)
- **PostgreSQL** — the 11 real tables from `beet_ticket.backup`, unmodified
- **Pydantic v2** — request/response validation, `app/schemas/`
- **Alembic** — migration environment, `alembic/` (see "Database setup" below — **read this before running `alembic upgrade head`**)
- **Argon2** (via passlib) — password hashing
- **python-jose** — JWT issuance/verification
- **pytest + httpx** — test suite, `tests/`

## Database setup — IMPORTANT

This backend does **not** create or replace your database. You must
restore the provided `beet_ticket.backup` into a real PostgreSQL instance
yourself:

```bash
# 1. Create an empty database (adjust name/user as needed)
psql -U postgres -c "CREATE DATABASE beet_ticket OWNER postgres;"

# 2. Restore the provided backup into it
psql -U postgres -d beet_ticket -f /path/to/beet_ticket.backup
```

Then point `DATABASE_URL` at that database (see `.env.example`), and run:

```bash
alembic upgrade head
```

**This single command is correct for BOTH a fresh restore of
`beet_ticket.backup` and a genuinely empty database — always `upgrade
head`, never `stamp head`.**

Older versions of this file instead told you to run `alembic stamp head`
after restoring the backup, on the reasoning that your database "already
had" the 11 tables from the dump. **That advice was a real bug, not a
style choice**, and it is the confirmed root cause of affiliate account
activation (`POST /api/auth/afiliado/registro`) failing on a freshly
restored database: `stamp head` marks *every* migration revision as
applied *without running any of their SQL*. Two of those migrations —
adding `afiliados.password_hash` and making
`usuarios_admin.cooperativa_id` nullable — are NOT part of the raw
`beet_ticket.backup` dump; `stamp head` silently skips them, leaving a
database that looks fully migrated but is actually missing a column the
application writes to on every activation. The fix was to `alembic/versions/26b8314392ca_*.py`,
the initial migration: its `upgrade()` now checks whether the 11 tables
already exist (`cooperativas` as the stand-in check) and, if so, skips
only its own `CREATE TABLE` calls — Alembic still records the revision
as applied and moves on to run the two follow-up migrations that a raw
backup restore never had. Verified against both starting states — see
`tests/test_alembic_migration.py`.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: DATABASE_URL (point at your restored beet_ticket DB), JWT_SECRET

alembic upgrade head        # see "Database setup" above — correct for both a restored DB and a fresh one
python -m scripts.seed_admin_users   # creates/updates the 3 test admin accounts (see below)
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive OpenAPI docs.

### Plantillas: 4 fixed designs in code, selectable per convenio

**Where the 4 designs live (read this before adding a 5th):** the
actual layout/positions/colors/texts for Cine Colombia, Mundo Aventura,
Wellness Spa and Salitre Mágico are Python dicts (`LAYOUT_*` +
`CATALOGO`) in **`backend/app/services/plantillas_catalogo.py`** — there
is no `.html` file per brand design. Each brand's logo/header/badge
image files live in **`backend/app/static/plantillas_catalogo/`**,
referenced by filename from that entry's `imagenes` dict. To add a 5th
design: write its `LAYOUT_*` dict, add an entry to `CATALOGO`, and drop
its image files in that same static folder — nothing else changes, and
no migration is needed (`clave` is validated in Python only, never
constrained in PostgreSQL).

This is a SEPARATE, older mechanism from the "diseños base" flow
(`plantillas_base.py` + **`backend/templates/plantillas_base/`**, which
DOES hold real standalone `.html` files — `diseno_base_1.html`,
`diseno_base_2.html`). That one is a real per-convenio uploaded
`plantillas` row with a `template_key` + admin-filled content form; the
4 catalog designs above are never uploaded or stored as a database row
at all — they're selected directly by name (see below).

**Creating a NEW per-convenio plantilla by pasting raw HTML (no visual
editor, no manual positioning):** `POST /api/plantillas` — the convenio
detail page's "Crear plantilla con HTML" button. The admin pastes a
complete HTML/Jinja2 document referencing the required variables
(`convenio`, `items`, `afiliado`, `transaccion_id`, `fecha_emision`,
`fecha_vencimiento` — see `template_engine.REQUIRED_VARIABLES`), plus
optionally a logo, a cooperativa logo, and free-text content fields
(título, términos, instrucciones, etc.). `POST /api/plantillas/preview`
runs the EXACT same validation + a real WeasyPrint render with fixture
data and returns the PDF WITHOUT saving anything — the two endpoints
share one function (`template_engine.validar_y_renderizar`) so a
preview can never look different from what actually gets saved, and a
broken template can never be persisted only to fail on a real purchase.
A successful `POST` adds a new versioned row to the real `plantillas`
table (`plantillas.convenio_id`) — no schema change, since that table
already supports exactly this. Requires write access (ADMIN/SUPER_ADMIN
— LECTOR is blocked, same as every other mutating endpoint).

**Selection:** `convenios.plantilla_catalogo_clave` — a plain nullable
`VARCHAR(50)` column storing one of `CATALOGO`'s keys directly (e.g.
`"cine_colombia"`), never a foreign key: these 4 designs aren't real
per-convenio `plantillas` rows, so there's nothing for a foreign key to
point at, and the same `clave` can be selected by any number of
convenios with zero risk of colliding with `plantillas`' real
`UNIQUE(convenio_id, version)` constraint. Set it via
`PATCH /api/convenios/{id}` (`{"plantilla_catalogo_clave": "cine_colombia"}`,
validated against `CATALOGO`'s keys — 400 if invalid) — the admin does
this from the convenio detail page's "Seleccionar plantilla" button.

`pdf_service.generar_ticket()` resolves, in order: (1) the convenio's
`plantilla_catalogo_clave`, rendered straight from code; (2) any real,
per-convenio `plantillas` row still active for that convenio (the
legacy visual-editor/diseño-base/uploaded-HTML formats, via the real
`plantillas.convenio_id` foreign key); (3) the generic placeholder
ticket — never blocked. The same resolution order drives
`GET /api/convenios/{id}/imagen-marca` (the convenio's real brand logo,
shown on the affiliate portal's benefit cards instead of the generic
diagonal-stripes placeholder).

**Stabilization history (for context):** an earlier round added a
`convenios.plantilla_id` FK column pointing into `plantillas` for this
same purpose. The real production database never had that column —
only a local dev copy did — so the app crashed there with
`psycopg2.errors.UndefinedColumn: no existe la columna
convenios.plantilla_id`; that column was reverted entirely (never
re-added). `plantilla_catalogo_clave` above is the column that replaced
it: deliberately a plain string with no FK, so it can never collide
with `plantillas`' real constraints the way the FK approach did.

### Test admin accounts

`python -m scripts.seed_admin_users` creates (or updates, idempotently)
exactly these three accounts, attached to the first existing cooperativa
in your database (or a new "Cooperativa Demo" row if none exists):

| Role | Correo | Password |
|---|---|---|
| SUPER_ADMIN | `superadmin@beetticket.test` | `SuperAdmin123!` |
| ADMIN | `admin@beetticket.test` | `Admin123!` |
| LECTOR | `lector@beetticket.test` | `Lector123!` |

Passwords are hashed with Argon2 before being stored — the script never
writes plaintext to `password_hash`.

## Running tests

```bash
# Tests run against a REAL PostgreSQL database, NOT beet_ticket itself —
# point DATABASE_URL (in your shell env, not necessarily .env) at a
# separate, disposable database (e.g. beet_ticket_test). The test suite
# DROPS and CREATEs the schema and TRUNCATEs every table between tests —
# never point it at a database you care about.
createdb beet_ticket_test
DATABASE_URL=postgresql+psycopg2://postgres:<PASSWORD>@localhost:5432/beet_ticket_test pytest -q
```

67 tests cover: admin login success/failure, unauthenticated access,
disjoint admin/affiliate token types, LECTOR write-block, role-restricted
admin-user management, cross-cooperativa isolation (afiliados and
convenios, both hidden as 404), audit logging (recorded correctly,
scoped correctly, survives non-JSON-native field types like `Decimal`),
**affiliate registro/login/me/self-update** (including the
documento+correo matching rule and the ambiguous-correo fail-closed
case), **the purchase flow** (card approved, card rejected as a
committed outcome, cupo with signature, insufficient inventory,
insufficient cupo, inactive/cross-tenant convenio, and ticket download
ownership), **usuarios_admin multi-tenancy** (nullable cooperativa_id,
required-unless-SUPER_ADMIN validation on create/update, cross-cooperativa
listing + filter), **afiliados bulk upload as a real upsert** (create
with cupo, update-by-documento, the cupo_total delta-adjustment policy,
blank-estado-leaves-unchanged, an afiliado absent from the file staying
untouched), **convenios bulk upload** (create, update-by-nombre,
duplicate/invalid-row handling, per-cooperativa scoping), **inventory
bulk upload across multiple convenios** (unknown-convenio-name and
duplicate-codigo handling, per-cooperativa scoping), and **the
`.xlsx` report exports** (real, parseable workbook bytes, scoped to the
requesting admin's own cooperativa).

## Authentication & authorization

- **Admin tokens only** (`type: "admin"`) — `app/dependencies/auth.py`'s
  `get_current_admin_user` re-loads the `UsuarioAdmin` row fresh on every
  request; role and `estado` are never trusted from the JWT claims, only
  `sub` (the numeric id) and `type` are.
- `require_roles(*roles)` gates SUPER_ADMIN-only endpoints (admin-user
  management). `require_write_access` blocks `LECTOR` from every mutating
  endpoint.
- Logout is client-side only (discarding the stored JWT) — these tokens
  are stateless, there is no server-side session to invalidate.
- Passwords are never returned in any API response (`password_hash` is
  simply absent from every Pydantic output schema), and JWT secrets/DB
  credentials are never logged or exposed in error responses.

## Multi-tenancy & ownership

Every admin query filters by `current_admin.cooperativa_id`, derived
where necessary via a join (`transacciones`/`documentos_asuncion_deuda`
have no denormalized `cooperativa_id` — see `SCHEMA_NOTES.md`).
Cross-tenant resources are hidden as **404**, never revealed as 403.

## Audit logging

`app/services/audit_service.record()` is the only code path that inserts
into `logs_auditoria` — every mutating admin action calls it in the same
DB transaction as the change it documents. There is no update/delete
route for this table. Reading it back (`GET /api/admin/logs`) is scoped
via `usuario_admin_id → usuarios_admin.cooperativa_id`, since the table
itself has no `cooperativa_id` column.

## API modules (all mounted)

| Prefix | Router file |
|---|---|
| `/api/auth/admin` | `auth_admin.py` (login, me) |
| `/api/auth/afiliado` | `auth_afiliado.py` (registro, login, me) |
| `/api/afiliados` | `afiliados.py` (admin CRUD + bulk upload; `GET`/`PATCH /me` for the affiliate) |
| `/api/convenios` | `convenios.py` (admin CRUD + bulk upload; `GET /catalogo` for the affiliate) |
| `/api/plantillas` | `plantillas.py` |
| `/api/inventario` | `inventario.py` |
| `/api/cupos` | `cupos.py` (admin; `GET /me` for the affiliate) |
| `/api/transacciones` | `transacciones.py` (admin read-only; `POST /comprar`, `GET /me`, `GET /me/{id}` for the affiliate) |
| `/api/tickets` | `tickets.py` (`GET /me`, `GET /me/{id}/descarga` — real PDF bytes) |
| `/api/documentos` | `documentos.py` (admin, read-only listing) |
| `/api/admin` | `admin.py` (admin-user mgmt, cooperativa config + listing, audit log) |
| `/api/dashboard` | `dashboard.py` |
| `/api/reportes` | `reportes.py` (JSON + `/exportar` real `.xlsx` downloads) |

## Multi-tenancy for usuarios_admin

`usuarios_admin.cooperativa_id` is nullable (see `../SCHEMA_NOTES.md`) so
a `SUPER_ADMIN` — who administers every cooperativa, not one in
particular — can exist without belonging to a single one. `ADMIN` and
`LECTOR` still always require it; enforced at the application layer:

- `UsuarioAdminCreate` rejects (`422`) creating an `ADMIN`/`LECTOR` with
  no `cooperativa_id`.
- `PATCH /api/admin/usuarios/{id}` re-checks the same rule against the
  row's EFFECTIVE values after merging the partial update — a request
  that only changes `rol` (e.g. `LECTOR` → `ADMIN`) or only clears
  `cooperativa_id` must still leave the row valid either way.
- `POST /api/admin/usuarios` takes `cooperativa_id` from the request body
  — **never** the creating `SUPER_ADMIN`'s own `cooperativa_id` (which
  may itself be `NULL`). A `SUPER_ADMIN` explicitly assigns which
  cooperativa a new `ADMIN`/`LECTOR` belongs to.
- `GET /api/admin/usuarios` is **cross-cooperativa by default** — the one
  listing in this app that has always ignored `admin.cooperativa_id` even
  before the cross-cooperativa data-access work below, since a
  `SUPER_ADMIN` managing *usuarios_admin* legitimately needs to see every
  cooperativa's users — with an optional `?cooperativa_id=` filter.

## Cross-cooperativa DATA access for SUPER_ADMIN (`resolve_cooperativa_scope`)

Beyond managing `usuarios_admin` (above), a `SUPER_ADMIN` can now also
view and manage every cooperativa's **business data** — afiliados,
convenios, inventario, cupos, transacciones, reportes, dashboard,
plantillas, documentos — but never implicitly or mixed across
cooperativas. `app/dependencies/auth.py` adds two dependencies used
everywhere `admin.cooperativa_id` used to be read directly:

```python
def resolve_cooperativa_scope(
    cooperativa_id: int | None = Query(default=None),
    admin: UsuarioAdmin = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> int:
    ...  # ADMIN/LECTOR -> admin.cooperativa_id, always, ?cooperativa_id= ignored.
         # SUPER_ADMIN -> the id passed in ?cooperativa_id=; missing -> 400,
         # nonexistent -> 404.

def resolve_cooperativa_scope_write(...)  # same rule, also blocks LECTOR
```

- **ADMIN/LECTOR**: unchanged behavior — always scoped to their own
  `admin.cooperativa_id`; any `cooperativa_id` they send is silently
  ignored, never trusted for scoping (defense in depth even though the
  frontend never shows them a selector).
- **SUPER_ADMIN**: has no cooperativa of its own, so it MUST select one
  explicitly via `?cooperativa_id=` on every request to these modules —
  `GET`/`POST`/`PATCH` alike, including multipart carga-masiva uploads
  (query params work alongside `File`/`Form` in FastAPI). No
  `?cooperativa_id=` → `400 Selecciona una cooperativa.`; a nonexistent
  one → `404 La cooperativa indicada no existe.`
- A bulk upload (`carga-masiva`) creates its rows in the **resolved**
  cooperativa, not `admin.cooperativa_id` — so a `SUPER_ADMIN` uploading
  an afiliados/convenios/inventario Excel with a cooperativa selected
  gets rows in that cooperativa, exactly like an `ADMIN` uploading into
  their own.
- Applied to every module named above, plus two more found by auditing
  every router for the same `admin.cooperativa_id`-read pattern that
  weren't explicitly requested but had the identical bug for
  `SUPER_ADMIN`: `plantillas.py` (list/get/create/update) and
  `documentos.py` (listing). Also fixed on the admin-facing side:
  `GET/PATCH /api/admin/cooperativa` (singular — an admin's own
  cooperativa profile; for `SUPER_ADMIN` this is now "the selected
  cooperativa's profile" instead of crashing on a `NULL` id) and
  `GET /api/admin/logs` (the audit log was silently scoped to
  `admin.cooperativa_id`, which is `NULL` for a `SUPER_ADMIN` with no
  selection concept before this pass — it showed almost nothing).
- **Cooperativas CRUD**: `GET /api/admin/cooperativas` (id/nombre/estado,
  `SUPER_ADMIN`-only) already existed and feeds both the usuarios-screen
  filter and the new persistent selector. `POST /api/admin/cooperativas`
  is new this pass (`SUPER_ADMIN`-only, 409 on duplicate `nit`) — the
  create-cooperativa flow reported as broken ("no me deja ingresar
  cooperativas") was in fact simply never implemented; there was no
  backend endpoint nor frontend screen for it before now.
- Frontend: see `../frontend/README.md` for the persistent cooperativa
  selector (`CooperativaContext`), the empty states on the 7 scoped
  screens, and the "Crear cooperativa" screen.

## The afiliados bulk upload is now a real upsert

`POST /api/afiliados/carga-masiva` no longer only creates rows and skips
existing `documento`s as "duplicados" — it's a real UPSERT, and every row
now also carries a required `cupo_total` column:

- **New `documento`**: creates the afiliado AND its `cupos_credito` row
  (`cupo_disponible = cupo_total` — a freshly-assigned, unspent cupo).
- **Existing `documento`**: updates `nombres`/`apellidos`/`correo`/
  `telefono` unconditionally; `estado` only if that cell has a value for
  the row (blank leaves it unchanged — a bulk load must never silently
  deactivate someone by omission); `cupo_total` only if it actually
  differs from the current value.
- **Decision — how `cupo_total` changes affect `cupo_disponible`.** When
  a row's `cupo_total` differs from the stored value, `cupo_disponible`
  moves by the SAME delta, clamped to `[0, nuevo_total]` — the identical
  policy already used by the manual `PATCH /api/cupos/{id}` endpoint
  (extracted into one shared function,
  `cupo_service.ajustar_cupo_total`, so the two call sites can never
  drift apart). Raising a limit by $100,000 grants $100,000 more
  available credit; lowering it removes the same amount, never leaving
  `cupo_disponible` negative or above the new total.
- **An afiliado absent from the file is never touched** — no state
  (estado, cupo) changes for anyone not explicitly listed in that
  upload, by design.
- The response (`CargaMasivaResultado` — also used by the convenios and
  inventario bulk uploads below) reports `creados`/`actualizados`/
  `invalidos` counts **and** a per-row reason string for every invalid
  row (`errores: ["Fila 5: correo inválido o vacío", ...]`), not just an
  aggregate count.

## Bulk inventory upload across multiple convenios

`POST /api/inventario/carga-masiva` (new this pass, alongside the
existing `POST /api/inventario/carga?convenio_id=` for one
already-selected convenio) loads codes for SEVERAL convenios in one
file — each row names its own convenio by exact `nombre`, scoped to the
uploading admin's own cooperativa (never a client-supplied convenio_id).
A row is invalid if the convenio name doesn't match any convenio in that
cooperativa; a row is a duplicate (`omitidos`, not `invalidos` — it's not
a data problem to fix, just a no-op) if its `codigo` already exists
anywhere (`codigo` is globally unique, not per-convenio). Neither stops
the rest of the file from loading.

## Affiliate authentication

`POST /api/auth/afiliado/registro` lets an affiliate claim an account on
a roster row an administrator already loaded via `POST /api/afiliados`
or the bulk upload — it never creates a new `afiliados` row itself, and
only ever succeeds against a row with `password_hash IS NULL` and
`estado = true`.

**Design decision — identifying the cooperativa at registro time.**
`documento` is only unique *per cooperativa* (`UNIQUE (cooperativa_id,
documento)`), not globally, so `documento` alone cannot identify a single
row to claim. Rather than add a cooperativa-selector step to the
registration form or a cooperativa-id URL parameter, `/registro` requires
**both** `documento` and `correo` to match the same row. This was chosen
over the alternatives because:
- It needs no new UI step and no cooperativa directory/lookup endpoint
  (which would itself leak which cooperativas exist).
- It's information the affiliate already has (an admin loads both fields
  when creating the roster row) and doesn't require them to know or
  select an internal cooperativa identifier.
- Any mismatch — wrong `documento`, wrong `correo`, an already-claimed
  account, or an inactive affiliate — fails with the exact same generic
  `400` message, so this doesn't create a way to enumerate the roster by
  probing `documento`/`correo` combinations one field at a time.

`POST /api/auth/afiliado/login` authenticates by `correo` + password.
Because `correo` has no unique constraint, a login attempt that matches
more than one row (a real email collision across two cooperativas) is
treated as failed login (generic `401`), not resolved to "the first
match" — failing closed rather than guessing which affiliate is logging
in.

`GET /api/auth/afiliado/me` returns `AfiliadoOut`, which now includes
`cooperativa_nombre` (a simple join to `cooperativas.nombre` done when
building the response) so the affiliate portal can show which
cooperativa they belong to — no new public endpoint was needed for this.

`PATCH /api/afiliados/me` lets an affiliate update only `correo` and
`telefono` — `documento`, `nombres`, `apellidos`, `cooperativa_id`, and
`estado` stay under the cooperative's administration and are silently
ignored if present in the request body.

## The purchase flow

`POST /api/transacciones/comprar` (`app/services/transaction_service.py`)
runs as one atomic database transaction:

1. Loads and validates the convenio (own cooperativa only — 404 if not,
   never 403; must be active and within its `fecha_inicio`/`fecha_fin`
   window).
2. For `TARJETA`: calls the mock gateway (`app/services/payment_gateway.py`)
   **before touching any inventory or cupo**. A rejection is a
   deliberately **committed** outcome (`estado = RECHAZADA`) — a
   declined card is a real business event the admin transaction list is
   meant to show, not something to roll back and hide. `simular_rechazo`
   only ever has an effect outside production.
3. Selects and locks the needed `unidades_inventario` rows with
   `SELECT ... FOR UPDATE` so two concurrent purchases can never be
   handed the same unit; insufficient stock rolls back everything.
4. For `CUPO`: debits `cupo_disponible` directly (after locking units,
   so an insufficient balance rolls back the whole purchase, including
   the units just locked) and requires a base64 PNG signature, which is
   used to generate and store a debt-assumption document
   (`documentos_asuncion_deuda`) as one more step of the same
   transaction — never left half-created awaiting a later step.
5. Records an audit log entry (`usuario_admin_id = NULL`, affiliate/
   convenio/amount context inside `detalles` — see `../SCHEMA_NOTES.md`
   for why `logs_auditoria` has no affiliate-facing column at all).

`GET /api/tickets/me/{id}/descarga` re-verifies ownership via the
`transaccion_unidades` join on every request (never trusts a
client-supplied `transaccion_id`/`afiliado_id`) and renders the ticket
PDF fresh from the database on every call via
`app/services/pdf_service.generar_ticket()` — real, valid PDF bytes
today, with a visible "TICKET PROVISIONAL" placeholder banner until
per-brand templates are supplied. Swapping in a real per-brand generator
later means only changing the body of `generar_ticket`/
`generar_documento_asuncion_deuda` — no call site changes.

## File storage / activating Firebase later

`app/services/storage_service.py` already existed with a Firebase-ready
design and was reused as-is this pass, in its **local-disk fallback
mode** (`backend/storage_local/`, gitignored) — every business flow
(tickets, debt-assumption documents, signatures) goes through this one
module's `upload_bytes`/`download_bytes`, never `open()` or a raw path,
so enabling Firebase later touches only this module's configuration:

1. Set all four of `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`,
   `FIREBASE_PRIVATE_KEY`, and `FIREBASE_STORAGE_BUCKET` in `.env`
   (`FIREBASE_PRIVATE_KEY` with literal `\n` escapes, as Firebase service
   account JSON keys are normally stored).
2. Install `firebase-admin` (already imported lazily inside
   `storage_service.py`; add it to `requirements.txt` when you do this).
3. Nothing else — `_firebase_configured()` flips to `true` automatically
   and every subsequent `upload_bytes`/`download_bytes` call uses the
   real bucket instead of local disk. No router, service, or model code
   needs to change.

## Ticket templates (plantillas): content form, QR/barcode, and PDF generation

Before this round, `pdf_service.generar_ticket()` had no code path that
read the `plantillas` table at all — every convenio got an identical
generic ReportLab placeholder PDF regardless of what, if anything, was
registered against it. This section documents the real engine that
replaced that, and the content-authoring form built on top of it —
covering the 6 points explicitly requested for this round.

### 1. Required Jinja2 variables (exact, final list)

Defined once, in `app/services/template_engine.py::REQUIRED_VARIABLES`,
and enforced identically by both `POST /api/plantillas` (create) and
`POST /api/plantillas/preview`:

```
convenio           # dict: id, nombre, descripcion
items              # list[dict]: codigo, estado — the redeemable unit(s) this document covers
afiliado           # dict: nombres, apellidos, documento
transaccion_id     # int
fecha_emision      # str, ISO date — when this PDF was generated
fecha_vencimiento  # str | None — the convenio's fecha_fin, if it has one
```

An uploaded `.html` file missing ANY of these is rejected at upload time
with a message naming exactly which one(s) are missing (e.g. "A la
plantilla le falta la variable requerida: fecha_vencimiento."), never
silently accepted to fail later on the first real purchase.

**Additional, OPTIONAL variables** are always available too — a template
may reference any, all, or none of them:

```
qr_base64                    # real QR PNG (base64) encoding the official code — see point 5
barcode_base64                # real Code128 barcode PNG (base64) of the same code
logo_base64                    # the convenio/establishment logo the admin uploaded, if any
logo_cooperativa_base64        # the cooperativa's own logo, if the admin uploaded one
titulo_ticket, subtitulo, descripcion_beneficio, texto_informativo,
terminos_condiciones, restricciones, instrucciones_redencion
                                # the content-form fields — see point 4
```

### 2. Version activation — decision (unchanged since first introduced)

A new plantilla version is created **ACTIVE (`estado=true`) immediately**
on save. Rationale: the admin already renders and inspects a real PDF via
"Vista previa" before ever reaching "Guardar" — there's no separate
"upload, then review, then activate" step to build, since the review
already happened. The convenio's effective plantilla is always the
**highest-`version` row with `estado=true`** (`pdf_service._plantilla_activa`),
so a freshly-created version is immediately the one used for new tickets.
To roll back to an older version, deactivate the newer one(s) via
`PATCH /api/plantillas/{id}` (`estado: false`) — the lookup then falls
through to the next-highest still-active version, or to the generic
placeholder if none is active. `UNIQUE(convenio_id, version)` is enforced
by the pre-existing database constraint; the next version number is
always computed server-side (`MAX(version) + 1`), never client-supplied.

### 3. `storage_service` (unchanged — confirmed still current)

`app/services/storage_service.py` is unchanged this round and still works
exactly as documented above ("File storage / activating Firebase later"):
local-disk fallback today, a real Firebase bucket the moment the four
`FIREBASE_*` env vars are set, with every caller going through
`upload_bytes`/`download_bytes`/`generate_object_key` — never a raw path.
A plantilla's `storage_path` column still just points at "the one file
behind this version" — no schema change was made to support any of this
round's new content fields; see point 4.

### 4. What a plantilla stores now (content fields, logos)

`plantillas.storage_path` (an existing `TEXT` column, unchanged) points
at **one JSON file**, uploaded through `storage_service` like everything
else, containing:

```json
{
  "html": "<the real uploaded .html source, verbatim>",
  "logo_storage_path": "plantillas-logos/<cooperativa>/convenio/<id>/<uuid>.png",
  "logo_cooperativa_storage_path": "plantillas-logos-cooperativa/.../<uuid>.png",
  "titulo_ticket": "...", "subtitulo": "...", "descripcion_beneficio": "...",
  "texto_informativo": "...", "terminos_condiciones": "...",
  "restricciones": "...", "instrucciones_redencion": "..."
}
```

**No new PostgreSQL column or table was added.** The content fields
(título, descripción del beneficio, texto informativo, términos y
condiciones, restricciones, instrucciones de redención) and both logos'
storage references live inside this one JSON blob, exactly the same
storage mechanism `storage_path` already used for the plain-HTML format
two rounds ago and the visual-builder format one round ago — only the
file's content shape changed. `pdf_service.generar_ticket()` detects
which of the three formats a given plantilla uses (`"html"` key → current
round, `"elements"` key → previous round's visual builder, kept for
backward compatibility, no JSON at all → the oldest bare-HTML format) and
renders accordingly; none of them were deleted, so nothing already saved
stops working.

The admin fills these content fields in a real form (`ConvenioDetail.jsx`
→ `PlantillaBuilder.jsx`) — logo and HTML are real file uploads, never a
hand-typed path — and still uploads the real `.html`/Jinja2 design file,
which is free to reference any subset of the content fields above via
Jinja2 (`{{ terminos_condiciones }}`, `<img src="data:image/png;base64,{{ logo_base64 }}">`,
etc.).

**Validation before saving** (`template_engine.validar_y_renderizar`,
shared by create and preview so neither can drift from the other): real
HTML, valid Jinja2 syntax, every required variable present, AND an
actual successful WeasyPrint render with fixture data. A plantilla the
engine cannot render is never persisted — that would otherwise only
surface on the first real purchase, the worst possible moment.

**Permissions**: both `ADMIN` and `SUPER_ADMIN` can create/version/
preview/activate plantillas — `ADMIN` is always scoped to its own
cooperativa (`resolve_cooperativa_scope_write`; any `cooperativa_id` it
sends is ignored), `SUPER_ADMIN` must select one explicitly (400 if it
doesn't), and `LECTOR` is blocked from all of it (`require_write_access`).
This was already correct in the code before this round's audit — no fix
was needed, only a permission-matrix test suite added to prove it stays
that way (`tests/test_plantillas_upload.py`).

### 5. Full generation flow: PDF, QR, and barcode

```
Afiliado compra / admin descarga un ticket
        │
        ▼
pdf_service.generar_ticket(convenio, unidad, variables)
        │
        ├─ busca la plantilla activa (mayor versión, estado=true)
        │
        ├─ NO hay plantilla activa ──► placeholder genérico (ReportLab)
        │
        └─ SÍ hay plantilla activa
                │
                ├─ descarga el JSON (storage_service.download_bytes)
                ├─ construye el contexto: convenio/afiliado/items/fechas
                │      + template_engine.generar_qr_base64(unidad.codigo)
                │      + template_engine.generar_barcode_base64(unidad.codigo)
                │      + campos de contenido + logo(s) en base64
                ├─ renderiza el HTML real con Jinja2 (template_engine.renderizar_html)
                └─ WeasyPrint convierte el HTML final a bytes de PDF
```

**The code is never generated by BEET, never modified, never re-encoded.**
`unidad.codigo` — the official code the entity (Cine Colombia, Salitre
Mágico, etc.) supplied — flows unchanged from the database straight into
both `qrcode.make(codigo)` and `barcode.get_barcode_class("code128")(codigo, ...)`;
neither function receives anything else (no afiliado name, no document
number, no transaction id) — the QR/barcode encode only what's needed to
identify the ticket, nothing sensitive. This is verified by an automated
test (`test_codigo_oficial_llega_sin_modificar_al_qr_y_al_barcode`) that
generates the same code twice — once through the real pipeline, once
calling `qrcode` directly — and asserts the resulting PNG bytes are
byte-for-byte identical.

Whether a rendered ticket shows a QR, a barcode, both, or neither is
decided **entirely by which `<img>` tags the uploaded HTML references**
(`{{ qr_base64 }}` and/or `{{ barcode_base64 }}`) — there is no database
column or admin toggle for "QR vs barcode", by explicit design: showing
both for the same code is a rendering choice, never an implied
authorization of either format for redemption in an external system BEET
doesn't control.

### 6. "Convenio inactivo" vs "convenio activo" in dashboard/reportes

Deactivating a convenio (`PATCH /api/convenios/{id}` with `estado:
false` — a soft delete; there has never been a physical `DELETE` endpoint
for convenios, since a real one almost always already has
`unidades_inventario`/`transacciones`/`plantillas` rows with no
`ON DELETE CASCADE`) is distinguished from "active" in reports like this:

- **Counts of "how many convenios do you currently have"** (`dashboard.convenios_activos`,
  the admin convenios list's default view) filter `Convenio.estado.is_(True)`
  — an inactive convenio drops out of these immediately.
- **Sums of past activity** (`dashboard.ventas_del_mes`, `ahorro_generado`,
  `ventas_por_forma_de_pago`, and the `rendimiento-convenios` report) never
  filter by `Convenio.estado` — a sale made while the convenio was still
  active stays counted in these totals forever, even after deactivation.
  This was already true in the code before this round (verified, not
  assumed) — `tests/test_convenio_inactivo.py` adds regression coverage:
  it creates a completed sale, reads dashboard stats, deactivates the
  convenio, reads stats again, and asserts `convenios_activos` dropped by
  exactly 1 while `ventas_del_mes` is unchanged.
- **Selectors used to pick a convenio for a NEW action** (uploading
  inventory, in `InventarioGeneral.jsx`'s per-convenio table) now show a
  visible "Inactivo" badge next to a deactivated convenio's name — it's
  never hidden entirely, since its existing stock/history is still real
  data worth seeing, but it can no longer look indistinguishable from an
  active one.
- **Selectors used to filter HISTORICAL data** (the convenio dropdown in
  Reportes and in Transacciones) deliberately keep listing inactive
  convenios too — an admin needs to be able to look up a now-inactive
  convenio's past sales — but each inactive option is now labeled
  `"<nombre> (inactivo)"` so it's never confused with an active one.
- **The affiliate-facing catalog** (`GET /api/convenios/catalogo`) already
  excluded `estado=false` convenios before this round; confirmed still
  correct with a live browser test (deactivate → convenio disappears from
  the portal catalog immediately, no manual refresh needed) and a pytest
  regression (`test_convenio_desactivado_desaparece_del_catalogo_del_afiliado`).
- **The admin convenios list** now defaults to showing only active
  convenios (`useTableState`'s new optional `defaultFilters` parameter);
  the existing "Todo estado / Activo / Inactivo" selector still lets an
  admin bring inactive ones back into view — unchanged, just no longer
  the default.

## Real bugs found and fixed

### This pass

- **`usuarios_admin.cooperativa_id` was still `NOT NULL`**, despite being
  documented as already relaxed — same discrepancy pattern as
  `afiliados.password_hash` below: verified directly (`\d usuarios_admin`)
  before writing any code against it, then relaxed
  (`ALTER TABLE usuarios_admin ALTER COLUMN cooperativa_id DROP NOT NULL`),
  documented in a new Alembic migration for from-scratch builds — same
  `stamp`-not-`upgrade` rule against the real, already-patched database.
- **The estado filter (Activos/Inactivos) silently showed everyone when
  filtering for "Inactivos"** — this turned out to be a frontend bug, not
  a backend one (the backend's `estado: bool | None` query param already
  filtered correctly). The real cause: `frontend/src/hooks/useTableState.js`'s
  client-side filter used `if (value) rows = rows.filter(...)`, which
  treats `false` — a real, legitimate filter value (estado=false) — the
  same as "no filter set" (`undefined`/`''`). One shared hook, so the fix
  (`if (value !== undefined && value !== '')`) corrected every screen
  using it at once (afiliados, convenios, cupos), not just afiliados.
- **The report export buttons were a stub** — `Reportes.jsx`'s `exportar()`
  just showed a toast saying "Esta exportación aún no está conectada al
  backend." Replaced with real `GET .../exportar` endpoints returning
  actual `.xlsx` bytes.
- **Convenios bulk upload had a working backend endpoint from an earlier
  pass but ZERO frontend wiring** — no service function, no upload
  button, nothing — found while auditing every bulk-upload screen for
  the colored-feedback requirement. Added the missing service function
  and upload UI (`ConveniosList.jsx`), matching the existing
  afiliados/inventario pattern.
- **Report-export filenames were invisible to the frontend** — browsers
  hide every response header from cross-origin JavaScript except a small
  safelist by default, and `Content-Disposition` (which carries the
  server-generated dated filename) isn't in it. Fixed by adding
  `expose_headers=["Content-Disposition"]` to the CORS middleware config
  in `app/main.py`.

### Earlier passes

- **`afiliados.password_hash` was missing from the real database**,
  despite being the documented prerequisite for this phase — verified
  directly (`\d afiliados`) before writing any code against it, then
  added as a nullable, additive column
  (`ALTER TABLE afiliados ADD COLUMN password_hash character varying(255) NULL`),
  matching the exact pattern already used by `usuarios_admin`. Documented
  in the Alembic migration `8f3a1c2d9e10_add_afiliados_password_hash.py`.
  **This is the column whose absence later caused a real, confirmed
  production-shaped bug** — see "Database setup — IMPORTANT" above for
  the full write-up of how the previously-documented `alembic stamp head`
  workflow silently skipped this exact migration on a freshly restored
  database, and why `alembic upgrade head` (now idempotent) is the only
  command needed going forward.
- **A validation error could crash into an unhandled 500** —
  `app/main.py`'s `RequestValidationError` handler passed
  `exc.errors()` straight to `JSONResponse`, which uses plain
  `json.dumps` internally. Whenever a `@field_validator`/
  `@model_validator` raises a `ValueError` (e.g. `CompraRequest`
  requiring a signature for `CUPO` purchases, or `ConvenioBase`'s
  price/date checks), Pydantic's error list embeds the raw exception
  object under `errors[i]["ctx"]["error"]` — which `json.dumps` cannot
  serialize, turning a should-be-422 into a `TypeError` and an
  unhandled 500. Found via the new pytest suite (a cupo purchase
  missing its required signature). Fixed by running `exc.errors()`
  through FastAPI's `jsonable_encoder` before it reaches
  `JSONResponse`, which was the only change needed.

## Error handling

Unchanged from the original design: validation errors return 422 with
Pydantic's own safe field messages, `HTTPException`s pass through as
written, and every other exception is logged server-side and returned as
a generic `{"detail": "Ocurrió un error interno..."}` (500) — no SQL
error, stack trace, password hash, or secret ever reaches a response
body.
