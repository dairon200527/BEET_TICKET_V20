// Thin fetch wrapper for the FastAPI backend. Additive only — see
// ./README.md for why nothing else in the app imports this yet.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Two entirely separate token stores, mirroring the backend's disjoint
// admin/afiliado JWT spaces (app/dependencies/auth.py). Never mix them —
// an admin token must never be sent to an affiliate endpoint or vice versa.
const ADMIN_TOKEN_KEY = "beetticket_admin_token";
const AFILIADO_TOKEN_KEY = "beetticket_afiliado_token";

export const adminTokenStore = {
  get: () => localStorage.getItem(ADMIN_TOKEN_KEY),
  set: (token) => localStorage.setItem(ADMIN_TOKEN_KEY, token),
  clear: () => localStorage.removeItem(ADMIN_TOKEN_KEY),
};

export const afiliadoTokenStore = {
  get: () => localStorage.getItem(AFILIADO_TOKEN_KEY),
  set: (token) => localStorage.setItem(AFILIADO_TOKEN_KEY, token),
  clear: () => localStorage.removeItem(AFILIADO_TOKEN_KEY),
};

// The cooperativa a SUPER_ADMIN has explicitly selected (see
// CooperativaContext). ADMIN/LECTOR never write here — the backend
// ignores this param for them anyway (see resolve_cooperativa_scope in
// app/dependencies/auth.py), but not sending it for those roles keeps
// requests honest about what actually matters.
//
// sessionStorage, not localStorage: it should survive a page refresh
// (so reloading mid-task doesn't drop the selection) but NOT persist
// into a brand-new browser session/tab — a SUPER_ADMIN coming back
// later should have to re-confirm which cooperativa they're operating
// on, rather than silently resuming one from days ago.
const COOPERATIVA_SCOPE_KEY = "beetticket_superadmin_cooperativa_id";

export const cooperativaScopeStore = {
  get: () => sessionStorage.getItem(COOPERATIVA_SCOPE_KEY),
  set: (id) => sessionStorage.setItem(COOPERATIVA_SCOPE_KEY, String(id)),
  clear: () => sessionStorage.removeItem(COOPERATIVA_SCOPE_KEY),
};

// `skipCooperativaScope` exists for the handful of SUPER_ADMIN endpoints
// that are cross-cooperativa BY DESIGN (usuarios/cooperativas management —
// see app/routers/admin.py) — without it, this function used to silently
// inject the header's SELECTED cooperativa into those requests too,
// which is wrong for them specifically: a usuario belonging to any OTHER
// cooperativa (or a SUPER_ADMIN with no cooperativa at all) would just
// vanish from the list depending on whatever happened to be selected in
// the unrelated persistent header selector, looking exactly like a
// create/delete-not-refreshing bug when the row was never fetched at all.
function withCooperativaScope(path, tokenAudience, skipCooperativaScope) {
  if (tokenAudience !== "admin" || skipCooperativaScope) return path;
  const cooperativaId = cooperativaScopeStore.get();
  if (!cooperativaId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}cooperativa_id=${encodeURIComponent(cooperativaId)}`;
}

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * @param {string} path e.g. "/api/convenios"
 * @param {"admin"|"afiliado"|null} tokenAudience which token store (if any) to attach
 */
async function request(
  path,
  { method = "GET", body, tokenAudience = null, isFormData = false, skipCooperativaScope = false } = {}
) {
  const headers = {};
  if (!isFormData) headers["Content-Type"] = "application/json";

  if (tokenAudience === "admin") {
    const token = adminTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  } else if (tokenAudience === "afiliado") {
    const token = afiliadoTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  path = withCooperativaScope(path, tokenAudience, skipCooperativaScope);

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  // A 204 (or any response with no body, e.g. Content-Length: 0) must
  // never reach .json()/.text() — FastAPI's default JSONResponse class
  // sets "Content-Type: application/json" on the headers even when the
  // body is empty, so relying on content-type alone here would call
  // response.json() on zero bytes and throw "Unexpected end of JSON
  // input" on an otherwise-successful request (e.g. DELETE .../{id}).
  const contentLength = response.headers.get("content-length");
  const hasNoBody = response.status === 204 || contentLength === "0";
  const contentType = response.headers.get("content-type") || "";
  const data = hasNoBody
    ? null
    : contentType.includes("application/json")
      ? await response.json()
      : await response.text();

  if (!response.ok) {
    const detail = typeof data === "object" && data !== null ? data.detail : data;

    if (response.status === 401 && tokenAudience) {
      // The token we sent was rejected (expired/invalid/deactivated user).
      // Clear it and let listeners (AuthContext) react — e.g. redirect to
      // login — instead of leaving the app in a stuck authenticated-looking
      // state that just keeps failing.
      (tokenAudience === "admin" ? adminTokenStore : afiliadoTokenStore).clear();
      window.dispatchEvent(new CustomEvent("beetticket:session-expired", { detail: { tokenAudience } }));
    }

    throw new ApiError(
      typeof detail === "string" ? detail : "Ocurrió un error al comunicarse con el servidor.",
      response.status,
      detail
    );
  }

  return data;
}

/**
 * Like `request`, but for endpoints that return raw binary bytes (e.g. a
 * PDF) instead of JSON — `request` always calls `.json()`/`.text()` on the
 * response, which would corrupt binary content. Used by ticket downloads.
 */
async function requestBlob(path, { tokenAudience = null, skipCooperativaScope = false } = {}) {
  const headers = {};
  if (tokenAudience === "admin") {
    const token = adminTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  } else if (tokenAudience === "afiliado") {
    const token = afiliadoTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  path = withCooperativaScope(path, tokenAudience, skipCooperativaScope);

  const response = await fetch(`${BASE_URL}${path}`, { method: "GET", headers });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    const detail = typeof data === "object" && data !== null ? data.detail : data;

    if (response.status === 401 && tokenAudience) {
      (tokenAudience === "admin" ? adminTokenStore : afiliadoTokenStore).clear();
      window.dispatchEvent(new CustomEvent("beetticket:session-expired", { detail: { tokenAudience } }));
    }

    throw new ApiError(
      typeof detail === "string" ? detail : "Ocurrió un error al comunicarse con el servidor.",
      response.status,
      detail
    );
  }

  return response;
}

/**
 * Like `requestBlob`, but POSTs a FormData body first — used by the
 * plantilla preview endpoint, which needs to upload a file AND get raw
 * PDF bytes back in the same call (no JSON envelope with a URL).
 */
async function requestFormBlob(path, formData, { tokenAudience = null, skipCooperativaScope = false } = {}) {
  const headers = {};
  if (tokenAudience === "admin") {
    const token = adminTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  } else if (tokenAudience === "afiliado") {
    const token = afiliadoTokenStore.get();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  path = withCooperativaScope(path, tokenAudience, skipCooperativaScope);

  const response = await fetch(`${BASE_URL}${path}`, { method: "POST", headers, body: formData });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    const detail = typeof data === "object" && data !== null ? data.detail : data;

    if (response.status === 401 && tokenAudience) {
      (tokenAudience === "admin" ? adminTokenStore : afiliadoTokenStore).clear();
      window.dispatchEvent(new CustomEvent("beetticket:session-expired", { detail: { tokenAudience } }));
    }

    throw new ApiError(
      typeof detail === "string" ? detail : "Ocurrió un error al comunicarse con el servidor.",
      response.status,
      detail
    );
  }

  return response.blob();
}

function filenameFromResponse(response, fallback) {
  const header = response.headers.get("content-disposition") || "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

export const apiClient = {
  get: (path, opts) => request(path, { ...opts, method: "GET" }),
  post: (path, body, opts) => request(path, { ...opts, method: "POST", body }),
  patch: (path, body, opts) => request(path, { ...opts, method: "PATCH", body }),
  delete: (path, opts) => request(path, { ...opts, method: "DELETE" }),
  postForm: (path, formData, opts) => request(path, { ...opts, method: "POST", body: formData, isFormData: true }),
  postFormBlob: (path, formData, opts) => requestFormBlob(path, formData, opts),
  getBlob: (path, opts) => requestBlob(path, opts).then((response) => response.blob()),
  // For downloads whose real filename comes from the server
  // (Content-Disposition) — e.g. a dated report export — rather than one
  // the frontend can just make up (a ticket's filename is derived from
  // data already on the page, so plain getBlob is enough there).
  getBlobWithFilename: async (path, opts, fallbackFilename = "descarga") => {
    const response = await requestBlob(path, opts);
    const filename = filenameFromResponse(response, fallbackFilename);
    return { blob: await response.blob(), filename };
  },
};
