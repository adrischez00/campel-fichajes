// src/utils/tiempo.js

/**
 * Formatea segundos a una duración legible tipo:
 *  - 8h
 *  - 7h 38min
 *  - 45min
 *  - 1h 02min 05s (si showSeconds=true)
 *
 * @param {number|null|undefined} segundos
 * @param {object} options
 * @param {boolean} [options.showSeconds=false]  Mostrar segundos si existen
 * @param {boolean} [options.compact=true]       Omite unidades cero (ej: 8h, no 8h 0min)
 * @param {boolean} [options.zeroAsDash=true]    Si 0 → devolver "—"
 * @param {number}  [options.maxUnits=2]         Máximo de unidades a mostrar (ej: horas y min)
 */
export function formatearDuracion(segundos, {
  showSeconds = false,
  compact = true,
  zeroAsDash = true,
  maxUnits = 2,
} = {}) {
  if (segundos == null || Number.isNaN(segundos)) return zeroAsDash ? "—" : "0min";
  if (segundos < 0) segundos = 0;

  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = Math.floor(segundos % 60);

  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0 || (!compact && h > 0)) parts.push(`${m.toString().padStart( (h>0 && !compact) ? 2 : 1, "0")}min`);
  if (showSeconds && (s > 0 || (!compact && (h>0 || m>0)))) parts.push(`${s.toString().padStart( (m>0 && !compact) ? 2 : 1, "0")}s`);

  // Si todo es cero
  if (parts.length === 0) return zeroAsDash ? "—" : (showSeconds ? "0s" : "0min");

  // Limita unidades
  return parts.slice(0, Math.max(1, maxUnits)).join(" ");
}

/**
 * Formatea fecha (YYYY-MM-DD) y hora (HH:MM:SS) en una línea legible.
 * No cambia zonas; solo hace display.
 */
export function formatearFechaHora(fechaISO, horaISO) {
  const fecha = fechaISO ? fechaISO.split("-").reverse().join("/") : "";
  const hora = horaISO ? horaISO.slice(0, 5) : ""; // HH:MM
  if (fecha && hora) return `${fecha} ${hora}`;
  return fecha || hora || "—";
}
