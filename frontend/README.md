# BEET Ticket — Panel administrativo + Portal del afiliado (frontend)

Frontend en React + Vite de BEET Ticket. Incluye **dos experiencias separadas** que comparten la misma identidad visual, **ambas totalmente conectadas al backend real**:

- **Panel administrativo** (`/`, `/login`, …) — usado por la cooperativa.
- **Portal del afiliado** (`/portal/*`) — usado por los afiliados: registro, login, perfil (editable), catálogo, compra de beneficios (tarjeta o cupo con firma), y descarga de tickets en PDF real. Layout, navegación y sesión completamente independientes del panel administrativo.

La única pantalla que sigue sin conectar es la de documentos de asunción de deuda del propio afiliado (`MyDocuments.jsx`/`DocumentDetail.jsx`, no montadas en `App.jsx`) — el backend solo expone un listado de solo lectura para administradores (`GET /api/documentos`), no un endpoint de descarga para el afiliado propietario del documento.

## Cómo correr

```bash
npm install
cp .env.example .env   # VITE_API_URL=http://127.0.0.1:8000 por defecto
npm run dev             # http://localhost:5173
npm run build
npm run lint
```

Requiere que el backend (`../backend`) esté corriendo — ver su propio README para instrucciones.

**No hay usuario ni sesión de ejemplo.** El panel administrativo (`/login`) solo acepta credenciales reales que existan en la base de datos PostgreSQL del backend — ver `../README.md` para las tres cuentas de prueba de administrador. El portal del afiliado (`/portal/login`) también solo aceptaría credenciales reales, pero **hoy no hay ninguna cuenta de afiliado que pueda iniciar sesión** (ver más abajo) — no hay autologin, no hay selector de rol funcional, no hay cuenta de prueba fabricada.

## Estructura

```
src/
  styles/                tokens.css (paleta, tipografía, espaciado) + global.css
  components/ui/         biblioteca de componentes compartida (Button, Field, Card, Badge,
                          Table, Modal, Stepper, SignaturePad, ...) — usada por ambas experiencias
  components/layout/      AdminLayout, Sidebar, Header, breadcrumbs, RequireAuth, RequireAffiliateAuth
  components/portal/      PortalLayout, PortalHeader, PortalBottomNav, BenefitCard, portal.css
  context/                AuthContext (admin: sesión real vía JWT), AffiliateAuthContext (afiliado: sesión real vía JWT),
                          ToastContext
  services/                cliente HTTP real hacia el backend FastAPI — ver services/README.md
  utils/                   format.js (formateo puro: moneda, fechas — sin datos), roles.js (vocabulario de roles admin)
  hooks/                   useTableState, useMiCupo, useRecentActivity
  pages/
    Login.jsx, Dashboard.jsx
    admin/convenios | inventario | afiliados | cupos | transacciones | reportes | usuarios | configuracion
    portal/                PortalLogin, PortalHome (dashboard), Profile (perfil, solo lectura),
                           MiCupo, Catalogo, BenefitDetail (solo lectura) — las únicas rutas de
                           /portal montadas en App.jsx esta pasada
```

**Archivos de `pages/portal/` que existen pero NO están montados en `App.jsx`**: `MyDocuments.jsx`, `DocumentDetail.jsx` — el backend no expone un endpoint de descarga de documentos de asunción de deuda para el propio afiliado (solo un listado de solo lectura para administradores). Quedan como scaffolding para una fase futura que sí agregue ese endpoint.

## El portal del afiliado — todo conectado al backend real

- **Activar cuenta** (`/portal/registro`, título en pantalla "Activa tu cuenta") — llama a `POST /api/auth/afiliado/registro` con `documento` + `correo` + password. Ambos campos son obligatorios porque `documento` solo es único *por cooperativa*, no globalmente — ver `../backend/README.md` para el detalle completo de esta decisión de diseño. El texto/copy se cambió de "Crear cuenta" a "Activa tu cuenta" (título, botón, mensajes) para reflejar correctamente que no se crea un afiliado nuevo — se activa el acceso a una fila que un admin ya cargó; el comportamiento del endpoint no cambió. El checkbox de "Acepto los términos y condiciones" se valida solo en el cliente — no existe una columna en `afiliados` para registrar esa aceptación, así que nunca se envía al backend.
- **Login** (`/portal/login`) — `POST /api/auth/afiliado/login` (correo + password).
- **Dashboard** (`/portal`) — saludo con el nombre real del afiliado, resumen de datos personales, cupo de crédito, y beneficios destacados desde el catálogo.
- **Mi perfil** (`/portal/perfil`) — nombres, apellidos, documento, correo, teléfono, **nombre de la cooperativa** (no solo su id — `AfiliadoOut.cooperativa_nombre`), estado. Botón "Editar datos de contacto" lleva a `/portal/perfil/editar`, que llama a `PATCH /api/afiliados/me` (solo correo/teléfono — nombres, apellidos, documento y estado los sigue administrando la cooperativa).
- **Mi cupo** (`/portal/cupo`) — cupo total, cupo disponible (`cupo_disponible`, el saldo real, no un monto "usado" acumulado — ver `../SCHEMA_NOTES.md`), estado.
- **Beneficios / Convenios** (`/portal/catalogo`, `/portal/catalogo/:id`) — catálogo real, con un botón real "Comprar este beneficio" que lleva a `/portal/comprar/:id`.
- **Comprar** (`/portal/comprar/:id`) — flujo completo contra `POST /api/transacciones/comprar`: cantidad, forma de pago (tarjeta o cupo), firma digital (solo cupo, capturada con `SignaturePad`, enviada como PNG en base64), resumen, y resultado. Una tarjeta rechazada por la pasarela simulada es un resultado exitoso de la llamada (HTTP 201, `estado: "RECHAZADA"`) — se distingue explícitamente de una compra completada, no se confunde con un error de red.
- **Mis tickets** (`/portal/tickets`, `/portal/tickets/:id`) — lista real de unidades compradas y descarga de un PDF real (`GET /api/tickets/me/{id}/descarga`, que devuelve bytes `application/pdf` directamente, no una URL). El frontend convierte la respuesta en un `Blob` (`apiClient.getBlob`) y lo abre con `URL.createObjectURL` — la descarga JSON-con-URL que tenía la versión anterior no aplica más.

Todas las pantallas manejan estados de carga, error y vacío sin exponer errores internos del backend. Diseño responsive reutilizando los componentes y la identidad visual existentes.

**Bug real encontrado y corregido**: `PortalHome.jsx` ("Mi información") mostraba `#{cooperativa_id}` (un número) en vez del nombre real de la cooperativa, con un comentario explicando que el endpoint no lo exponía — comentario que ya estaba desactualizado, porque `AfiliadoOut.cooperativa_nombre` se agregó en una pasada anterior y `Profile.jsx` ya lo usaba correctamente. Corregido para usar `afiliado.cooperativa_nombre` igual que el resto del portal.

## Panel administrativo — cambios de esta pasada

- **Usuarios** (`/usuarios`, solo visible/gestionable por `SUPER_ADMIN`): el formulario de "Crear usuario" ahora tiene un selector de cooperativa, obligatorio para los roles `ADMIN`/`LECTOR` (oculto/no aplicable para `SUPER_ADMIN`, que administra todas). La tabla muestra la columna "Cooperativa" y hay un filtro por cooperativa arriba de la tabla — antes el listado no distinguía a qué cooperativa pertenecía cada usuario.
- **Afiliados** (`/afiliados`): el modal "Cargar afiliados" ahora es un upsert real (documento existente → actualiza; nuevo → crea, junto con su cupo de crédito vía la nueva columna `cupo_total` del Excel) y muestra el resultado con color (verde/rojo, componente `Alert` reutilizado) incluyendo el motivo de cada fila inválida. El botón "Exportar" (antes sin `onClick`, no hacía nada) ahora descarga un `.xlsx` real.
- **Convenios** (`/convenios`): se agregó el botón "Cargar convenios" — el endpoint de carga masiva ya existía en el backend desde una pasada anterior, pero **no tenía ninguna conexión en el frontend** (ni servicio, ni botón); se conectó igual que afiliados/inventario, con el mismo feedback de color.
- **Inventario** (`/inventario`): nueva sección "Carga masiva de inventario (varios convenios a la vez)" — sube un Excel con columnas `convenio, codigo` y crea unidades en varios convenios distintos según el nombre de cada fila, a diferencia de la carga por convenio ya existente (que sigue funcionando igual, ahora también con feedback de color y motivo por fila).
- **Reportes** (`/reportes`): los botones de exportar ya no muestran "Esta exportación aún no está conectada al backend" — descargan `.xlsx` reales (rendimiento por convenio, afiliados con cupo).
- **Cerrar sesión**: tanto en el panel administrativo como en el portal del afiliado, ahora pide confirmación ("¿Cerrar sesión?" / Cancelar / Cerrar sesión) antes de destruir la sesión — antes cerraba sesión de inmediato al hacer clic.
- **Header del panel admin**: se quitó un cuadro de búsqueda (`input` sin `value`/`onChange`, no hacía absolutamente nada al escribir o dar enter) que estaba oculto en pantallas angostas y aparecía sin funcionar en pantallas anchas.
- **Bug real encontrado y corregido**: filtrar cualquier listado (afiliados, convenios, cupos) por "Inactivos" mostraba TODOS los registros, no solo los inactivos. La causa era el hook compartido `hooks/useTableState.js`, que trataba el valor de filtro `false` igual que "sin filtro" — corregido una sola vez en el hook, lo que arregla las tres pantallas a la vez.

## Selector persistente de cooperativa (SUPER_ADMIN) — pasada más reciente

Un `SUPER_ADMIN` ahora puede ver y gestionar los datos de **cualquier**
cooperativa (afiliados, convenios, inventario, cupos, transacciones,
reportes, dashboard), pero nunca de forma implícita ni mezclada entre
cooperativas — ver `../backend/README.md` para el detalle del backend
(`resolve_cooperativa_scope`). `ADMIN`/`LECTOR` no cambian en nada: siguen
atados de forma fija a su propia cooperativa, sin selector.

- **`context/CooperativaContext.jsx`** (nuevo): mantiene qué cooperativa
  tiene seleccionada un `SUPER_ADMIN`. Persistida en `sessionStorage`
  (no `localStorage`) — sobrevive un refresh de página pero no una
  sesión nueva del navegador, para que un `SUPER_ADMIN` que vuelve más
  tarde tenga que reconfirmar explícitamente sobre qué cooperativa está
  operando, en vez de retomar en silencio una selección de hace días.
  Para `ADMIN`/`LECTOR` este contexto queda inerte (`isSuperAdmin: false`,
  `selected: null`).
- **`services/apiClient.js`**: nuevo `cooperativaScopeStore` (mismo patrón
  que `adminTokenStore`) — cuando hay una cooperativa seleccionada, TODA
  request admin-scoped le agrega automáticamente `?cooperativa_id=`,
  sin que cada pantalla o servicio tenga que pasarlo a mano. Para
  `ADMIN`/`LECTOR` nunca hay nada en el store, así que nunca se agrega
  (el backend lo ignoraría de todos modos).
- **`components/layout/Header.jsx`**: nuevo selector (`<select>`) visible
  solo para `SUPER_ADMIN`, junto al badge de rol — lista las
  cooperativas reales vía `GET /api/admin/cooperativas`. Cambiar la
  selección dispara un refetch inmediato en la pantalla activa (cada
  pantalla depende del `selectedId` del contexto en su efecto de carga).
- **`components/layout/RequireCooperativaSeleccionada.jsx`** (nuevo):
  wrapper de estado vacío ("Selecciona una cooperativa arriba para ver
  esta información") usado en las 7 pantallas afectadas — Dashboard,
  Convenios, Inventario, Afiliados, Cupos de crédito, Transacciones,
  Reportes. Mientras un `SUPER_ADMIN` no haya seleccionado nada, esas
  pantallas NUNCA cargan datos de la primera cooperativa por defecto ni
  mezclan varias — simplemente no piden nada al backend.
- En las pantallas de carga masiva/creación manual (Afiliados, Convenios,
  Inventario), el botón de subir/crear queda **deshabilitado** (no solo
  falla al hacer clic) mientras no haya cooperativa seleccionada, y junto
  al formulario aparece "Estás gestionando datos de: {nombre}" para que
  sea visualmente imposible subir un Excel sin saber a cuál cooperativa
  va a parar.
- **Usuarios** (`/usuarios`): nuevo botón "Crear cooperativa" (antes no
  existía ni el endpoint ni la pantalla — ver `../backend/README.md`)
  junto a "Crear usuario". Al crear una cooperativa, se refresca tanto el
  filtro local de esta pantalla como el selector persistente del Header,
  para que la cooperativa nueva aparezca de inmediato en ambos sin tener
  que recargar la página.
- **Bug real encontrado y corregido durante esta pasada**: al navegar a
  una URL directa (o refrescar la página) con una cooperativa ya
  seleccionada, `CooperativaContext` la borraba — porque su efecto
  trataba "todavía verificando la sesión" (`AuthContext.isCheckingSession`,
  momento en que `isAuthenticated` es `false` incluso para una sesión
  real) igual que "no es SUPER_ADMIN", y limpiaba `sessionStorage` de
  inmediato. Corregido para que el efecto no toque nada mientras la
  sesión se está verificando.

Ver `src/services/README.md` para el detalle completo de cada servicio.
