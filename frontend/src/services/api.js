// src/services/api.js

// === BASE URL (forzar https si la app va en https) ===
const API_URL_RAW = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const API_URL =
  (typeof window !== "undefined" && window.location.protocol === "https:")
    ? API_URL_RAW.replace(/^http:\/\//, "https://")
    : API_URL_RAW;

// === Cookies httpOnly para refresh ===
const USE_CREDENTIALS = true; // ⬅️ IMPRESCINDIBLE para enviar/recibir la cookie refresh

// --- utils ---
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

// Ensambla BASE + path sin duplicar /api
function join(path = "") {
  const BASE = API_URL.replace(/\/+$/, ""); // sin barra final
  let p = normalizePath(path);
  if (BASE.endsWith("/api") && p.startsWith("/api/")) p = p.slice(4);
  return BASE + p;
}

// ====== Almacenamiento de access token ======
const ACCESS_KEYS = ["access", "access_token", "token"]; // compat
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

// ====== Cabeceras ======
function buildHeaders(extraHeaders = {}, token, willSendBody) {
  const headers = { ...extraHeaders };
  const t = token ?? storage.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (willSendBody && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  return headers;
}

// ====== Refresh concurrente (cola) ======
let refreshing = false;
let waiters = [];

async function refreshAccess() {
  // Llama a /auth/refresh (usa cookie httpOnly)
  const url = join("/auth/refresh");
  const opts = {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  };
  const res = await fetch(url, opts);
  if (!res.ok) {
    // refresh fallido → limpiar sesión
    storage.clear();
    throw new Error("No se pudo refrescar la sesión");
  }
  const data = await res.json();
  const newAccess = data?.access_token;
  if (!newAccess) throw new Error("Refresh sin access_token");
  storage.set(newAccess); // sessionStorage por defecto
  return newAccess;
}

async function withAutoRefresh(fetcher) {
  // Ejecuta una petición; si da 401, refresca y reintenta 1 vez
  try {
    return await fetcher();
  } catch (e) {
    throw e; // errores de red o abort; no toques
  }
}

// ====== Core request con auto-refresh ======
async function request(method, endpoint, { body, token = null, headers = {}, signal, retry = false } = {}) {
  assertNoMixedContent();

  const willSendBody = body !== undefined && body !== null && method !== "GET" && method !== "HEAD";
  const url = join(endpoint);
  const finalHeaders = buildHeaders(headers, token, willSendBody);

  const opts = { method, headers: finalHeaders, signal };
  if (willSendBody) opts.body = typeof body === "string" ? body : JSON.stringify(body);
  if (USE_CREDENTIALS) opts.credentials = "include"; // ⬅️ cookie httpOnly de refresh

  const res = await fetch(url, opts);

  if (res.status === 401 && !retry) {
    // Intentar refresh con cola
    if (!refreshing) {
      refreshing = true;
      try {
        const newAccess = await refreshAccess();
        // despachar a los que esperaban
        waiters.forEach((resume) => resume(newAccess));
        waiters = [];
      } catch (err) {
        waiters.forEach((resume) => resume(null));
        waiters = [];
        refreshing = false;
        // Redirigir a login
        if (typeof window !== "undefined") window.location.href = "/login";
        throw err;
      } finally {
        refreshing = false;
      }
    } else {
      // Esperar a que termine el refresh en curso
      await new Promise((resolve) => waiters.push((/*newAccess*/) => resolve()));
    }
    // Reintentar 1 vez con nuevo access en storage
    const tokenAfter = storage.get();
    const retriedHeaders = buildHeaders(headers, tokenAfter, willSendBody);
    const retriedOpts = { ...opts, headers: retriedHeaders };
    const res2 = await fetch(url, retriedOpts);
    if (!res2.ok) {
      // Si vuelve a fallar, limpiar y a login
      if (res2.status === 401) {
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
      }
      const errText = await safeErrorText(res2);
      throw new Error(errText || `Error ${res2.status} en ${endpoint}`);
    }
    return parseBody(res2, endpoint);
  }

  if (!res.ok) {
    const errText = await safeErrorText(res);
    throw new Error(errText || `Error ${res.status} en ${endpoint}`);
  }
  return parseBody(res, endpoint);
}

async function safeErrorText(res) {
  try {
    const j = await res.json();
    return j?.detail || JSON.stringify(j);
  } catch {
    try { return await res.text(); } catch { return null; }
  }
}

async function parseBody(res, endpoint) {
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// --- API de alto nivel ---
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
  try { await api.post("/auth/logout"); } catch {}
  storage.clear();
  if (typeof window !== "undefined") window.location.href = "/login";
}

// ===== Calendario =====
// Feed unificado (autenticado). IMPORTANTE: sin /api delante; API_URL puede terminar en /api.
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
