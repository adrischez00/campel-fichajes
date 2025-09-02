// src/components/admin/AgrupadorSolicitudes.jsx
import React from 'react';
import SolicitudCard from './SolicitudCard';

export default function AgrupadorSolicitudes({ solicitudes, onResolver }) {
  const agrupadas = solicitudes.reduce((acc, s) => {
    const [y, m, d] = s.fecha.split("-");
    const fechaFormateada = `${d}/${m}/${y}`;
    if (!acc[fechaFormateada]) acc[fechaFormateada] = [];
    acc[fechaFormateada].push(s);
    return acc;
  }, {});

  const fechas = Object.keys(agrupadas).sort((a, b) => new Date(b) - new Date(a));

  return (
    <div className="space-y-6">
      {fechas.map((fecha) => (
        <div key={fecha}>
          <div className="flex items-center mb-3">
            <span className="text-lg font-semibold text-blue-800">📅 {fecha}</span>
            <div className="flex-grow border-b ml-2 border-gray-300"></div>
          </div>
          <ul className="space-y-3">
            {agrupadas[fecha].map((s) => (
              <SolicitudCard key={s.id} solicitud={s} onResolver={onResolver} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
