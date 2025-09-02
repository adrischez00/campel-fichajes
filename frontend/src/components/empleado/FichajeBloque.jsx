// src/components/empleado/FichajeBloque.jsx
import { useEffect, useState } from 'react';
import { parseISO, fmtHoraISO } from '../../utils/fecha';

export default function FichajeBloque({ entrada, salida, duracion, anomalia }) {
  const [duracionActual, setDuracionActual] = useState(duracion || 0);

  useEffect(() => {
    if (entrada?.timestamp && !salida?.timestamp) {
      const inicio = parseISO(entrada.timestamp); // 👈 corrige ISO sin zona → UTC
      if (!inicio || isNaN(inicio)) return;
      const interval = setInterval(() => {
        const ahora = new Date();
        setDuracionActual(Math.floor((ahora.getTime() - inicio.getTime()) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else if (duracion != null) {
      setDuracionActual(duracion);
    } else {
      setDuracionActual(0);
    }
  }, [entrada, salida, duracion]);

  const parseFecha = (ts) => {
    const f = parseISO(ts);
    return f && !isNaN(f) ? f : null;
  };

  const tEntrada = parseFecha(entrada?.timestamp);
  const tSalida = parseFecha(salida?.timestamp);

  // Horas SIEMPRE en Europe/Madrid (HH:mm)
  const formatHora = (isoOrDate) => {
    if (!isoOrDate) return '—';
    const iso = typeof isoOrDate === 'string' ? isoOrDate : isoOrDate.toISOString();
    return fmtHoraISO(iso) || '—';
  };

  const formatDuracion = (seg) => {
    if (seg == null) return '—';
    const h = Math.floor(seg / 3600);
    const m = Math.floor((seg % 3600) / 60);
    const s = seg % 60;
    return `${h}h ${m}min ${s}s`;
  };

  return (
    <div
      className={`rounded-2xl p-4 border transition-all duration-200 shadow-sm hover:shadow-md ${
        anomalia ? 'bg-red-100 border-red-300 text-red-900'
                 : 'bg-white border-gray-200 text-gray-800'
      }`}
    >
      {tEntrada ? (
        <p className="text-sm font-medium text-green-700 flex items-center gap-2">
          🟢 Entrada: <span>{formatHora(entrada?.timestamp)}</span>
          {entrada?.is_manual && <span className="text-xs text-blue-500">✍️ manual</span>}
        </p>
      ) : (
        <p className="text-sm text-red-700">⚠️ Falta la entrada</p>
      )}

      {tSalida ? (
        <p className="text-sm font-medium text-red-600 flex items-center gap-2">
          🔴 Salida: <span>{formatHora(salida?.timestamp)}</span>
          {salida?.is_manual && <span className="text-xs text-blue-500">✍️ manual</span>}
        </p>
      ) : (
        <p className="text-sm text-yellow-600">🕓 Aún sin salida</p>
      )}

      {anomalia && <p className="text-xs italic text-red-800 mt-1">⚠️ {anomalia}</p>}

      <p className="text-xs text-gray-500 italic mt-1">
        ⏱️ Duración: {formatDuracion(duracionActual)}
      </p>
    </div>
  );
}
