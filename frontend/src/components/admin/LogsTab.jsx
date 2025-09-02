import React, { useMemo, useState, useEffect } from "react";
import Paginacion from "../shared/Paginacion";
import BarraFiltros from "../shared/BarraFiltros";

export default function LogsTab({ logs }) {
  // Filtros reutilizados
  const [busqueda, setBusqueda] = useState("");
  const [rangoSeleccionado, setRangoSeleccionado] = useState("todos");
  const [fechasPersonalizadas, setFechasPersonalizadas] = useState({ inicio: "", fin: "" });

  // Paginación
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(5);

  // Anim
  const [fadeOn, setFadeOn] = useState(true);
  useEffect(() => {
    setFadeOn(false);
    const t = setTimeout(() => setFadeOn(true), 0);
    return () => clearTimeout(t);
  }, [busqueda, rangoSeleccionado, fechasPersonalizadas, pagina, porPagina]);

  const logsArray = Array.isArray(logs) ? logs : [];
  const parseTs = (ts) => { const d=new Date(ts); return isNaN(d.getTime())?0:d.getTime(); };

  // Filtrado
  const ahoraTs = useMemo(() => Date.now(), []);
  const logsFiltrados = useMemo(() => {
    const q = busqueda.toLowerCase();
    const byText = (l) =>
      (l.usuario_email || "").toLowerCase().includes(q) ||
      (l.tipo || "").toLowerCase().includes(q) ||
      (l.detalle || "").toLowerCase().includes(q) ||
      (l.motivo || "").toLowerCase().includes(q);

    const byFecha = (l) => {
      const ts = parseTs(l.timestamp);
      switch (rangoSeleccionado) {
        case "24h": return ahoraTs - ts <= 24*60*60*1000;
        case "5d":  return ahoraTs - ts <= 5 *24*60*60*1000;
        case "7d":  return ahoraTs - ts <= 7 *24*60*60*1000;
        case "14d": return ahoraTs - ts <= 14*24*60*60*1000;
        case "personalizado": {
          if (!fechasPersonalizadas.inicio || !fechasPersonalizadas.fin) return true;
          const ini = new Date(fechasPersonalizadas.inicio).getTime();
          const fin = new Date(fechasPersonalizadas.fin).getTime() + (23*60*60+59*60+59)*1000;
          return ts >= ini && ts <= fin;
        }
        default: return true;
      }
    };

    return logsArray.filter(byText).filter(byFecha).sort((a,b)=>parseTs(b.timestamp)-parseTs(a.timestamp));
  }, [logsArray, busqueda, rangoSeleccionado, fechasPersonalizadas, ahoraTs]);

  // Agrupación
  const agrupados = useMemo(() => agruparLogsConIntervalos(logsFiltrados), [logsFiltrados]);

  // Paginación
  const totalPaginas = Math.ceil(agrupados.length / porPagina) || 1;
  const desde = (pagina - 1) * porPagina;
  const visibles = agrupados.slice(desde, desde + porPagina);

  // Microcopy
  const fechaLabel =
    rangoSeleccionado === "24h" ? "Últimas 24h" :
    rangoSeleccionado === "5d"  ? "Últimos 5 días" :
    rangoSeleccionado === "7d"  ? "Últimos 7 días" :
    rangoSeleccionado === "14d" ? "Últimos 14 días" :
    rangoSeleccionado === "personalizado"
      ? (fechasPersonalizadas.inicio && fechasPersonalizadas.fin
          ? `Personalizado: ${fmt(fechasPersonalizadas.inicio)} → ${fmt(fechasPersonalizadas.fin)}`
          : "Personalizado")
      : "Todo";
  const microcopy = `Mostrando: ${fechaLabel} · ${logsFiltrados.length} resultado${logsFiltrados.length===1?"":"s"}${busqueda?` · Filtro: “${busqueda}”`:""}`;

  // Exportar (respeta filtros)
  const exportarLogs = async (formato = "csv") => {
    const datosAEnviar = formato === "json" ? logsFiltrados : agrupados;
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/logs/exportar_logs?formato=${formato}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datosAEnviar) }
      );
      if (!res.ok) throw new Error("❌ Error al exportar");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `exportacion.${formato}`;
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch (err) { console.error("❌ Error exportando logs:", err); }
  };

  return (
    <div className="space-y-6">
      <BarraFiltros
        microcopy={microcopy}
        placeholderBusqueda="Buscar por usuario, tipo, detalle o motivo…"
        busqueda={busqueda}
        setBusqueda={(v)=>{ setBusqueda(v); setPagina(1); }}
        rangoSeleccionado={rangoSeleccionado}
        setRangoSeleccionado={(v)=>{ setRangoSeleccionado(v); setPagina(1); }}
        fechasPersonalizadas={fechasPersonalizadas}
        setFechasPersonalizadas={(v)=>{ setFechasPersonalizadas(v); setPagina(1); }}
        porPagina={porPagina}
        setPorPagina={(n)=>{ setPorPagina(n); setPagina(1); }}
      />

      {/* Listado */}
      <ul
        className="text-sm space-y-4"
        style={{ opacity: fadeOn ? 1 : 0, transform: fadeOn ? "translateY(0)" : "translateY(4px)", transition: "opacity 200ms ease, transform 200ms ease" }}
      >
        {visibles.map((entry, i) => (
          <li key={`${entry.usuario}-${entry.fecha}-${i}`} className="p-4 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200">
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

      {/* Paginación */}
      {totalPaginas > 1 && (
        <Paginacion
          pagina={pagina}
          totalPaginas={totalPaginas}
          totalItems={agrupados.length}
          porPagina={porPagina}
          onAnterior={() => setPagina((p) => Math.max(1, p - 1))}
          onSiguiente={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
        />
      )}

      {/* Exportaciones */}
      <div className="pt-4 border-t border-gray-200 flex flex-wrap gap-3">
        <button onClick={() => exportarLogs("csv")} className="px-5 py-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-indigo-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200">
          📄 Exportar CSV
        </button>
        <button onClick={() => exportarLogs("pdf")} className="px-5 py-2 rounded-2xl bg-gradient-to-r from-red-500 to-red-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200">
          🧾 Exportar PDF
        </button>
        <button onClick={() => exportarLogs("json")} className="px-5 py-2 rounded-2xl bg-gradient-to-r from-green-500 to-green-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200">
          🧠 Exportar JSON
        </button>
        <button onClick={() => exportarLogs("xlsx")} className="px-5 py-2 rounded-2xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-semibold shadow-md hover:shadow-lg hover:scale-[1.03] transition-all duration-200">
          📊 Exportar XLSX
        </button>
      </div>
    </div>
  );
}

/* Utils */
function formatHora(date) {
  return new Date(date).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", hour12: false }).replace(/\u200E/g,'');
}
function agruparLogsConIntervalos(logs) {
  const agrupados = {};
  logs.forEach(log => {
    const user = log.usuario_email;
    const fecha = new Date(log.timestamp).toLocaleDateString("es-ES");
    const time = new Date(log.timestamp);
    const tipo = (log.tipo || "").toLowerCase();
    const isManual = log.is_manual;
    const motivo = log.motivo || "";
    if (!user || !fecha || !tipo) return;
    if (!agrupados[user]) agrupados[user] = {};
    if (!agrupados[user][fecha]) agrupados[user][fecha] = [];
    agrupados[user][fecha].push({ tipo, time, isManual, motivo });
  });

  const resultado = [];
  for (const usuario in agrupados) {
    for (const fecha in agrupados[usuario]) {
      const logsDia = agrupados[usuario][fecha].sort((a,b)=>a.time-b.time);
      const intervalos = [];
      let entrada = null, entradaManual = false, motivoEntrada = "";
      let totalMs = 0;

      logsDia.forEach(({ tipo, time, isManual, motivo }) => {
        if (tipo === "entrada") {
          entrada = time; entradaManual = isManual; motivoEntrada = motivo;
        } else if (tipo === "salida" && entrada) {
          const durMs = time - entrada; totalMs += durMs;
          intervalos.push({
            entrada: formatHora(entrada),
            salida: formatHora(time),
            duracion: `${Math.floor(durMs/3600000)}h ${Math.floor((durMs/60000)%60)}m`,
            manualEntrada: entradaManual,
            manualSalida: isManual,
            motivoEntrada: motivoEntrada || "",
            motivoSalida: motivo || ""
          });
          entrada = null; motivoEntrada = "";
        }
      });

      const total = `${Math.floor(totalMs/3600000)}h ${Math.floor((totalMs/60000)%60)}m`;
      resultado.push({ usuario, fecha, intervalos, total });
    }
  }
  return resultado;
}
function fmt(iso){ if(!iso) return ""; const [y,m,d]=iso.split("-"); return `${d}/${m}/${y}`; }
