// src/services/api.js

// === BASE URL (forzar https si la app va en https) ===
const API_URL_RAW = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const API_URL =
  (typeof window !== "undefined" && window.location.protocol === "https:")
    ? API_URL_RAW.replace(/^http:\/\//, "https://")
    : API_URL_RAW;

// === Cookies httpOnly para refresh ===
const USE_CREDENTIALS = true; // imprescindible para enviar/recibir la cookie refresh

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
  const BASE = API_URL.replace(/\/+$/, "");
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
function buildHeaders(extraHeaders = {}, token, addJsonContentType) {
  const headers = { ...extraHeaders };
  const t = token ?? storage.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (addJsonContentType && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  return headers;
}

// ====== Refresh ======
let refreshing = false;
let waiters = [];

async function refreshAccess() {
  const url = join("/auth/refresh");
  const opts = {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  };
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
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// ====== Core request con auto-refresh ======
async function request(method, endpoint, { body, token = null, headers = {}, signal, retry = false } = {}) {
  assertNoMixedContent();

  const url = join(endpoint);

  // FormData detection para no forzar JSON ni Content-Type
  const isFormData = (typeof FormData !== "undefined") && body instanceof FormData;
  const willSendBody = body !== undefined && body !== null && method !== "GET" && method !== "HEAD";

  const finalHeaders = buildHeaders(headers, token, willSendBody && !isFormData);

  const opts = { method, headers: finalHeaders, signal };
  if (willSendBody) {
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
        waiters = [];
      } catch (err) {
        waiters.forEach((resume) => resume());
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
    // Reintento 1 vez
    const retriedHeaders = buildHeaders(headers, storage.get(), willSendBody && !isFormData);
    const retriedOpts = { ...opts, headers: retriedHeaders };
    const res2 = await fetch(url, retriedOpts);
    if (!res2.ok) {
      if (res2.status === 401) {
        storage.clear();
        if (typeof window !== "undefined") window.location.href = "/login";
      }
      const errText = await safeErrorText(res2);
      throw new Error(errText || `Error ${res2.status} en ${endpoint}`);
    }
    return parseBody(res2);
  }

  if (!res.ok) {
    const errText = await safeErrorText(res);
    throw new Error(errText || `Error ${res.status} en ${endpoint}`);
  }
  return parseBody(res);
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
  // Nuevo: envío de FormData (no JSON, sin Content-Type manual)
  postForm(endpoint, formData, token = null, extraHeaders = {}, signal) {
    return request("POST", endpoint, { body: formData, token, headers: extraHeaders, signal });
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

