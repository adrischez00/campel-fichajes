// src/components/empleado/MisAusencias.jsx
import React from "react";

/*
  Componente 2025:
  - Glassmorphism + sombras suaves
  - Filtros: estado, tipo, fecha desde/hasta, búsqueda de motivo/subtipo
  - Ordenación client-side (multi-col, establece la principal con clic)
  - Paginación client-side
  - Export CSV / Copiar
  - Cabecera sticky + responsive
  - Accesible: atajos teclado (R refrescar, E exportar, C copiar, / foco búsqueda)
*/

const ESTADO_CLASE = {
  APROBADA: "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300/50",
  RECHAZADA: "bg-rose-100 text-rose-700 ring-1 ring-rose-300/50",
  PENDIENTE: "bg-amber-100 text-amber-700 ring-1 ring-amber-300/50",
};

const TIPO_BADGE = {
  VACACIONES:
    "bg-gradient-to-r from-indigo-500/15 to-indigo-400/15 text-indigo-800 ring-1 ring-indigo-300/40",
  BAJA:
    "bg-gradient-to-r from-rose-500/15 to-rose-400/15 text-rose-800 ring-1 ring-rose-300/40",
  "CITA MEDICA":
    "bg-gradient-to-r from-fuchsia-500/15 to-fuchsia-400/15 text-fuchsia-800 ring-1 ring-fuchsia-300/40",
  ASUNTOS_PROPIOS:
    "bg-gradient-to-r from-sky-500/15 to-sky-400/15 text-sky-800 ring-1 ring-sky-300/40",
  OTRA:
    "bg-gradient-to-r from-slate-500/15 to-slate-400/15 text-slate-800 ring-1 ring-slate-300/40",
};

const COLS = [
  { key: "tipo", label: "Tipo" },
  { key: "fechas", label: "Fechas" },
  { key: "parcial", label: "Parcial" },
  { key: "retribuida", label: "Retribuida" },
  { key: "estado", label: "Estado" },
  { key: "motivo", label: "Motivo" },
];

const fmtHora = (h) => (h ? String(h).slice(0, 5) : null);
const toISODate = (d) => (d instanceof Date ? d.toISOString().slice(0, 10) : d);

function toCSV(rows) {
  const header = ["Tipo", "Subtipo", "Fecha inicio", "Hora inicio", "Fecha fin", "Hora fin", "Parcial", "Retribuida", "Estado", "Motivo"];
  const lines = rows.map((a) => [
    a.tipo || "",
    a.subtipo || "",
    a.fecha_inicio || "",
    fmtHora(a.hora_inicio) || "",
    a.fecha_fin || "",
    fmtHora(a.hora_fin) || "",
    a.parcial ? "Sí" : "No",
    a.retribuida ? "Sí" : "No",
    a.estado || "",
    (a.motivo || "").replaceAll("\n", " "),
  ]);
  return [header, ...lines]
    .map((row) =>
      row
        .map((cell) => {
          const s = String(cell ?? "");
          return /[",;\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
        })
        .join(";")
    )
    .join("\n");
}

function useHotkeys(refs) {
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === "/" && refs.search?.current) {
        e.preventDefault();
        refs.search.current.focus();
      }
      if (e.key.toLowerCase() === "r" && refs.onRefresh) {
        e.preventDefault();
        refs.onRefresh();
      }
      if (e.key.toLowerCase() === "e" && refs.onExport) {
        e.preventDefault();
        refs.onExport();
      }
      if (e.key.toLowerCase() === "c" && refs.onCopy) {
        e.preventDefault();
        refs.onCopy();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [refs]);
}

export default function MisAusencias({ data = [], cargando, onRefrescar }) {
  const searchRef = React.useRef(null);

  const [estado, setEstado] = React.useState("TODOS");
  const [tipo, setTipo] = React.useState("TODOS");
  const [q, setQ] = React.useState("");
  const [desde, setDesde] = React.useState("");
  const [hasta, setHasta] = React.useState("");
  const [sort, setSort] = React.useState({ key: "fechas", dir: "desc" });
  const [page, setPage] = React.useState(1);
  const perPage = 10;

  // hotkeys
  useHotkeys({
    search: searchRef,
    onRefresh: onRefrescar,
    onExport: handleExport,
    onCopy: handleCopy,
  });

  // valores únicos para filtros
  const tiposUnicos = React.useMemo(() => {
    const set = new Set(data.map((d) => d.tipo).filter(Boolean));
    // Añadimos “OTRA” si hay tipos no mapeados
    return ["TODOS", ...Array.from(set)];
  }, [data]);

  const estadosUnicos = React.useMemo(() => {
    const set = new Set(data.map((d) => d.estado).filter(Boolean));
    return ["TODOS", ...Array.from(set)];
  }, [data]);

  // filtrar
  const filtradas = React.useMemo(() => {
    const lower = q.trim().toLowerCase();
    return (data || []).filter((a) => {
      if (estado !== "TODOS" && a.estado !== estado) return false;
      if (tipo !== "TODOS" && a.tipo !== tipo) return false;

      if (desde && (a.fecha_fin || a.fecha_inicio) < desde) return false;
      if (hasta && (a.fecha_inicio || a.fecha_fin) > hasta) return false;

      if (lower) {
        const texto = [
          a.tipo,
          a.subtipo,
          a.motivo,
          a.fecha_inicio,
          a.fecha_fin,
          fmtHora(a.hora_inicio),
          fmtHora(a.hora_fin),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!texto.includes(lower)) return false;
      }
      return true;
    });
  }, [data, estado, tipo, q, desde, hasta]);

  // ordenar
  const ordenadas = React.useMemo(() => {
    const arr = [...filtradas];
    const dir = sort.dir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      const key = sort.key;
      if (key === "tipo") {
        const at = `${a.tipo || ""} ${a.subtipo || ""}`.toLowerCase();
        const bt = `${b.tipo || ""} ${b.subtipo || ""}`.toLowerCase();
        return at > bt ? dir : at < bt ? -dir : 0;
      }
      if (key === "fechas") {
        const aKey = `${toISODate(a.fecha_inicio)} ${fmtHora(a.hora_inicio) || "00:00"}`;
        const bKey = `${toISODate(b.fecha_inicio)} ${fmtHora(b.hora_inicio) || "00:00"}`;
        return aKey > bKey ? dir : aKey < bKey ? -dir : 0;
      }
      if (key === "parcial" || key === "retribuida") {
        return (a[key] === b[key] ? 0 : a[key] ? 1 : -1) * dir;
      }
      if (key === "estado") {
        const order = { APROBADA: 3, PENDIENTE: 2, RECHAZADA: 1 };
        return ((order[a.estado] || 0) - (order[b.estado] || 0)) * dir;
      }
      if (key === "motivo") {
        const am = (a.motivo || "").toLowerCase();
        const bm = (b.motivo || "").toLowerCase();
        return am > bm ? dir : am < bm ? -dir : 0;
      }
      return 0;
    });
    return arr;
  }, [filtradas, sort]);

  // paginación
  const total = ordenadas.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  const paginated = React.useMemo(() => {
    const start = (page - 1) * perPage;
    return ordenadas.slice(start, start + perPage);
  }, [ordenadas, page]);

  React.useEffect(() => {
    setPage(1);
  }, [estado, tipo, q, desde, hasta]);

  function toggleSort(key) {
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  function handleExport() {
    const csv = toCSV(ordenadas);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const fecha = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `mis-ausencias_${fecha}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function handleCopy() {
    const csv = toCSV(ordenadas);
    try {
      await navigator.clipboard.writeText(csv);
      // opcional: toast simple
      console.info("Copiado al portapapeles");
    } catch (e) {
      console.warn("No se pudo copiar automáticamente");
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow-md p-3">
        <div className="flex flex-col xl:flex-row xl:items-center gap-3">
          {/* Filtros izquierda */}
          <div className="flex flex-1 flex-wrap items-center gap-2">
            <select
              value={estado}
              onChange={(e) => setEstado(e.target.value)}
              className="px-3 py-2 rounded-lg bg-white/70 border border-white/60 text-sm shadow-sm"
            >
              {estadosUnicos.map((op) => (
                <option key={op} value={op}>
                  {op[0] + op.slice(1).toLowerCase()}
                </option>
              ))}
            </select>

            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="px-3 py-2 rounded-lg bg-white/70 border border-white/60 text-sm shadow-sm"
            >
              {tiposUnicos.map((op) => (
                <option key={op} value={op}>
                  {op === "TODOS" ? "Todos los tipos" : op.replaceAll("_", " ")}
                </option>
              ))}
            </select>

            <div className="flex items-center gap-2">
              <input
                type="date"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
                className="px-3 py-2 rounded-lg bg-white/70 border border-white/60 text-sm shadow-sm"
                placeholder="Desde"
              />
              <span className="text-slate-400 text-sm">→</span>
              <input
                type="date"
                value={hasta}
                onChange={(e) => setHasta(e.target.value)}
                className="px-3 py-2 rounded-lg bg-white/70 border border-white/60 text-sm shadow-sm"
                placeholder="Hasta"
              />
            </div>
          </div>

          {/* Búsqueda + Acciones */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                ref={searchRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                type="text"
                placeholder="Buscar motivo, subtipo, fecha…  ( / )"
                className="pl-9 pr-3 py-2 rounded-lg bg-white/70 border border-white/60 text-sm shadow-sm w-64"
              />
              <span className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400">🔎</span>
            </div>

            <button
              onClick={onRefrescar}
              className="px-3 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 text-sm shadow-sm"
              title="Refrescar (R)"
            >
              ⟳
            </button>
            <button
              onClick={handleExport}
              className="px-3 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 text-sm shadow-sm"
              title="Exportar CSV (E)"
            >
              ⤓ CSV
            </button>
            <button
              onClick={handleCopy}
              className="px-3 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 text-sm shadow-sm"
              title="Copiar CSV (C)"
            >
              ⧉ Copiar
            </button>
          </div>
        </div>
      </div>

      {/* Tabla */}
      <div className="overflow-x-auto rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow-lg">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-white/70 backdrop-blur-xl">
            <tr className="text-slate-700">
              {COLS.map((c) => (
                <th
                  key={c.key}
                  onClick={() => toggleSort(c.key)}
                  className="px-4 py-3 text-left font-semibold cursor-pointer select-none"
                  title={`Ordenar por ${c.label}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.label}
                    <SortGlyph active={sort.key === c.key} dir={sort.dir} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={COLS.length} className="px-4 py-8 text-center text-slate-500">
                  Cargando…
                </td>
              </tr>
            ) : paginated.length === 0 ? (
              <tr>
                <td colSpan={COLS.length} className="px-4 py-10">
                  <EmptyState onClear={() => { setQ(""); setDesde(""); setHasta(""); setEstado("TODOS"); setTipo("TODOS"); }} />
                </td>
              </tr>
            ) : (
              paginated.map((a) => (
                <tr key={a.id} className="border-t border-white/60 hover:bg-white/70 transition">
                  {/* Tipo + subtipo */}
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded-lg ${TIPO_BADGE[a.tipo] || TIPO_BADGE.OTRA}`}>
                      {(a.tipo || "").replace("_", " ")}
                      {a.subtipo ? ` · ${a.subtipo}` : ""}
                    </span>
                  </td>

                  {/* Fechas */}
                  <td className="px-4 py-2">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
                      <span className="font-medium">{a.fecha_inicio}</span>
                      <span className="text-slate-400">→</span>
                      <span className="font-medium">{a.fecha_fin}</span>
                      {a.parcial && (
                        <span className="text-slate-600">
                          ({fmtHora(a.hora_inicio)} - {fmtHora(a.hora_fin)})
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Parcial */}
                  <td className="px-4 py-2">{a.parcial ? "Sí" : "No"}</td>

                  {/* Retribuida */}
                  <td className="px-4 py-2">{a.retribuida ? "Sí" : "No"}</td>

                  {/* Estado */}
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded-lg text-xs font-semibold ${ESTADO_CLASE[a.estado] || "bg-slate-100 text-slate-700 ring-1 ring-slate-300/50"}`}>
                      {a.estado}
                    </span>
                  </td>

                  {/* Motivo */}
                  <td className="px-4 py-2">
                    <span className="block max-w-[40ch] truncate text-slate-800" title={a.motivo || ""}>
                      {a.motivo || "—"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-600">
          {total === 0
            ? "0 resultados"
            : `${(page - 1) * perPage + 1}–${Math.min(page * perPage, total)} de ${total}`}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded-lg bg-white/70 border border-white/60 disabled:opacity-50"
          >
            ← Anterior
          </button>
          <span className="text-slate-600">
            Página <strong>{page}</strong> / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded-lg bg-white/70 border border-white/60 disabled:opacity-50"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </div>
  );
}

function SortGlyph({ active, dir }) {
  if (!active) return <span className="text-slate-300">↕</span>;
  return <span className="text-slate-600">{dir === "asc" ? "↑" : "↓"}</span>;
}

function EmptyState({ onClear }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-8">
      <div className="text-4xl mb-2">✨</div>
      <h4 className="text-lg font-semibold text-slate-800">Sin resultados</h4>
      <p className="text-slate-600 text-sm max-w-md">
        Ajusta los filtros o borra la búsqueda para ver más solicitudes.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={onClear}
          className="px-3 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 text-sm shadow-sm"
        >
          Limpiar filtros
        </button>
      </div>
    </div>
  );
}

