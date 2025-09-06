// src/services/api.js

// ===== Configuración base =====
const API_URL_RAW = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const API_URL =
  (typeof window !== "undefined" && window.location.protocol === "https:")
    ? API_URL_RAW.replace(/^http:\/\//, "https://")
    : API_URL_RAW;

// Cookies httpOnly para refresh (recomendado mantener en true si usas cookie de refresh)
const USE_CREDENTIALS = true;

// Timeout (ms) para evitar requests colgados
const HTTP_TIMEOUT_MS = Number(import.meta.env?.VITE_HTTP_TIMEOUT_MS ?? 15000);

// ===== Utilidades base =====
function normalizePath(endpoint) {
  if (!endpoint) return "/";
  return endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
}

function assertNoMixedContent() {
  if (
    typeof window !== "undefined" &&
    window.location.protocol === "https:" &&
    API_URL.startsWith("http://")
  ) {
    throw new Error(`Mixed content: app en HTTPS pero API_URL=${API_URL}. Usa HTTPS en VITE_API_URL.`);
  }
}

/** Ensambla BASE + path sin duplicar /api */
export function join(path = "") {
  const BASE = API_URL.replace(/\/+$/, "");
  let p = normalizePath(path);
  if (BASE.endsWith("/api") && p.startsWith("/api/")) p = p.slice(4);
  return BASE + p;
}

// ===== Almacenamiento de access token =====
const ACCESS_KEYS = ["access", "access_token", "token"]; // claves compatibles
const storage = {
  get() {
    let v = null;
    if (typeof sessionStorage !== "undefined") {
      for (const k of ACCESS_KEYS) { v ||= sessionStorage.getItem(k); if (v) break; }
    }
    if (!v && typeof localStorage !== "undefined") {
      for (const k of ACCESS_KEYS) { v ||= localStorage.getItem(k); if (v) break; }
    }
    return v;
  },
  set(token, remember = false) {
    if (!token) return this.clear();
    if (remember && typeof localStorage !== "undefined") {
      localStorage.setItem("access", token);
    } else if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem("access", token);
    }
  },
  clear() {
    if (typeof sessionStorage !== "undefined") {
      for (const k of ACCESS_KEYS) sessionStorage.removeItem(k);
    }
    if (typeof localStorage !== "undefined") {
      for (const k of ACCESS_KEYS) localStorage.removeItem(k);
    }
  },
};
export const getAccessToken = () => storage.get();

// ===== Cabeceras =====
function buildHeaders(extraHeaders = {}, token, willSendJsonBody) {
  const headers = { ...extraHeaders };
  const t = token ?? storage.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (willSendJsonBody && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (!headers["Accept"]) headers["Accept"] = "application/json";
  return headers;
}

// ===== Refresh concurrente (cola) =====
let refreshing = false;
let waiters = []; // resolvers que esperan al refresh

async function refreshAccess() {
  const url = join("/auth/refresh");
  const opts = {
    method: "POST",
    credentials: "include", // cookie httpOnly
    headers: { "Content-Type": "application/json" },
  };
  const res = await fetch(url, opts);
  if (!res.ok) {
    storage.clear();
    throw new Error("No se pudo refrescar la sesión");
  }
  // Permitir 204 sin cuerpo y tratarlo como error
  let data = null;
  try { data = await res.json(); } catch { /* sin cuerpo */ }
  const newAccess = data?.access_token;
  if (!newAccess) {
    storage.clear();
    throw new Error("Refresh sin access_token");
  }
  storage.set(newAccess); // por defecto sessionStorage
  return newAccess;
}

// ===== Helpers de parseo de respuesta/errores =====
async function safeErrorText(res) {
  try {
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      const j = await res.json();
      return j?.detail || j?.message || JSON.stringify(j);
    }
    return await res.text();
  } catch {
    return null;
  }
}

async function parseBody(res) {
  if (res.status === 204) return null;
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (ct.includes("application/json")) {
    return res.json();
  }
  const txt = await res.text();
  try { return txt ? JSON.parse(txt) : null; } catch { return txt || null; }
}

// ===== Core request JSON con auto-refresh + timeout =====
async function request(method, endpoint, { body, token = null, headers = {}, signal } = {}) {
  assertNoMixedContent();

  const url = join(endpoint);
  const willSendJsonBody = body !== undefined && body !== null && method !== "GET" && method !== "HEAD" && !(body instanceof FormData);
  const finalHeaders = buildHeaders(headers, token, willSendJsonBody);

  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(new DOMException("Timeout", "AbortError")), HTTP_TIMEOUT_MS);

  const opts = {
    method,
    headers: finalHeaders,
    credentials: USE_CREDENTIALS ? "include" : "same-origin",
    signal: signal || ac.signal,
  };
  if (willSendJsonBody) opts.body = typeof body === "string" ? body : JSON.stringify(body);
  if (body instanceof FormData) opts.body = body; // (por si alguien llama request con FormData)

  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    clearTimeout(t);
    const err = new Error(e?.name === "AbortError" ? "Solicitud agotada (timeout)" : "Error de red");
    err.code = e?.name === "AbortError" ? "TIMEOUT" : "NETWORK";
    err.cause = e;
    throw err;
  }
  clearTimeout(t);

  // Auto-refresh 401 (una sola vez por llamada)
  if (res.status === 401) {
    // Colapsar refresh en curso
    if (!refreshing) {
      refreshing = true;
      try {
        const newAccess = await refreshAccess();
        waiters.forEach((resolve) => resolve(newAccess));
        waiters = [];
      } catch (err) {
        waiters.forEach((resolve) => resolve(null));
        waiters = [];
        refreshing = false;
        if (typeof window !== "undefined") window.location.href = "/login";
        throw err;
      } finally {
        refreshing = false;
      }
    } else {
      await new Promise((resolve) => waiters.push(resolve));
    }

    // Reintentar con el token actual del storage
    const tokenAfter = storage.get();
    const retryHeaders = buildHeaders(headers, tokenAfter, willSendJsonBody);
    const retryOpts = {
      ...opts,
      headers: retryHeaders,
    };
    const res2 = await fetch(url, retryOpts);
    if (!res2.ok) {
      if (res2.status === 401) {
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
      }
      const msg = (await safeErrorText(res2)) || `Error ${res2.status} en ${endpoint}`;
      const err = new Error(msg);
      err.status = res2.status;
      throw err;
    }
    return parseBody(res2);
  }

  if (!res.ok) {
    const msg = (await safeErrorText(res)) || `Error ${res.status} en ${endpoint}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }

  return parseBody(res);
}

// ===== Request para FormData (fichar) con auto-refresh + timeout =====
async function requestForm(endpoint, { formData, token = null, headers = {}, signal } = {}) {
  assertNoMixedContent();

  const url = join(endpoint);
  const finalHeaders = buildHeaders(headers, token, /*willSendJsonBody*/ false);
  // No pongas Content-Type: el navegador añade boundary correcto

  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(new DOMException("Timeout", "AbortError")), HTTP_TIMEOUT_MS);

  const baseOpts = {
    method: "POST",
    headers: finalHeaders,
    credentials: USE_CREDENTIALS ? "include" : "same-origin",
    body: formData,
    signal: signal || ac.signal,
  };

  let res;
  try {
    res = await fetch(url, baseOpts);
  } catch (e) {
    clearTimeout(t);
    const err = new Error(e?.name === "AbortError" ? "Solicitud agotada (timeout)" : "Error de red");
    err.code = e?.name === "AbortError" ? "TIMEOUT" : "NETWORK";
    err.cause = e;
    throw err;
  }
  clearTimeout(t);

  if (res.status === 401) {
    if (!refreshing) {
      refreshing = true;
      try {
        const newAccess = await refreshAccess();
        waiters.forEach((resolve) => resolve(newAccess));
        waiters = [];
      } catch (err) {
        waiters.forEach((resolve) => resolve(null));
        waiters = [];
        refreshing = false;
        if (typeof window !== "undefined") window.location.href = "/login";
        throw err;
      } finally {
        refreshing = false;
      }
    } else {
      await new Promise((resolve) => waiters.push(resolve));
    }

    // Reintento con nuevo token (si lo hay)
    const tokenAfter = storage.get();
    const retryHeaders = buildHeaders(headers, tokenAfter, false);
    const res2 = await fetch(url, { ...baseOpts, headers: retryHeaders });
    if (!res2.ok) {
      if (res2.status === 401) {
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
      }
      const msg = (await safeErrorText(res2)) || `Error ${res2.status} en ${endpoint}`;
      const err = new Error(msg);
      err.status = res2.status;
      throw err;
    }
    return parseBody(res2);
  }

  if (!res.ok) {
    const msg = (await safeErrorText(res)) || `Error ${res.status} en ${endpoint}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }

  return parseBody(res);
}

// ===== API de alto nivel =====
export const api = {
  get(endpoint, token = null, extraHeaders = {}, signal) {
    return request("GET", endpoint, { token, headers: extraHeaders, signal });
  },
  post(endpoint, body, token = null, extraHeaders = {}, signal) {
    return request("POST", endpoint, { body, token, headers: extraHeaders, signal });
  },
  put(endpoint, body, token = null, extraHeaders = {}, signal) {
    return request("PUT", endpoint, { body, token, headers: extraHeaders, signal });
  },
  delete(endpoint, token = null, extraHeaders = {}, signal) {
    return request("DELETE", endpoint, { token, headers: extraHeaders, signal });
  },
  /** POST con FormData (p.ej. /fichar) */
  postForm(endpoint, formData, token = null, extraHeaders = {}, signal) {
    return requestForm(endpoint, { formData, token, headers: extraHeaders, signal });
  },
};

// ===== Helpers de Auth (front) =====
export async function doLogin(email, password, remember = false) {
  const data = await api.post("/auth/login-json", { email, password });
  const access = data?.access_token;
  if (!access) throw new Error("Login sin access_token");
  storage.set(access, remember);
  return data;
}

export async function doLogout() {
  try { await api.post("/auth/logout", {}); } catch {}
  storage.clear();
  if (typeof window !== "undefined") window.location.href = "/login";
}

// ===== Calendario =====
export async function fetchUserCalendarEvents(_userId, start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/events?${qs}`, token, {}, signal);
}

export async function fetchWorkingDays(userId, start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/users/${userId}/working-days?${qs}`, token, {}, signal);
}

export async function fetchWorkingDaysMe(start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/working-days?${qs}`, token, {}, signal);
}

export async function fetchUserWorkingDays(...args) {
  return fetchWorkingDays(...args);
}
