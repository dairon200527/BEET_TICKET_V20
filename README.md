# BEET Ticket

The full BEET Ticket project — admin/back-office panel **and** affiliate
portal, both connected to the **real PostgreSQL database** (restored from
the provided `beet_ticket.backup`) and a real FastAPI backend. This
covers four passes:

1. Admin module integration against the real database.
2. Affiliate portal frontend (built ahead of the backend that would
   support it).
3. Real affiliate authentication, convenios bulk upload, the full
   purchase flow (card + cupo/credit-quota payment), real PDF ticket
   generation, and wiring the affiliate frontend to all of it.
4. **This pass**: multi-tenant `usuarios_admin` (a `SUPER_ADMIN`
   administers every cooperativa, explicitly assigns one when creating
   an `ADMIN`/`LECTOR`), the afiliados bulk upload rebuilt as a real
   upsert with a `cupo_total` column, bulk inventory upload across
   multiple convenios, real `.xlsx` report exports, and a round of admin
   UX fixes (logout confirmation, a dead search box removed, a
   client-side filter bug affecting every "Inactivos" filter in the
   app).

File storage still runs in local-disk fallback mode — real Firebase
credentials are deliberately not configured yet; see
`backend/README.md`, "File storage / activating Firebase later", for
exactly what changes when they are.

```
BEET-TICKET-integrated/
├── frontend/            # React + Vite — admin panel (connected) + affiliate portal UI (built, not yet connected — see below)
├── backend/             # FastAPI + SQLAlchemy + PostgreSQL + Pydantic
├── SCHEMA_NOTES.md        # the real 11-table schema, column by column
└── README.md              # this file
```

## Requirements

- **PostgreSQL** (any recent version; developed/verified against PostgreSQL 16), with the `beet_ticket.backup` dump you were given already restored into it.
- **Python 3.11 or 3.12**
- **Node.js 18+** and npm

## 1. Database setup

Restore the provided backup into a real, named `beet_ticket` database —
do **not** create a different throwaway database and do **not** skip this
step; the application does not create its own schema against a fresh
database in normal operation.

```bash
psql -U postgres -c "CREATE DATABASE beet_ticket OWNER postgres;"
psql -U postgres -d beet_ticket -f /path/to/beet_ticket.backup
```

Verify it worked:

```bash
psql -U postgres -d beet_ticket -c "\dt"
# should list exactly 11 tables: cooperativas, usuarios_admin, afiliados,
# convenios, plantillas, unidades_inventario, cupos_credito, transacciones,
# transaccion_unidades, documentos_asuncion_deuda, logs_auditoria
```

## 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `backend/.env`:

```
DATABASE_URL=postgresql+psycopg2://postgres:<PASSWORD>@localhost:5432/beet_ticket
JWT_SECRET=<generate one: python -c "import secrets; print(secrets.token_urlsafe(64))">
CORS_ORIGINS=http://localhost:5173
ENVIRONMENT=development
```

Replace `<PASSWORD>` with your real local PostgreSQL password. **Never
commit `.env`** — it's already in `.gitignore`.

Then run the migrations:

```bash
alembic upgrade head
```

**This is now the ONLY command you ever need here — always `upgrade
head`, never `stamp head`.** Earlier versions of this README told you to
run `alembic stamp head` after restoring the backup, reasoning that your
database "already had" the 11 tables. That advice was wrong and has been
removed: `stamp head` marks *every* migration as applied without running
any of their SQL, which silently skipped the two migrations that add
`afiliados.password_hash` and make `usuarios_admin.cooperativa_id`
nullable — columns the restored backup does not include. The real-world
symptom was affiliate account activation
(`POST /api/auth/afiliado/registro`) failing outright, because the code
was writing to a column that, on a freshly restored database, did not
exist. The initial migration (`alembic/versions/26b8314392ca_*.py`) now
detects on its own whether the 11 tables already exist and skips only its
own `CREATE TABLE` calls when they do — so `alembic upgrade head` is
correct and safe whether you restored the backup or are provisioning a
genuinely empty database. See `backend/README.md` for the full write-up.

Create the three required test admin accounts:

```bash
python -m scripts.seed_admin_users
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend runs at **http://localhost:8000** (interactive docs at
`http://localhost:8000/docs`).

## 3. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env    # VITE_API_URL=http://localhost:8000 by default
npm run dev
```

Frontend runs at **http://localhost:5173**.

## 4. Log in

Go to `http://localhost:5173/login` and sign in with any of the three
test accounts below.

## Test admin accounts

Created by `python -m scripts.seed_admin_users` (backend step above),
with Argon2-hashed passwords — never stored or returned in plaintext:

| Role | Correo | Password |
|---|---|---|
| **SUPER_ADMIN** | `superadmin@beetticket.test` | `SuperAdmin123!` |
| **ADMIN** | `admin@beetticket.test` | `Admin123!` |
| **LECTOR** | `lector@beetticket.test` | `Lector123!` |

## Roles & permissions

- **SUPER_ADMIN** — full access: everything ADMIN can do, plus creating/managing other admin users and editing cooperativa configuration.
- **ADMIN** — full read/write on afiliados, convenios, plantillas, inventario, cupos; can edit cooperativa configuration; cannot manage other admin users.
- **LECTOR** — read-only everywhere; every mutating endpoint (POST/PATCH) returns 403.

Authorization is enforced entirely server-side, re-derived from the
database on every request (never from the JWT's claims beyond identity,
and never from anything the frontend sends) — see `backend/README.md`.

## What was integrated this pass

The backend's models, Pydantic schemas, routers, dependencies, audit
service, Alembic migration, and test suite were all rewritten to match
the real database schema exactly (see `SCHEMA_NOTES.md` for the full
column-by-column diff against the backend's earlier, incorrect
assumptions). The frontend's admin screens (login, dashboard, nav,
afiliados, convenios, plantillas, inventario, cupos, transacciones,
documentos, usuarios, configuración, reportes) were updated to match the
adjusted API contracts — real field names, real boolean `estado` values,
real uppercase role/status vocabularies.

A real bug was found and fixed during live end-to-end testing in that
earlier pass: SQLAlchemy's `Enum` column type reads/writes a Python
enum's *name*, not its *value*, by default — `unidades_inventario.estado`'s
enum has uppercase names (`DISPONIBLE`) mapped to lowercase database
values (`disponible`), which crashed every read of that column with a
`LookupError` until `values_callable` was added to the column definition
(`backend/app/models/unidad_inventario.py`).

A later pass found two more real issues — see `backend/README.md`,
"Real bugs found and fixed" → "Earlier passes", for the full detail: the
`afiliados.password_hash` column documented as already present was
actually missing from the real database (added, additively, after
verifying with `\d afiliados`); and a `RequestValidationError` whose
cause was a `@model_validator`/`@field_validator`-raised `ValueError`
(e.g. a cupo purchase missing its required signature) crashed into an
unhandled 500 instead of a 422, because `app/main.py`'s exception handler
passed Pydantic's raw error list straight to `json.dumps` — fixed by
running it through FastAPI's `jsonable_encoder` first.

## This pass: multi-tenant usuarios_admin, real bulk-upload upserts, exports, UX fixes

- **`usuarios_admin.cooperativa_id` is now nullable** — a `SUPER_ADMIN`
  administers every cooperativa rather than belonging to one; `ADMIN`/
  `LECTOR` still always require it (enforced at the application layer).
  The **Usuarios** screen now has a cooperativa selector when creating a
  user and a cooperativa filter/column on the listing — see
  `backend/README.md`, "Multi-tenancy for usuarios_admin".
- **Afiliados bulk upload is now a real upsert**, with a new required
  `cupo_total` column that creates/adjusts the affiliate's credit quota
  in the same pass — see `backend/README.md`, "The afiliados bulk
  upload is now a real upsert", for the exact `cupo_disponible`
  delta-adjustment policy (a decision made without asking mid-task, per
  explicit instruction, and documented there).
- **Bulk inventory upload across multiple convenios in one file**
  (`POST /api/inventario/carga-masiva`) — a new button on the
  **Inventario** screen.
- **Real `.xlsx` report exports** — the "Excel/PDF" buttons on
  **Reportes** were previously a stub; **Afiliados** also had a
  completely dead "Exportar" button, now wired to the same export.
- **UX**: a confirmation modal before logging out (admin panel and
  affiliate portal), colored success/error feedback (reusing the
  existing `Alert` component) on every bulk-upload result with a
  per-row reason for each invalid row, and a dead, non-functional
  search box removed from the admin header.
- **A real, cross-screen bug found and fixed**: filtering any admin list
  by "Inactivos" silently showed every row (active and inactive alike).
  The cause was a shared frontend hook (`useTableState.js`) treating the
  filter value `false` the same as "no filter set" — see
  `backend/README.md`, "Real bugs found and fixed" → "This pass", for
  the full detail. Fixed once in the shared hook, correcting every
  screen that uses it (afiliados, convenios, cupos) at the same time.

## The affiliate portal (now fully connected)

The affiliate frontend built in an earlier pass — dashboard, profile,
credit-quota ("mi cupo"), benefits catalog — is now connected to a real,
working backend:

- **Registro / login** (`/portal/registro`, `/portal/login`) against
  `POST /api/auth/afiliado/registro` / `login` — see `backend/README.md`
  for the design decision behind how `/registro` identifies which
  cooperativa a registering affiliate belongs to.
- **Editable profile** (`/portal/perfil/editar`) — correo/telefono only.
- **Purchasing a benefit** (`/portal/comprar/:id`) — card (mock gateway)
  or cupo/credit-quota with a captured signature — and **Mis tickets**
  (`/portal/tickets`, `/portal/tickets/:id`) with a real, downloadable
  PDF ticket.

Not connected: a download screen for the debt-assumption document
generated during a cupo purchase — the backend only exposes an
admin-facing, read-only listing of these (`GET /api/documentos`), not an
affiliate-facing download endpoint, so `MyDocuments.jsx`/`DocumentDetail.jsx`
remain unrouted scaffolding (see `backend/README.md`, "Scope of this
pass").

## What's NOT implemented (by design)

- **Real Firebase Storage credentials** — deliberately deferred to the
  end of the project; the storage abstraction is fully wired and working
  in local-disk mode. See `backend/README.md`.
- **A real card payment gateway** — a deterministic mock behind the same
  interface a real provider would implement.
- **Password recovery / email delivery** — no email provider is
  configured, for admin or affiliate.
- **Affiliate-facing download of the debt-assumption document** — see
  "The affiliate portal" above.
- **Production deployment/infrastructure** — this is a local development
  setup only.

## Security notes

- Passwords are never stored or returned in plaintext (Argon2 hashing,
  `password_hash` never appears in any API response).
- JWT secret, database credentials, and all other secrets are read
  exclusively from environment variables — never hardcoded, never
  committed (`.env` is gitignored; only `.env.example` with placeholders
  is included).
- CORS origins are configured via `CORS_ORIGINS` — never a wildcard in
  production (the backend refuses to start with `*` in production).
- Every admin endpoint re-verifies identity, role, and cooperativa
  ownership against the database on every request.

## Testing this yourself

```bash
# Backend tests — point at a SEPARATE, disposable database, never at
# beet_ticket itself (the test suite drops/recreates the schema and
# truncates every table between tests):
createdb beet_ticket_test
cd backend && DATABASE_URL=postgresql+psycopg2://postgres:<PASSWORD>@localhost:5432/beet_ticket_test pytest -q

# Frontend build/lint:
cd frontend && npm run build && npm run lint
```

All of the above were run against this exact codebase before delivery.
The backend was additionally started against the real, restored
`beet_ticket` database and exercised end-to-end in a real browser via
Playwright: admin login for all three roles + every admin screen
(regression), plus the full new affiliate journey — registro against an
existing roster row, login, seeing the cooperativa name and catalog,
buying a benefit with the mock card gateway, buying a second one with
cupo + a drawn signature (verified against the real
`documentos_asuncion_deuda` row and its generated PDF/PNG on disk), and
downloading a real PDF ticket. This created real rows in the `beet_ticket`
database (one claimed affiliate account, two completed transactions,
their generated documents) — nothing was deleted or rolled back
afterward, since it's real, valid business data, not test debris.

**This pass's live E2E run** additionally exercised, against the same
real database (a second cooperativa, "Cooperativa Norte", was created —
the platform's normal way of onboarding a new client cooperativa — since
demonstrating cross-cooperativa scoping needs at least two to exist):
creating an `ADMIN` from the `SUPER_ADMIN` account and assigning it to
Cooperativa Norte, filtering the usuarios listing by cooperativa,
confirming that new `ADMIN` sees an empty afiliados/convenios list (real
tenant isolation, not just an assertion), uploading an afiliados Excel
with a `cupo_total` column twice — the second upload with different
values — confirming the second run updates in place rather than
duplicating or skipping, uploading a multi-convenio inventory Excel,
confirming the Activos/Inactivos filter actually filters, downloading a
real `.xlsx` report export, the logout confirmation modal (cancel, then
confirm) on both the admin panel and the affiliate portal, and
activating/logging into an affiliate account that was loaded via Excel
with a cupo, confirming they land with the exact real cupo from that
file (not zero) — ready to buy.
