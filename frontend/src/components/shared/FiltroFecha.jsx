import React, { useEffect, useState } from "react";

export default function FiltroFecha({
  rangoSeleccionado,
  setRangoSeleccionado,
  fechasPersonalizadas,
  setFechasPersonalizadas,
  onAplicarFiltro // Este callback se llama solo si lo necesitas externamente
}) {
  const [error, setError] = useState("");
  const [filtroAplicado, setFiltroAplicado] = useState(false);

  useEffect(() => {
    if (rangoSeleccionado === "personalizado") {
      const { inicio, fin } = fechasPersonalizadas;
      if (!inicio || !fin) {
        setError("Debes seleccionar ambas fechas.");
      } else if (new Date(inicio) > new Date(fin)) {
        setError("La fecha de inicio no puede ser posterior a la de fin.");
      } else {
        setError("");
      }
    } else {
      setError("");
      setFiltroAplicado(true);
    }
  }, [rangoSeleccionado, fechasPersonalizadas]);

  const aplicarFiltro = () => {
    if (!error && onAplicarFiltro) {
      onAplicarFiltro();
      setFiltroAplicado(true);
    }
  };

  return (
    <div className="mb-6 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
      <label className="text-sm font-medium text-gray-700">📅 Filtrar por fecha:</label>

      <div className="relative w-full sm:w-auto">
        <select
          value={rangoSeleccionado}
          onChange={(e) => {
            setRangoSeleccionado(e.target.value);
            setFiltroAplicado(false);
          }}
          className="appearance-none w-full rounded-xl border border-gray-300 bg-white px-4 py-2 pr-10 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="24h">Últimas 24 horas</option>
          <option value="5d">Últimos 5 días</option>
          <option value="7d">Últimos 7 días</option>
          <option value="14d">Últimos 14 días</option>
          <option value="todos">Todos</option>
          <option value="personalizado">Personalizado</option>
        </select>
        <svg
          className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {rangoSeleccionado === "personalizado" && (
        <div className="flex flex-col sm:flex-row gap-3 w-full">
          <input
            type="date"
            value={fechasPersonalizadas.inicio}
            onChange={(e) =>
              setFechasPersonalizadas({ ...fechasPersonalizadas, inicio: e.target.value })
            }
            className="w-full rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <input
            type="date"
            value={fechasPersonalizadas.fin}
            onChange={(e) =>
              setFechasPersonalizadas({ ...fechasPersonalizadas, fin: e.target.value })
            }
            className="w-full rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={aplicarFiltro}
            disabled={!!error}
            className={`whitespace-nowrap px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
              error
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            Aplicar filtro
          </button>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600 italic ml-[2px]">{error}</p>
      )}
    </div>
  );
}
