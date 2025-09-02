// src/components/admin/LogsTab.jsx
import React, { useState } from "react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import Paginacion from "../shared/Paginacion";

export default function LogsTab({ logs, rangoSeleccionado, fechasPersonalizadas }) {
  const [busqueda, setBusqueda] = useState("");
  const [pagina, setPagina] = useState(1);
  const porPagina = 5; // Reducido a 5 para que cada página sea más manejable
  const ahora = new Date();

  const filtrarPorFecha = (log) => {
    const fechaLog = new Date(log.timestamp);
    switch (rangoSeleccionado) {
      case '24h': return ahora - fechaLog <= 86400000;
      case '5d': return ahora - fechaLog <= 5 * 86400000;
      case '7d': return ahora - fechaLog <= 7 * 86400000;
      case '14d': return ahora - fechaLog <= 14 * 86400000;
      case 'personalizado':
        if (!fechasPersonalizadas.inicio || !fechasPersonalizadas.fin) return true;
        const inicio = new Date(fechasPersonalizadas.inicio);
        const fin = new Date(fechasPersonalizadas.fin);
        return fechaLog >= inicio && fechaLog <= fin;
      default: return true;
    }
  };

  const logsFiltrados = logs
    .filter(filtrarPorFecha)
    .filter(log =>
      (log.usuario_email || "").toLowerCase().includes(busqueda.toLowerCase())
    )
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

  const agrupados = agruparLogsConIntervalos(logsFiltrados);
  const totalPaginas = Math.ceil(agrupados.length / porPagina);
  const visibles = agrupados.slice((pagina - 1) * porPagina, pagina * porPagina);

  const exportarCSV = () => {
    let csv = "Usuario,Fecha,Entrada,Salida,Duración tramo,Total del día\n";
    agrupados.forEach(({ usuario, fecha, total, intervalos }) => {
      intervalos.forEach(i => {
        csv += `${usuario},${fecha},${i.entrada},${i.salida},${i.duracion},${total}\n`;
      });
    });
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", "logs_detallados.csv");
    link.click();
  };

  const exportarPDF = () => {
    const doc = new jsPDF();
    doc.setFontSize(14);
    doc.text("Campel – Logs detallados", 14, 20);
    doc.setFontSize(10);
    doc.text(new Date().toLocaleString("es-ES"), 14, 26);

    agrupados.forEach(({ usuario, fecha, total, intervalos }, index) => {
      const rows = intervalos.map(i => [fecha, i.entrada, i.salida, i.duracion]);
      autoTable(doc, {
        startY: doc.autoTable.previous ? doc.autoTable.previous.finalY + 10 : 32,
        head: [["Fecha", "Entrada", "Salida", "Duración"]],
        body: rows,
        margin: { left: 14, right: 14 },
        didDrawPage: index === 0 ? undefined : () => doc.addPage(),
        theme: 'striped',
        headStyles: { fillColor: [41, 128, 185] },
      });

      const y = doc.autoTable.previous.finalY + 4;
      doc.setFont(undefined, "bold");
      doc.text(`Usuario: ${usuario}`, 14, y);
      doc.text(`Total del día: ${total}`, 150, y, { align: 'right' });
    });

    doc.save("logs_detallados.pdf");
  };

  return (
    <div className="space-y-6">
      <input
        type="text"
        placeholder="🔍 Buscar por usuario..."
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        className="w-full md:w-96 px-4 py-2 rounded-xl border border-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
      />

      <ul className="text-sm space-y-4">
        {visibles.map((entry, i) => (
          <li key={i} className="p-4 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200">
            <p className="text-base font-bold text-blue-800 mb-2">{entry.usuario} – {entry.fecha}</p>
            <ul className="pl-2 mt-2 text-sm text-gray-700 space-y-1 border-l-2 border-blue-200">
              {entry.intervalos.map((t, idx) => (
                <li key={idx} className="pl-2">
                  <span className="flex items-center gap-2">
                    🕒 <strong>{t.entrada}</strong> → <strong>{t.salida}</strong>
                    <span className="text-gray-500 italic ml-2">({t.duracion})</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-blue-800 mt-2">Total del día: <strong>{entry.total}</strong></p>
          </li>
        ))}
      </ul>

      {totalPaginas > 1 && (
        <Paginacion
          pagina={pagina}
          totalPaginas={totalPaginas}
          onAnterior={() => setPagina(p => Math.max(1, p - 1))}
          onSiguiente={() => setPagina(p => Math.min(totalPaginas, p + 1))}
        />
      )}

      <div className="pt-4 border-t border-gray-200 flex flex-wrap gap-3">
        <button
          onClick={exportarCSV}
          className="px-5 py-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-indigo-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200"
        >
          📄 Exportar CSV
        </button>
        <button
          onClick={exportarPDF}
          className="px-5 py-2 rounded-2xl bg-gradient-to-r from-red-500 to-red-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200"
        >
          🧾 Exportar PDF
        </button>
      </div>
    </div>
  );
}

function agruparLogsConIntervalos(logs) {
  const agrupados = {};

  logs.forEach(log => {
    const user = log.usuario_email;
    const fecha = new Date(log.timestamp).toLocaleDateString("es-ES");
    const time = new Date(log.timestamp);
    const tipo = (log.tipo || "").toLowerCase();
    const isManual = log.is_manual;

    if (!user || !fecha || !tipo) return;

    if (!agrupados[user]) agrupados[user] = {};
    if (!agrupados[user][fecha]) agrupados[user][fecha] = [];

    agrupados[user][fecha].push({ tipo, time, isManual });
  });

  const resultado = [];

  for (const usuario in agrupados) {
    for (const fecha in agrupados[usuario]) {
      const logsDia = agrupados[usuario][fecha].sort((a, b) => a.time - b.time);
      const intervalos = [];
      let entrada = null;
      let entradaManual = false;
      let totalMs = 0;

      logsDia.forEach(({ tipo, time, isManual }) => {
        if (tipo === "entrada") {
          entrada = time;
          entradaManual = isManual;
        } else if (tipo === "salida" && entrada) {
          const durMs = time - entrada;
          totalMs += durMs;
          intervalos.push({
            entrada: `${entrada.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}${entradaManual ? " 📝" : ""}`,
            salida: `${time.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}${isManual ? " 📝" : ""}`,
            duracion: `${Math.floor(durMs / 3600000)}h ${Math.floor((durMs / 60000) % 60)}m`
          });
          entrada = null;
        }
      });

      const total = `${Math.floor(totalMs / 3600000)}h ${Math.floor((totalMs / 60000) % 60)}m`;
      resultado.push({ usuario, fecha, intervalos, total });
    }
  }

  return resultado;
}

