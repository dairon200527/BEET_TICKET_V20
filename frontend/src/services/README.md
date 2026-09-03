# Frontend service layer (real backend calls)

Every page in this app — both the admin panel and the affiliate portal —
calls the real FastAPI backend in `../../../backend` through this
directory. There is no mock data layer: no fake data is fabricated
anywhere, including in the affiliate portal (see below for why some of
its calls currently fail — that's a real, documented backend gap, not a
mock standing in for one). `src/utils/format.js` — pure formatting
utilities (`formatCOP`, `formatDate`, etc.), not data — is the only
non-service, non-page module every screen shares.

## What's here

- `apiClient.js` — fetch wrapper: base URL from `VITE_API_URL` (see
  `../../.env.example`), JSON handling, error normalization, and **two
  entirely separate token stores** (`admin` and `afiliado`) mirroring the
  backend's disjoint JWT identity spaces — never mixed, never used to
  infer a role client-side. It also clears a token and fires a
  `beetticket:session-expired` event when the backend rejects it (401),
  which `AuthContext`/`AffiliateAuthContext` listen for to log the user
  out immediately instead of leaving a stale "authenticated" UI around a
  dead session.
- `authService.js` — admin login (real, working) + affiliate
  login/register/forgot/reset-password (real calls, but the backend
  routes they hit are not currently mounted/functional — see
  `../README.md`'s "Backend endpoints this portal expects").
- `afiliadosService.js`, `convenioService.js`, `plantillasService.js`,
  `inventarioService.js`, `cuposService.js`, `transaccionesService.js`,
  `documentosService.js`, `adminService.js`, `dashboardService.js`,
  `reportesService.js` — one module per backend router, used by the
  corresponding pages. The affiliate-scoped functions in
  `afiliadosService.js` (`miPerfilAfiliado`, `actualizarMiPerfilAfiliado`),
  `cuposService.js` (`miCupo`), and `convenioService.js`
  (`obtenerCatalogoAfiliado`) call endpoints that exist in code intent but
  are not currently mounted on the running backend — see `../README.md`.
- `ticketsService.js` — kept for a future phase (tickets viewing); not
  called by any currently-mounted page.

## Known real gaps — admin panel (backend doesn't expose this yet)

- **No affiliate-facing stock-count endpoint.** `GET /api/inventario/resumen`
  requires an admin token.
- **No aggregate "cupo consumido across all affiliates" endpoint** — the
  admin dashboard/reportes screens say so explicitly instead of computing
  a number client-side.
- **No fecha de vencimiento per inventory unit** — the real schema only
  has `fecha_ingreso`; the dashboard's "próximas a vencer" KPI was
  replaced with "convenios por vencer" (based on `convenios.fecha_fin`).

## Known real gaps — affiliate portal (see ../README.md for full detail)

The entire affiliate-facing API surface (login, `/me` profile, `/me` cupo,
convenio catalog) either doesn't exist as a mounted route or is
architecturally blocked (`afiliados` has no `password_hash` column). The
frontend pages/services are built and ready to call these endpoints
exactly as a real affiliate portal would need — nothing here fabricates a
substitute response.

## Security note

The admin panel's dev-only role switcher was removed entirely — it shows
the authenticated admin's real role (`AdminOut.rol`) as a read-only badge,
with no client-side mechanism to change it. Every request is authorized
from the database on the backend, never from anything the client sends.
