import React from "react";
import { formatDateTime } from "../../utils/formatDate";

export default function LogItem({ log }) {
  const fecha = new Date(log.timestamp);
  const fechaFormateada = formatDateTime(
    fecha.toISOString().slice(0, 10),
    fecha.toTimeString().slice(0, 5)
  );

  const accion = log.accion.charAt(0).toUpperCase() + log.accion.slice(1);
  const detalle = log.detalle.charAt(0).toUpperCase() + log.detalle.slice(1);

  return (
    <li className="flex justify-between items-start p-4 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex-1 pr-2">
        <p className="text-sm font-medium text-gray-800">
          <span className="text-blue-700 font-semibold">{log.usuario_email}</span> – {accion}
        </p>
        <p className="text-sm text-gray-600 mt-1">{detalle}</p>
      </div>
      <div className="text-xs text-gray-500 text-right min-w-fit pl-2">{fechaFormateada}</div>
    </li>
  );
}
