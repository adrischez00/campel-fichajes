import React, { useMemo, useState, useCallback, useEffect } from "react";
import { useLocation } from "react-router-dom";
import SolicitudCard from "./SolicitudCard";
import Paginacion from "../shared/Paginacion";
import { useToast } from "../ui/ToastContext";

const POR_PAGINA_DEFAULT = 4;

/* ───────────── Utils texto ───────────── */
const strip = (s) =>
  (s || "")
    .toString()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");

/* ───────────── Utils fecha/hora ───────────── */
function normalizeHora(hora) {
  const [h = "00", m = "00", s = "00"] = String(hora || "").trim().split(":");
  const pad2 = (x) => String(x ?? "00").padStart(2, "0");
  return [pad2(h), pad2(m), pad2(s)].join(":");
}
function parseFechaSolo(fechaStr) {
  if (!fechaStr) return null;
  const raw = String(fechaStr).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const [y, m, d] = raw.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) {
    const [d, m, y] = raw.split("/").map(Number);
    return new Date(y, m - 1, d);
  }
  const dt = new Date(raw);
  return isNaN(dt.getTime()) ? null : dt;
}
function toDate(fechaStr, horaStr) {
  const base = parseFechaSolo(fechaStr);
  if (!base) return null;
  const [hh, mm, ss] = normalizeHora(horaStr).split(":").map((n) => Number(n));
  base.setHours(hh, mm, ss, 0);
  return base;
}
function getTimestamp(s) {
  if (s?.timestamp) {
    const dt = new Date(s.timestamp);
    if (!isNaN(dt.getTime())) return dt;
  }
  const dt2 = toDate(s?.fecha, s?.hora);
  return dt2 && !isNaN(dt2.getTime()) ? dt2 : null;
}
function msLimite(rango) {
  switch (rango) {
    case "24h": return 24 * 60 * 60 * 1000;
    case "5d":  return 5  * 24 * 60 * 60 * 1000;
    case "7d":  return 7  * 24 * 60 * 60 * 1000;
    case "14d": return 14 * 24 * 60 * 60 * 1000;
    default:    return 0;
  }
}

/* ───────────── Estado desde URL/KPI ───────────── */
const normalizeEstado = (v) => {
  const s = strip(v);
  if (!s) return null;
  if (["todas", "todos", "all", "*"].includes(s)) return "todas";
  if (["pendiente", "pendientes"].includes(s)) return "pendiente";
  if (["aprobada", "aprobadas"].includes(s)) return "aprobada";
  if (["rechazada", "rechazadas", "denegada", "denegadas"].includes(s)) return "rechazada";
  return null;
};
function estadoFromLocation(location) {
  try {
    const params = new URLSearchParams(location.search);
    const q = params.get("estado");
    const n = normalizeEstado(q);
    if (n) return n;
  } catch {}
  if (location.hash && location.hash.includes("estado=")) {
    try {
      const hash = location.hash.startsWith("#") ? location.hash.slice(1) : location.hash;
      const hp = new URLSearchParams(hash.includes("?") ? hash.split("?")[1] : hash);
      const n = normalizeEstado(hp.get("estado"));
      if (n) return n;
    } catch {}
  }
  const parts = location.pathname.split("/").filter(Boolean);
  for (let i = parts.length - 1; i >= 0; i--) {
    const n = normalizeEstado(parts[i]);
    if (n) return n;
  }
  return null;
}
function pickFiltroEstado({ location, filtroInicial, estadoInicial }) {
  const p1 = normalizeEstado(filtroInicial?.estado);
  if (p1) return p1;
  const p2 = normalizeEstado(estadoInicial);
  const p3 = estadoFromLocation(location);
  return p3 || p2 || "pendiente";
}

/* ───────────── Componente ───────────── */
export default function SolicitudesTab({
  solicitudes,
  onResolver,
  filtroInicial,                 // opcional: { estado: '...' } desde KPI
  estadoInicial = "pendiente",   // compat
  rangoInicial = "todos",        // "todos" | "24h" | "5d" | "7d" | "14d" | "personalizado"
}) {
  const { show } = useToast();
  const location = useLocation();

  // Estado (controlado por URL/KPIs)
  const [filtroEstado, setFiltroEstado] = useState(() =>
    pickFiltroEstado({ location, filtroInicial, estadoInicial })
  );
  useEffect(() => {
    const next = pickFiltroEstado({ location, filtroInicial, estadoInicial });
    if (next !== filtroEstado) {
      setFiltroEstado(next);
      setPagina(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location, filtroInicial?.estado, estadoInicial]);

  // Filtros locales
  const [busqueda, setBusqueda] = useState("");
  const [rangoSeleccionado, setRangoSeleccionado] = useState(rangoInicial);
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(POR_PAGINA_DEFAULT);

  // Animación sutil al cambiar filtros
  const [fadeOn, setFadeOn] = useState(true);
  useEffect(() => {
    setFadeOn(false);
    const t = setTimeout(() => setFadeOn(true), 0);
    return () => clearTimeout(t);
  }, [filtroEstado, rangoSeleccionado, fechaInicio, fechaFin, busqueda, porPagina, pagina]);

  // Limpiar filtros
  const hasActiveFilters =
    !!busqueda ||
    rangoSeleccionado === "personalizado" ||
    (rangoSeleccionado !== "todos" && ["24h", "5d", "7d", "14d"].includes(rangoSeleccionado)) ||
    !!fechaInicio ||
    !!fechaFin;

  const clearFilters = useCallback(() => {
    setBusqueda("");
    setRangoSeleccionado("todos");
    setFechaInicio("");
    setFechaFin("");
    setPagina(1);
    show("Filtros limpiados");
  }, [show]);

  // ESC → limpiar filtros
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape" && hasActiveFilters) {
        e.preventDefault();
        clearFilters();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [hasActiveFilters, clearFilters]);

  // Tokens de búsqueda
  const tokens = useMemo(() => strip(busqueda).split(/\s+/).filter(Boolean), [busqueda]);

  // Filtrado principal
  const filtradas = useMemo(() => {
    const now = Date.now();
    const limite = msLimite(rangoSeleccionado);

    let inicioPers = null;
    let finPers = null;
    if (rangoSeleccionado === "personalizado" && (fechaInicio || fechaFin)) {
      if (fechaInicio) inicioPers = parseFechaSolo(fechaInicio);
      if (fechaFin) {
        finPers = parseFechaSolo(fechaFin);
        if (finPers) finPers.setHours(23, 59, 59, 999);
      }
    }

    return (solicitudes || [])
      .filter((s) => {
        if (filtroEstado !== "todas" && s.estado !== filtroEstado) return false;

        const ts = getTimestamp(s);
        if (!ts) return false;
        if (limite > 0 && now - ts.getTime() > limite) return false;
        if (rangoSeleccionado === "personalizado") {
          if (inicioPers && ts < inicioPers) return false;
          if (finPers && ts > finPers) return false;
        }

        if (tokens.length > 0) {
          const haystack = strip([s.usuario_email, s.tipo, s.motivo].join(" "));
          if (!tokens.every((t) => haystack.includes(t))) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const ta = getTimestamp(a)?.getTime() ?? 0;
        const tb = getTimestamp(b)?.getTime() ?? 0;
        return tb - ta;
      });
  }, [solicitudes, filtroEstado, rangoSeleccionado, tokens, fechaInicio, fechaFin]);

  // Paginación
  const totalPaginas = Math.max(1, Math.ceil(filtradas.length / porPagina));
  const desde = (pagina - 1) * porPagina;
  const hasta = Math.min(desde + porPagina, filtradas.length);
  const encontradas = filtradas.slice(desde, hasta);

  // Labels
  const estadoLabel =
    filtroEstado === "pendiente" ? "Pendientes" :
    filtroEstado === "aprobada"  ? "Aprobadas" :
    filtroEstado === "rechazada" ? "Rechazadas" : "Todas";

  const rangoLabel =
    rangoSeleccionado === "24h" ? "Últimas 24h" :
    rangoSeleccionado === "5d"  ? "Últimos 5 días" :
    rangoSeleccionado === "7d"  ? "Últimos 7 días" :
    rangoSeleccionado === "14d" ? "Últimos 14 días" :
    rangoSeleccionado === "personalizado"
      ? (fechaInicio && fechaFin
          ? `Personalizado: ${fmt(fechaInicio)} → ${fmt(fechaFin)}`
          : fechaInicio ? `Personalizado: desde ${fmt(fechaInicio)}`
          : fechaFin ? `Personalizado: hasta ${fmt(fechaFin)}`
          : "Personalizado")
      : "Todo";

  const microcopy = `Mostrando: ${estadoLabel} · ${rangoLabel} · ${filtradas.length} resultado${filtradas.length === 1 ? "" : "s"}${busqueda ? ` · Filtro: “${busqueda}”` : ""}`;

  return (
    <div className="space-y-5">
      {/* TOOLBAR glassmorphism */}
      <div className="sticky top-20 z-10">
        <div className="rounded-2xl border border-white/50 bg-white/50 backdrop-blur-md shadow-sm px-4 pt-2 pb-3">
          <p className="text-sm text-gray-700 flex items-center gap-2 mb-2">
            <span>📊</span>
            <span aria-live="polite">{microcopy}</span>
          </p>

          <div className="flex flex-wrap items-center gap-8">
            {/* Buscador */}
            <div className="relative flex-1 min-w-[260px]">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 select-none">🔍</span>
              <input
                type="text"
                placeholder="Buscar por usuario, tipo o motivo…"
                aria-label="Buscar solicitudes"
                value={busqueda}
                onChange={(e) => { setBusqueda(e.target.value); setPagina(1); }}
                className="w-full pl-10 pr-3 py-2 rounded-xl border border-white/60 bg-white/70 backdrop-blur focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Rango rápido */}
            <div className="flex flex-wrap items-center gap-2">
              {[
                { id: "24h",  label: "24h" },
                { id: "5d",   label: "5 días" },
                { id: "7d",   label: "7 días" },
                { id: "14d",  label: "14 días" },
                { id: "todos",label: "Todo" },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => { setRangoSeleccionado(id); setPagina(1); }}
                  className={`px-3 py-1.5 rounded-xl text-sm border transition ${
                    rangoSeleccionado === id
                      ? "bg-blue-600 text-white border-blue-600 shadow"
                      : "bg-white/60 text-gray-800 border-white/60 hover:bg-white/80"
                  }`}
                >
                  {label}
                </button>
              ))}

              {/* Personalizado */}
              <details className="group">
                <summary
                  className={`list-none cursor-pointer inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm border transition ${
                    rangoSeleccionado === "personalizado"
                      ? "bg-blue-600 text-white border-blue-600 shadow"
                      : "bg-white/60 text-gray-800 border-white/60 hover:bg-white/80"
                  }`}
                  onClick={(e) => {
                    const el = e.currentTarget.parentElement;
                    if (!el.open) { setRangoSeleccionado("personalizado"); setPagina(1); }
                  }}
                >
                  <span>Personalizado</span>
                  <span className="transition group-open:rotate-180">▾</span>
                </summary>

                <div className="mt-2 flex items-center gap-2 p-2 rounded-xl border border-white/60 bg-white/70 backdrop-blur">
                  <input
                    type="date"
                    value={fechaInicio}
                    onChange={(e) => { setFechaInicio(e.target.value); setPagina(1); }}
                    className="px-2 py-1.5 rounded-lg border border-white/60 bg-white/80"
                    aria-label="Fecha inicio"
                  />
                  <span className="text-gray-500">→</span>
                  <input
                    type="date"
                    value={fechaFin}
                    onChange={(e) => { setFechaFin(e.target.value); setPagina(1); }}
                    className="px-2 py-1.5 rounded-lg border border-white/60 bg-white/80"
                    aria-label="Fecha fin"
                  />
                </div>
              </details>

              {/* Limpiar filtros */}
              <button
                onClick={clearFilters}
                disabled={!hasActiveFilters}
                className={`ml-1 px-3 py-1.5 rounded-xl text-sm border transition ${
                  hasActiveFilters
                    ? "bg-white/60 text-gray-800 border-white/60 hover:bg-white/80"
                    : "bg-white/40 text-gray-400 border-white/40 cursor-not-allowed"
                }`}
                title="Borrar búsqueda y filtros"
              >
                Limpiar filtros
              </button>

              {/* Selector por página */}
              <div className="ml-2">
                <label className="text-sm text-gray-700 mr-2" htmlFor="por-pagina">Por página</label>
                <select
                  id="por-pagina"
                  value={porPagina}
                  onChange={(e) => { setPorPagina(Number(e.target.value)); setPagina(1); }}
                  className="px-2 py-1.5 rounded-lg border border-white/60 bg-white/70"
                >
                  <option value={4}>4</option>
                  <option value={8}>8</option>
                  <option value={12}>12</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* LISTADO */}
      <ul
        className="list-none p-0 m-0 space-y-4"
        style={{ opacity: fadeOn ? 1 : 0, transform: fadeOn ? "translateY(0px)" : "translateY(4px)", transition: "opacity 200ms ease, transform 200ms ease" }}
      >
        {encontradas.length === 0 ? (
          <li className="text-gray-600 italic text-center mt-6">No se encontraron solicitudes.</li>
        ) : (
          encontradas.map((s) => (
            <li key={s.id}>
              <SolicitudCard solicitud={s} onResolver={onResolver} highlight={tokens} />
            </li>
          ))
        )}
      </ul>

      {/* Paginación */}
      {totalPaginas > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-gray-700">
            Mostrando <strong>{filtradas.length ? desde + 1 : 0}</strong>–<strong>{hasta}</strong> de <strong>{filtradas.length}</strong>
          </span>

          <Paginacion
            pagina={pagina}
            totalPaginas={totalPaginas}
            onAnterior={() => setPagina((p) => Math.max(1, p - 1))}
            onSiguiente={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
            totalItems={filtradas.length}
            porPagina={porPagina}
          />
        </div>
      )}
    </div>
  );
}

function fmt(iso) {
  if (!iso) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(iso)) return iso;
  return iso;
}