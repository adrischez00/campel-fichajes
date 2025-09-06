// src/services/api.js

// === BASE URL (HTTPS-safe y con sufijo /api garantizado) ===
const RAW = (import.meta.env?.VITE_API_URL || "http://localhost:8000")
  .replace(/\/+$/, "");
const RAW_SECURE =
  typeof window !== "undefined" && window.location.protocol === "https:"
    ? RAW.replace(/^http:\/\//, "https://")
    : RAW;
// Fuerza sufijo /api en la base (evita /api/api más abajo)
export const API_URL = /\/api$/i.test(RAW_SECURE) ? RAW_SECURE : `${RAW_SECURE}/api`;

// === Cookies httpOnly para refresh ===
const USE_CREDENTIALS = true;

// ====== almacén de access token ======
const ACCESS_KEYS = ["access", "access_token", "token"];
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
// API_URL ya termina en /api. Evita duplicar si alguien pasa "/api/...."
function join(path = "") {
  const BASE = API_URL.replace(/\/+$/, "");
  let p = normalizePath(path);
  if (BASE.endsWith("/api") && p.startsWith("/api/")) p = p.slice(4);
  return BASE + p;
}

function willSendBody(method, body) {
  if (method === "GET" || method === "HEAD") return false;
  return body !== undefined && body !== null;
}

function buildHeaders(extraHeaders = {}, token, method, body) {
  const headers = { ...extraHeaders };
  const t = token ?? storage.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  const isFormData = (typeof FormData !== "undefined") && body instanceof FormData;
  if (willSendBody(method, body) && !headers["Content-Type"] && !isFormData) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

async function safeErrorText(res) {
  try {
    const j = await res.json();
    return j?.detail || JSON.stringify(j);
  } catch {
    try { return await res.text(); } catch { return null; }
  }
}
async function parseBody(res) {
  if (res.status === 204) return null;
  const txt = await res.text();
  return txt ? JSON.parse(txt) : null;
}

// ====== refresh concurrente (cola) ======
let refreshing = false;
let waiters = [];

async function refreshAccess() {
  const url = join("/auth/refresh");
  const opts = { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" } };
  const res = await fetch(url, opts);
  if (!res.ok) {
    storage.clear();
    throw new Error("No se pudo refrescar la sesión");
  }
  const data = await res.json();
  const newAccess = data?.access_token;
  if (!newAccess) throw new Error("Refresh sin access_token");
  storage.set(newAccess);
  return newAccess;
}

// ====== core request ======
async function request(method, endpoint, { body, token = null, headers = {}, signal, retry = false } = {}) {
  assertNoMixedContent();

  const url = join(endpoint);
  const opts = { method, signal };
  const isFormData = (typeof FormData !== "undefined") && body instanceof FormData;
  opts.headers = buildHeaders(headers, token, method, body);
  if (willSendBody(method, body)) {
    opts.body = isFormData ? body : (typeof body === "string" ? body : JSON.stringify(body));
  }
  if (USE_CREDENTIALS) opts.credentials = "include";

  const res = await fetch(url, opts);

  if (res.status === 401 && !retry) {
    if (!refreshing) {
      refreshing = true;
      try {
        await refreshAccess();
        waiters.forEach((resume) => resume());
      } catch (err) {
        waiters.forEach((resume) => resume());
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
        throw err;
      } finally {
        refreshing = false;
        waiters = [];
      }
    } else {
      await new Promise((resolve) => waiters.push(resolve));
    }
    // retry una vez, con token ya actualizado en storage
    const retried = await fetch(url, {
      ...opts,
      headers: buildHeaders(headers, storage.get(), method, body),
    });
    if (!retried.ok) {
      if (retried.status === 401) {
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
      }
      const errText = await safeErrorText(retried);
      throw new Error(errText || `Error ${retried.status} en ${endpoint}`);
    }
    return parseBody(retried);
  }

  if (!res.ok) {
    const errText = await safeErrorText(res);
    throw new Error(errText || `Error ${res.status} en ${endpoint}`);
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
  patch(endpoint, body, token = null, extraHeaders = {}, signal) {
    return request("PATCH", endpoint, { body, token, headers: extraHeaders, signal });
  },
  delete(endpoint, token = null, extraHeaders = {}, signal) {
    return request("DELETE", endpoint, { token, headers: extraHeaders, signal });
  },
  // Especial para FormData (no fija Content-Type)
  postForm(endpoint, formData, token = null, extraHeaders = {}, signal) {
    return request("POST", endpoint, { body: formData, token, headers: extraHeaders, signal });
  },
};

// ===== Helpers de Auth =====
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

// ===== Helpers de Calendario (compat con AusenciasCalendario.jsx) =====
export function fetchUserCalendarEvents(_userId, start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/events?${qs}`, token, {}, signal);
}
export function fetchWorkingDays(userId, start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/users/${userId}/working-days?${qs}`, token, {}, signal);
}
export function fetchWorkingDaysMe(start, end, token = null, signal) {
  const qs = new URLSearchParams({ start, end }).toString();
  return api.get(`/calendar/working-days?${qs}`, token, {}, signal);
}
export function fetchUserWorkingDays(...args) {
  // alias usado por AusenciasCalendario.jsx
  return fetchWorkingDays(...args);
}
