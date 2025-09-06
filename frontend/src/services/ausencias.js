// src/services/ausencias.js
import { api } from "./api";

// —— helpers de querystring
function qs(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** Balance de ausencias para el usuario autenticado (o el indicado). */
export function getBalance(token, { user_id, email, year } = {}) {
  return api.get(`/ausencias/balance${qs({ user_id, email, year })}`, token);
}

/** Reglas de convenio aplicables al usuario autenticado (o el indicado). */
export function reglas(token, { user_id, email, year } = {}) {
  return api.get(`/ausencias/reglas${qs({ user_id, email, year })}`, token);
}

/** Movimientos del “ledger” de saldos. */
export function movimientos(token, { user_id, email, limit = 100 } = {}) {
  return api.get(`/ausencias/movimientos${qs({ user_id, email, limit })}`, token);
}

/** Valida una solicitud antes de crearla. */
export function validar(token, body) {
  return api.post(`/ausencias/validar`, body, token);
}

/** Crea una ausencia (usa alias /crear por compatibilidad). */
export function crear(token, payload) {
  return api.post(`/ausencias/crear`, payload, token);
}

/** Listados y acciones de gestión */
export function listarMiasPorEmail(token, email) {
  return api.get(`/ausencias${qs({ usuario_email: email })}`, token);
}

export function listarTodas(token, filtros = {}) {
  return api.get(`/ausencias${qs(filtros)}`, token);
}

export function aprobar(token, id) {
  // POST sin body
  return api.post(`/ausencias/${id}/aprobar`, null, token);
}

export function rechazar(token, id /*, motivoRechazo */) {
  // POST sin body (el backend actual no espera motivo)
  return api.post(`/ausencias/${id}/rechazar`, null, token);
}

export function eliminar(token, id) {
  return api.delete(`/ausencias/${id}`, token);
}

// API agrupada por comodidad
export const ausenciasService = {
  getBalance,
  reglas,
  movimientos,
  validar,
  crear,
  listarMiasPorEmail,
  listarTodas,
  aprobar,
  rechazar,
  eliminar,
};

export default ausenciasService;
