import React from 'react';

export default function FiltroFecha({ rangoSeleccionado, setRangoSeleccionado, fechasPersonalizadas, setFechasPersonalizadas }) {
  const handlePersonalizadaChange = (campo, valor) => {
    setFechasPersonalizadas({ ...fechasPersonalizadas, [campo]: valor });
  };

  return (
    <div className="mb-6">
      <label className="block text-sm font-semibold text-gray-800 mb-2">📆 Filtrar por fecha</label>
      <select
        value={rangoSeleccionado}
        onChange={(e) => setRangoSeleccionado(e.target.value)}
        className="w-full md:w-64 p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        <option value="24h">Últimas 24 horas</option>
        <option value="5d">Últimos 5 días</option>
        <option value="7d">Últimos 7 días</option>
        <option value="14d">Últimos 14 días</option>
        <option value="todos">Todos</option>
        <option value="personalizado">Personalizado</option>
      </select>

      {rangoSeleccionado === "personalizado" && (
        <div className="mt-3 flex flex-col md:flex-row items-start md:items-center gap-2">
          <input
            type="date"
            value={fechasPersonalizadas.inicio}
            onChange={(e) => handlePersonalizadaChange("inicio", e.target.value)}
            className="p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <span className="text-gray-500">a</span>
          <input
            type="date"
            value={fechasPersonalizadas.fin}
            onChange={(e) => handlePersonalizadaChange("fin", e.target.value)}
            className="p-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
      )}
    </div>
  );
}