// src/utils/fecha.js
const TZ = 'Europe/Madrid';
const HAS_TZ = /([zZ]|[+\-]\d{2}:?\d{2})$/; // Z o +hh(:)mm al final

// Si el ISO no trae zona, asumimos UTC (añadimos 'Z')
export const parseISO = (iso) => {
  if (!iso) return null;
  if (iso instanceof Date) return iso;
  const s = String(iso).trim();
  return new Date(HAS_TZ.test(s) ? s : s + 'Z');
};

export const fmtHoraISO = (iso) => {
  const d = parseISO(iso);
  if (!d || isNaN(d)) return '';
  return d.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: TZ,
  });
};

export const fmtFechaISO = (iso) => {
  const d = parseISO(iso);
  if (!d || isNaN(d)) return '';
  return d.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: TZ,
  });
};

export const fmtFechaHoraISO = (iso) =>
  iso ? `${fmtFechaISO(iso)} · ${fmtHoraISO(iso)}` : '';

export const yyyymmddTZ = (isoOrDate) => {
  const d = parseISO(isoOrDate) || new Date();
  const s = d.toLocaleDateString('es-ES', {
    timeZone: TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return s.split('/').reverse().join('-'); // YYYY-MM-DD
};
