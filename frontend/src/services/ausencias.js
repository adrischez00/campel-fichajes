// src/services/ausencias.js
import { api } from "../services/api"; // ← ajusta la ruta si tu api.js vive en otra carpeta

export const ausenciasService = {
  crear(token, payload) {
    return api.post("/ausencias", token, payload);
  },

  // Nuevo: listar por email usando el filtro del backend
  listarMiasPorEmail(token, email) {
    return api.get(`/ausencias?usuario_email=${encodeURIComponent(email)}`, token);
  },

  listarTodas(token) {
    return api.get("/ausencias", token);
  },

  aprobar(token, id) {
    return api.post(`/ausencias/${id}/aprobar`, token);
  },

  rechazar(token, id, motivoRechazo) {
    return api.post(`/ausencias/${id}/rechazar`, token, { motivo: motivoRechazo });
  },

  eliminar(token, id) {
    return api.delete(`/ausencias/${id}`, token);
  },
};

