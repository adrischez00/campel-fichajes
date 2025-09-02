import React from "react";

/**
 * Barra de filtros reutilizable (buscador + rangos + personalizado + por página)
 *
 * Props:
 * - microcopy: string                 -> texto "Mostrando..."
 * - placeholderBusqueda: string
 * - busqueda, setBusqueda: string, fn
 * - rangoSeleccionado, setRangoSeleccionado: string ('24h'|'5d'|'7d'|'14d'|'todos'|'personalizado')
 * - fechasPersonalizadas, setFechasPersonalizadas: {inicio, fin}, fn
 * - porPagina, setPorPagina: number, fn
 * - chipsEstado?: [{id,label,icon,count,vista}], onChipClick?: (chip)=>void   (opcional)
 */
export default function BarraFiltros({
  microcopy,
  placeholderBusqueda = "Buscar…",
  busqueda,
  setBusqueda,
  rangoSeleccionado,
  setRangoSeleccionado,
  fechasPersonalizadas,
  setFechasPersonalizadas,
  porPagina,
  setPorPagina,
  chipsEstado = null,
  onChipClick = () => {},
}) {
  return (
    <div className="sticky top-20 z-10 bg-[#F4F6F8] pt-1 pb-3">
      {/* Chips opcionales (p.ej. estados en Solicitudes) */}
      {Array.isArray(chipsEstado) && chipsEstado.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-3" role="tablist">
          {chipsEstado.map((c) => (
            <button
              key={c.id}
              role="tab"
              aria-selected={c.activo}
              onClick={() => onChipClick(c)}
              className={`px-3 py-1.5 rounded-xl text-sm border transition inline-flex items-center gap-2
                ${c.activo
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"}`}
              title={c.label}
            >
              <span aria-hidden>{c.icon}</span>
              <span>{c.label}</span>
              {typeof c.count === "number" && (
                <span className="text-xs opacity-80">({c.count})</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Microcopy */}
      {microcopy && (
        <p className="text-sm text-gray-500 flex items-center gap-2 mb-2">
          <span>📊</span>
          <span>{microcopy}</span>
        </p>
      )}

      {/* Buscador + rangos + por página */}
      <div className="flex flex-wrap items-center gap-8">
        {/* Buscador */}
        <div className="relative flex-1 min-w-[260px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 select-none">🔍</span>
          <input
            type="text"
            placeholder={placeholderBusqueda}
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="w-full pl-10 pr-3 py-2 rounded-xl border border-gray-300 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Rangos rápidos */}
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: "24h", label: "24h" },
            { id: "5d", label: "5 días" },
            { id: "7d", label: "7 días" },
            { id: "14d", label: "14 días" },
            { id: "todos", label: "Todo" },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setRangoSeleccionado(id)}
              className={`px-3 py-1.5 rounded-xl text-sm border transition ${
                rangoSeleccionado === id
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
              }`}
              aria-pressed={rangoSeleccionado === id}
            >
              {label}
            </button>
          ))}

          {/* Personalizado */}
          <details className="group">
            <summary
              className={`list-none cursor-pointer inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm border transition ${
                rangoSeleccionado === "personalizado"
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
              }`}
              onClick={(e) => {
                const el = e.currentTarget.parentElement;
                if (!el.open) setRangoSeleccionado("personalizado");
              }}
            >
              <span>Personalizado</span>
              <span className="transition group-open:rotate-180">▾</span>
            </summary>

            <div className="mt-2 flex items-center gap-2 p-2 rounded-xl border border-gray-200 bg-white shadow-sm">
              <input
                type="date"
                value={fechasPersonalizadas.inicio || ""}
                onChange={(e) => setFechasPersonalizadas((p) => ({ ...p, inicio: e.target.value }))}
                className="px-2 py-1.5 rounded-lg border border-gray-300"
                aria-label="Fecha inicio"
              />
              <span className="text-gray-400">→</span>
              <input
                type="date"
                value={fechasPersonalizadas.fin || ""}
                onChange={(e) => setFechasPersonalizadas((p) => ({ ...p, fin: e.target.value }))}
                className="px-2 py-1.5 rounded-lg border border-gray-300"
                aria-label="Fecha fin"
              />
            </div>
          </details>

          {/* Por página */}
          <div className="ml-2">
            <label className="text-sm text-gray-500 mr-2">Por página</label>
            <select
              value={porPagina}
              onChange={(e) => setPorPagina(Number(e.target.value))}
              className="px-2 py-1.5 rounded-lg border border-gray-300 bg-white text-sm"
              aria-label="Resultados por página"
            >
              <option value={4}>4</option>
              <option value={8}>8</option>
              <option value={12}>12</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
