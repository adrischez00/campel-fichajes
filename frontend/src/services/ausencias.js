// src/services/ausencias.js
import { api } from "../services/api"; // mantiene tu wrapper actual

// -------- helpers internos --------
function getToken(t) {
  try {
    return t || (typeof localStorage !== "undefined" ? localStorage.getItem("access_token") : null);
  } catch {
    return t || null;
  }
}
function qs(params = {}) {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    u.set(k, String(v));
  });
  const s = u.toString();
  return s ? `?${s}` : "";
}

/**
 * Servicio de Ausencias
 * Todas las funciones aceptan el token como PRIMER parámetro para ser compatibles con tu código existente.
 * El token es OPCIONAL: si no lo pasas, se lee de localStorage ("access_token").
 */
export const ausenciasService = {
  // ---------- CRUD básico existente ----------

  crear(token, payload) {
    return api.post("/ausencias", getToken(token), payload);
  },

  // Nuevo preferido: usa la ruta /ausencias/mias del backend
  listarMias(token) {
    return api.get("/ausencias/mias", getToken(token));
  },

  // Mantengo el que ya tenías (aunque es mejor listarMias()):
  listarMiasPorEmail(token, email) {
    return api.get(`/ausencias${qs({ usuario_email: email })}`, getToken(token));
  },

  // Listado general con filtros
  listarTodas(token, { usuario_email, estado, tipo, desde, hasta } = {}) {
    return api.get(
      `/ausencias${qs({ usuario_email, estado, tipo, desde, hasta })}`,
      getToken(token)
    );
  },

  aprobar(token, id) {
    return api.post(`/ausencias/${id}/aprobar`, getToken(token));
  },

  // OJO: tu backend actual NO recibe "motivo" en esta ruta. Lo ignoro y aviso.
  rechazar(token, id, motivoRechazo) {
    if (motivoRechazo) {
      // eslint-disable-next-line no-console
      console.warn("ausenciasService.rechazar(): el backend no acepta 'motivo' en esta ruta; se ignora.");
    }
    return api.post(`/ausencias/${id}/rechazar`, getToken(token));
  },

  // ATENCIÓN: en tu backend NO hay DELETE /ausencias/{id}. Si lo llamas, obtendrás 404.
  eliminar(token, id) {
    return api.delete(`/ausencias/${id}`, getToken(token));
  },

  // ---------- NUEVOS ENDPOINTS (read-only + validar) ----------

  /**
   * GET /api/ausencias/balance
   * @param {{userId?: number, year?: number, email?: string}} params
   */
  balance(token, { userId, year, email } = {}) {
    return api.get(`/ausencias/balance${qs({ user_id: userId, year, email })}`, getToken(token));
  },

  /**
   * GET /api/ausencias/reglas
   * @param {{userId?: number, year?: number, email?: string}} params
   */
  reglas(token, { userId, year, email } = {}) {
    return api.get(`/ausencias/reglas${qs({ user_id: userId, year, email })}`, getToken(token));
  },

  /**
   * GET /api/ausencias/movimientos
   * @param {{userId?: number, limit?: number, email?: string}} params
   */
  movimientos(token, { userId, limit = 100, email } = {}) {
    return api.get(`/ausencias/movimientos${qs({ user_id: userId, limit, email })}`, getToken(token));
  },

  /**
   * POST /api/ausencias/validar
   * @param {{tipo: string, desde: string, hasta: string, medio_dia?: boolean, userId?: number, email?: string}} payload
   */
  validar(token, { tipo, desde, hasta, medio_dia = false, userId, email }) {
    const body = {
      tipo,
      desde,
      hasta,
      medio_dia,
      ...(userId ? { usuario_id: userId } : {}),
      ...(email ? { usuario_email: email } : {}),
    };
    return api.post("/ausencias/validar", getToken(token), body);
  },
};
