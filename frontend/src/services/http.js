// src/services/http.js
export function getApiBase() {
  const raw = import.meta.env?.VITE_API_URL || "http://localhost:8000/api";
  const clean = String(raw).replace(/\/+$/, "");         // quita / finales
  return /\/api$/i.test(clean) ? clean : `${clean}/api`; // fuerza sufijo /api
}

export async function apiFetch(path, options = {}) {
  const url = `${getApiBase()}${path}`;
  const res = await fetch(url, {
    credentials: "include",   // igual que antes
    ...options,
  });
  return res;
}

export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
