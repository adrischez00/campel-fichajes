// src/services/ausencias.js
import { api } from "../services/api";

export const ausenciasService = {
  // CRUD básico
  crear(payload, token = null) {
    return api.post("/ausencias", payload, token);
  },
  listarMiasPorEmail(token = null, email) {
    return api.get(`/ausencias?usuario_email=${encodeURIComponent(email)}`, token);
  },
  listarTodas(token = null) {
    return api.get("/ausencias", token);
  },
  aprobar(id, token = null) {
    return api.post(`/ausencias/${id}/aprobar`, {}, token);
  },
  rechazar(id, motivoRechazo, token = null) {
    return api.post(`/ausencias/${id}/rechazar`, { motivo: motivoRechazo }, token);
  },
  eliminar(id, token = null) {
    return api.delete(`/ausencias/${id}`, token);
  },

  // NUEVO: endpoints de saldos/reglas/movimientos/validación
  balance(params = {}, token = null) {
    const qs = new URLSearchParams(params).toString();
    const path = qs ? `/ausencias/balance?${qs}` : "/ausencias/balance";
    return api.get(path, token);
  },
  reglas(params = {}, token = null) {
    const qs = new URLSearchParams(params).toString();
    const path = qs ? `/ausencias/reglas?${qs}` : "/ausencias/reglas";
    return api.get(path, token);
  },
  movimientos(params = {}, token = null) {
    const qs = new URLSearchParams(params).toString();
    const path = qs ? `/ausencias/movimientos?${qs}` : "/ausencias/movimientos";
    return api.get(path, token);
  },
  validar(payload, token = null) {
    return api.post("/ausencias/validar", payload, token);
  },
};
