// src/components/empleado/AusenciasCalendario.jsx
import React from "react";
import { fetchUserCalendarEvents, fetchUserWorkingDays} from "../../services/api";

/* ============================
   Paletas y helpers visuales
   ============================ */
const estadoDot = {
  APROBADA: "bg-emerald-500",
  PENDIENTE: "bg-amber-500",
  RECHAZADA: "bg-rose-500",
  FESTIVO: "bg-sky-500",
};

const tipoBadgeMap = {
  VACACIONES:
    "bg-gradient-to-r from-indigo-500/20 to-indigo-400/20 text-indigo-800 ring-1 ring-indigo-300/40",
  BAJA:
    "bg-gradient-to-r from-rose-500/20 to-rose-400/20 text-rose-800 ring-1 ring-rose-300/40",
  "CITA MEDICA":
    "bg-gradient-to-r from-fuchsia-500/20 to-fuchsia-400/20 text-fuchsia-800 ring-1 ring-fuchsia-300/40",
  CITA_MEDICA:
    "bg-gradient-to-r from-fuchsia-500/20 to-fuchsia-400/20 text-fuchsia-800 ring-1 ring-fuchsia-300/40",
  ASUNTOS_PROPIOS:
    "bg-gradient-to-r from-sky-500/20 to-sky-400/20 text-sky-800 ring-1 ring-sky-300/40",
  OTRA:
    "bg-gradient-to-r from-slate-500/20 to-slate-400/20 text-slate-800 ring-1 ring-slate-300/40",
  FESTIVO:
    "bg-gradient-to-r from-sky-500/20 to-sky-400/20 text-sky-800 ring-1 ring-sky-300/40",
  FESTIVO_NACIONAL:
    "bg-gradient-to-r from-sky-500/20 to-sky-400/20 text-sky-800 ring-1 ring-sky-300/40",
  FESTIVO_REGION:
    "bg-gradient-to-r from-teal-500/20 to-teal-400/20 text-teal-800 ring-1 ring-teal-300/40",
  FESTIVO_PROVINCIA:
    "bg-gradient-to-r from-cyan-500/20 to-cyan-400/20 text-cyan-800 ring-1 ring-cyan-300/40",
  FESTIVO_LOCAL:
    "bg-gradient-to-r from-blue-500/20 to-blue-400/20 text-blue-800 ring-1 ring-blue-300/40",
  FESTIVO_EMPRESA:
    "bg-gradient-to-r from-violet-500/20 to-violet-400/20 text-violet-800 ring-1 ring-violet-300/40",
};
const getTipoBadge = (t) => {
  const k1 = String(t || "").toUpperCase();
  const k2 = k1.replaceAll("_", " ");
  return tipoBadgeMap[k1] || tipoBadgeMap[k2] || tipoBadgeMap.OTRA;
};

const weekHead = ["L", "M", "X", "J", "V", "S", "D"];

const fmtHora = (h) => String(h || "").slice(0, 5);
const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate();

const toKey = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;

const fromKey = (k) => {
  const [y, m, d] = k.split("-").map((n) => parseInt(n, 10));
  return new Date(y, m - 1, d);
};

// Normaliza a medianoche
const atMidnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

// Convierte rangos a días: { "YYYY-MM-DD": [ausencias] }
function expandRangesToDays(items) {
  const byDay = {};
  for (const a of items || []) {
    const fi = new Date(a.fecha_inicio);
    const ff = new Date(a.fecha_fin);
    const d = new Date(fi.getFullYear(), fi.getMonth(), fi.getDate());
    const end = new Date(ff.getFullYear(), ff.getMonth(), ff.getDate());
    while (d <= end) {
      const key = toKey(d);
      if (!byDay[key]) byDay[key] = [];
      byDay[key].push(a);
      d.setDate(d.getDate() + 1);
    }
  }
  return byDay;
}

/* ============================
   Ranges helpers (merge etc.)
   ============================ */
const normalizeRange = (r) => {
  if (!r?.start || !r?.end) return null;
  const a = atMidnight(r.start);
  const b = atMidnight(r.end);
  return a <= b ? { start: a, end: b } : { start: b, end: a };
};

const mergeRanges = (ranges) => {
  const rs = (ranges || [])
    .map(normalizeRange)
    .filter(Boolean)
    .sort((a, b) => a.start - b.start);
  if (rs.length === 0) return [];
  const out = [rs[0]];
  for (let i = 1; i < rs.length; i++) {
    const prev = out[out.length - 1];
    const cur = rs[i];
    const nextDay = new Date(prev.end);
    nextDay.setDate(nextDay.getDate() + 1);
    if (cur.start <= nextDay) {
      if (cur.end > prev.end) prev.end = cur.end;
    } else {
      out.push({ ...cur });
    }
  }
  return out;
};

const dateInAnyRange = (d, ranges) => {
  const t = atMidnight(d).getTime();
  for (const r of ranges || []) {
    const a = atMidnight(r.start).getTime();
    const b = atMidnight(r.end).getTime();
    if (t >= a && t <= b) return true;
  }
  return false;
};

const rangesStats = (ranges, byDay) => {
  if (!ranges?.length) return null;
  let days = 0,
    totalItems = 0,
    parciales = 0;
  const estados = { APROBADA: 0, PENDIENTE: 0, RECHAZADA: 0 };

  for (const r of ranges) {
    const start = atMidnight(r.start);
    const end = atMidnight(r.end);
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      days++;
      const arr = byDay[toKey(d)] || [];
      totalItems += arr.length;
      parciales += arr.filter((x) => x.parcial).length;
      arr.forEach((x) => (estados[x.estado] = (estados[x.estado] || 0) + 1));
    }
  }
  return { rangesCount: ranges.length, days, total: totalItems, parciales, estados };
};

/* ===== Helpers toggle día en rangos ===== */
const sameDate = (a, b) => atMidnight(a).getTime() === atMidnight(b).getTime();

function removeDayFromRanges(ranges, day) {
  const d = atMidnight(day);
  const out = [];
  for (const r of ranges) {
    const a = atMidnight(r.start);
    const b = atMidnight(r.end);
    if (d < a || d > b) {
      out.push({ ...r });
      continue;
    }
    if (sameDate(a, b)) {
      continue;
    } else if (sameDate(d, a)) {
      const na = new Date(a);
      na.setDate(na.getDate() + 1);
      out.push({ start: na, end: b });
    } else if (sameDate(d, b)) {
      const nb = new Date(b);
      nb.setDate(nb.getDate() - 1);
      out.push({ start: a, end: nb });
    } else {
      const leftEnd = new Date(d);
      leftEnd.setDate(leftEnd.getDate() - 1);
      const rightStart = new Date(d);
      rightStart.setDate(rightStart.getDate() + 1);
      out.push({ start: a, end: leftEnd }, { start: rightStart, end: b });
    }
  }
  return mergeRanges(out);
}

function dayInRanges(ranges, day) {
  return dateInAnyRange(day, ranges);
}

/* ============================
   Tooltip y Modal
   ============================ */
function Tooltip({ children, open, anchorRef }) {
  const [pos, setPos] = React.useState({ top: 0, left: 0 });

  React.useLayoutEffect(() => {
    if (!open || !anchorRef?.current) return;
    const r = anchorRef.current.getBoundingClientRect();
    setPos({
      top: r.top + window.scrollY + r.height + 8,
      left: r.left + window.scrollX + Math.min(r.width / 2, 140),
    });
  }, [open, anchorRef]);

  if (!open) return null;

  return (
    <div
      className="fixed z-50 pointer-events-none transform -translate-x-1/2 transition-opacity duration-150"
      style={{ top: pos.top, left: pos.left }}
      role="tooltip"
    >
      <div className="backdrop-blur-xl bg-white/80 dark:bg-slate-900/70 text-slate-800 dark:text-slate-100 border border-white/60 dark:border-white/10 shadow-xl rounded-xl px-3 py-2 max-w-xs">
        {children}
      </div>
    </div>
  );
}

function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div className="relative w-full sm:max-w-lg sm:rounded-2xl bg-white/85 backdrop-blur-xl border border-white/60 shadow-2xl p-4 sm:p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700">
            Cerrar
          </button>
        </div>
        <div className="max-h-[70vh] overflow-auto">{children}</div>
      </div>
    </div>
  );
}

/* ============================
   Export CSV de selección
   ============================ */
function exportarSeleccionCSV(data, ranges) {
  const rs = mergeRanges(ranges);
  if (!rs.length) return;
  const rows = [
    ["Tipo", "Subtipo", "Parcial", "Retribuida", "Fecha inicio", "Hora inicio", "Fecha fin", "Hora fin", "Estado", "Motivo"],
  ];
  for (const a of data || []) {
    const ai = atMidnight(new Date(a.fecha_inicio));
    const af = new Date(a.fecha_fin + "T23:59:59");
    const cae = rs.some((r) => !(af < r.start || ai > r.end));
    if (!cae) continue;
    rows.push([
      a.tipo || "",
      a.subtipo || "",
      a.parcial ? "Sí" : "No",
      a.retribuida ? "Sí" : "No",
      a.fecha_inicio || "",
      a.hora_inicio || "",
      a.fecha_fin || "",
      a.hora_fin || "",
      a.estado || "",
      String(a.motivo || "").replace(/\n/g, " "),
    ]);
  }
  const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const first = rs[0].start.toISOString().slice(0, 10);
  const last = rs[rs.length - 1].end.toISOString().slice(0, 10);
  a.href = url;
  a.download = `ausencias_${first}_${last}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ============================
   Calendario
   ============================ */
export default function AusenciasCalendario({
  data = [],
  cargando,
  onNeedData,
  onPrefill,
  userId,           // usamos esto para /events y /working-days
  apiRoot = "",     // sigue aceptándose pero ya no se usa (api.js tiene API_URL)
}) {
  const today = new Date();
  const [cursor, setCursor] = React.useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [monthsView, setMonthsView] = React.useState(1);
  const [hoverKey, setHoverKey] = React.useState(null);
  const [modalKey, setModalKey] = React.useState(null);

  // Selección multi-rango
  const [selectedRanges, setSelectedRanges] = React.useState([]);
  const [anchorDate, setAnchorDate] = React.useState(null);
  const [dragging, setDragging] = React.useState(false);
  const [dragIndex, setDragIndex] = React.useState(null);
  const [dragFixedStart, setDragFixedStart] = React.useState(null);
  const anchorRef = React.useRef(null);
  const suppressClickRef = React.useRef(false);

  // Festivos filtrados por backend
  const [eventsByDay, setEventsByDay] = React.useState({}); // { 'YYYY-MM-DD': [pseudoFestivo] }

  // Días laborables (respuesta del backend)
  const [workingDaysCount, setWorkingDaysCount] = React.useState(null);

  const byDay = React.useMemo(() => expandRangesToDays(data), [data]);

  const goPrev = () => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - monthsView, 1));
  const goNext = () => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + monthsView, 1));
  const goToday = () => setCursor(new Date(today.getFullYear(), today.getMonth(), 1));

  const months = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  const years = React.useMemo(() => {
    const base = today.getFullYear();
    const arr = [];
    for (let y = base - 5; y <= base + 2; y++) arr.push(y);
    return arr;
  }, [today]);

  const onChangeMonth = (e) => setCursor(new Date(cursor.getFullYear(), parseInt(e.target.value, 10), 1));
  const onChangeYear = (e) => setCursor(new Date(parseInt(e.target.value, 10), cursor.getMonth(), 1));

  // Rango visible (para pedir feed unificado)
  const visibleRange = React.useMemo(() => {
    const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const end = new Date(cursor.getFullYear(), cursor.getMonth() + monthsView, 0);
    return { start, end };
  }, [cursor, monthsView]);

  /* ==========================================
     Feed unificado (mantengo TU llamada con userId)
     ========================================== */
  React.useEffect(() => {
    let alive = true;
    let aborter = new AbortController();

    (async () => {
      try {
        const s = visibleRange.start.toISOString().slice(0, 10);
        const e = visibleRange.end.toISOString().slice(0, 10);
        if (!s || !e) return;

        const events = await fetchUserCalendarEvents(userId, s, e);

        // Dedupe y quedarnos SOLO con FESTIVO
        const acc = {};
        const seen = new Set();
        for (const ev of events || []) {
          if (String(ev.type).toUpperCase() !== "FESTIVO") continue;
          const k = String(ev.fecha).slice(0, 10);
          const sig = `${k}|${ev.titulo}|FESTIVO`;
          if (seen.has(sig)) continue;
          seen.add(sig);
          const pseudo = {
            tipo: "FESTIVO",
            estado: "FESTIVO",
            parcial: false,
            retribuida: true,
            fecha_inicio: k,
            fecha_fin: k,
            hora_inicio: null,
            hora_fin: null,
            motivo: ev.titulo || "",
          };
          if (!acc[k]) acc[k] = [];
          acc[k].push(pseudo);
        }
        if (alive) setEventsByDay(acc);
      } catch {
        if (alive) setEventsByDay({});
      }
    })();

    return () => {
      alive = false;
      aborter.abort();
    };
  }, [visibleRange.start.getTime(), visibleRange.end.getTime(), userId]);



 // Pedir días laborables al backend cuando cambie la selección (único efecto)
 React.useEffect(() => {
   const rs = mergeRanges(selectedRanges);
   if (!rs.length || userId == null) {
     setWorkingDaysCount(null);
     return;
   }
   const s = rs[0].start.toISOString().slice(0, 10);
   const e = rs[0].end.toISOString().slice(0, 10);
   (async () => {
     try {
       const { working_days } = await fetchUserWorkingDays(userId, s, e);
       setWorkingDaysCount(typeof working_days === "number" ? working_days : null);
     } catch {
       setWorkingDaysCount(null);
     }
   })();
 }, [selectedRanges, userId]);

  // Keyboard nav + limpiar con Esc
  const onKeyDown = (e) => {
    if (e.key === "ArrowLeft") goPrev();
    else if (e.key === "ArrowRight") goNext();
    else if (e.key === "Home") setCursor(new Date(cursor.getFullYear(), 0, 1));
    else if (e.key === "End") setCursor(new Date(cursor.getFullYear(), 11, 1));
    else if (e.key === "PageUp") goPrev();
    else if (e.key === "PageDown") goNext();
    else if (e.key === "Escape") {
      setSelectedRanges([]);
      setAnchorDate(null);
    }
  };

  // Click / Shift-click / Ctrl-click
  const onDayClick = (dateObj, evt) => {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    const d = atMidnight(dateObj);

    if (!evt?.shiftKey && !evt?.metaKey && !evt?.ctrlKey && dayInRanges(selectedRanges, d)) {
      setSelectedRanges(removeDayFromRanges(selectedRanges, d));
      setAnchorDate(d);
      return;
    }

    if (evt?.metaKey || evt?.ctrlKey) {
      if (dayInRanges(selectedRanges, d)) {
        setSelectedRanges(removeDayFromRanges(selectedRanges, d));
      } else {
        const merged = mergeRanges([...selectedRanges, { start: d, end: d }]);
        setSelectedRanges(merged);
      }
      setAnchorDate(d);
      return;
    }

    if (evt?.shiftKey && anchorDate) {
      let ranges = [...selectedRanges];
      if (ranges.length === 0) {
        ranges = [{ start: anchorDate, end: d }];
      } else {
        ranges[ranges.length - 1] = normalizeRange({ start: anchorDate, end: d });
      }
      setSelectedRanges(mergeRanges(ranges));
      return;
    }

    setSelectedRanges([{ start: d, end: d }]);
    setAnchorDate(d);
  };

  /* ===== Arrastre robusto ===== */
  const onMouseDownDay = (dateObj, e) => {
    e.preventDefault();
    const d = atMidnight(dateObj);

    if (e?.shiftKey && anchorDate) {
      suppressClickRef.current = true;
      const temp = normalizeRange({ start: anchorDate, end: d });
      const merged = mergeRanges([...selectedRanges, temp]);
      setSelectedRanges(merged);
      setDragIndex(merged.length - 1);
      setDragFixedStart(anchorDate);
      setDragging(true);
      return;
    }

    if (e?.metaKey || e?.ctrlKey) {
      suppressClickRef.current = true;
      const merged = mergeRanges([...selectedRanges, { start: d, end: d }]);
      setSelectedRanges(merged);
      setAnchorDate(d);
      setDragIndex(merged.length - 1);
      setDragFixedStart(d);
      setDragging(true);
      return;
    }

    setDragging(true);
    setDragIndex(null);
    setDragFixedStart(d);
    setAnchorDate(d);
  };

  const onMouseEnterDay = (dateObj) => {
    if (!dragging) return;
    const d = atMidnight(dateObj);
    setSelectedRanges((prev) => {
      let copy = [...prev];

      if (dragIndex == null) {
        const created = normalizeRange({ start: dragFixedStart || d, end: d });
        const merged = mergeRanges([...copy, created]);
        suppressClickRef.current = true;
        setDragIndex(merged.length - 1);
        return merged;
      }

      if (!copy[dragIndex]) return prev;
      copy[dragIndex] = normalizeRange({
        start: dragFixedStart || copy[dragIndex].start,
        end: d,
      });
      return mergeRanges(copy);
    });
  };

  const onMouseUp = () => {
    setDragging(false);
    setDragIndex(null);
    setDragFixedStart(null);
  };

  React.useEffect(() => {
    if (!dragging) return;
    const up = () => {
      setDragging(false);
      setDragIndex(null);
      setDragFixedStart(null);
    };
    window.addEventListener("mouseup", up);
    window.addEventListener("mouseleave", up);
    return () => {
      window.removeEventListener("mouseup", up);
      window.removeEventListener("mouseleave", up);
    };
  }, [dragging]);

  const inSelected = (d) => dateInAnyRange(d, selectedRanges);

  // Estadísticas de selección
  const selectionStats = React.useMemo(() => rangesStats(selectedRanges, byDay), [selectedRanges, byDay]);

  // Festivos dentro de la selección (solo eventsByDay)
  const festivosEnSeleccion = React.useMemo(() => {
    if (!selectedRanges?.length) return 0;
    const rs = mergeRanges(selectedRanges);
    let n = 0;
    for (const r of rs) {
      for (let d = new Date(r.start); d <= r.end; d.setDate(d.getDate() + 1)) {
        const k = toKey(d);
        const arr = eventsByDay[k] || [];
        n += arr.filter((x) => String(x.estado) === "FESTIVO").length;
      }
    }
    return n;
  }, [selectedRanges, eventsByDay]);

  /* ===== NUEVO: fines de semana y “no laborables” (solo UI) ===== */
  const weekendCount = React.useMemo(() => {
    const rs = mergeRanges(selectedRanges);
    let n = 0;
    for (const r of rs) {
      const d = new Date(r.start);
      for (; d <= r.end; d.setDate(d.getDate() + 1)) {
        const wd = d.getDay(); // 0=domingo, 6=sábado
        if (wd === 0 || wd === 6) n++;
      }
    }
    return n;
  }, [selectedRanges]);

  const totalSeleccionados = selectionStats?.days || 0;
  const noLaborables =
    typeof workingDaysCount === "number"
      ? Math.max(0, totalSeleccionados - workingDaysCount)
      : null;

  const noLaborablesTitle =
    noLaborables == null
      ? ""
      : `Sáb+Dom: ${weekendCount}\nFestivos: ${festivosEnSeleccion}\nOtros: ${Math.max(
          0,
          totalSeleccionados - workingDaysCount - weekendCount - festivosEnSeleccion
        )}`;

  // Prefill para el formulario
  const solicitarConSeleccion = () => {
    const rs = mergeRanges(selectedRanges);
    if (!rs.length) return;
    const s = rs[0].start;
    const e = rs[0].end;
    if (typeof onPrefill === "function") {
      onPrefill(s, e);
    } else {
      try {
        sessionStorage.setItem(
          "ausencias_prefill",
          JSON.stringify({
            fecha_inicio: s.toISOString().slice(0, 10),
            fecha_fin: e.toISOString().slice(0, 10),
          })
        );
      } catch {}
      const params = new URLSearchParams(window.location.search);
      params.set("tab", "solicitar");
      window.history.pushState({}, "", "?" + params.toString());
      alert(
        rs.length > 1
          ? "Se han prefijado las fechas del primer rango seleccionado en el formulario."
          : "Fechas prefijadas en el formulario de solicitud."
      );
    }
  };

  // Render de un mes
  const renderMonth = (baseYear, baseMonth) => {
    const first = new Date(baseYear, baseMonth, 1);
    const last = new Date(baseYear, baseMonth + 1, 0);
    const firstWeekday = (first.getDay() + 6) % 7; // 0 = lunes
    const daysInMonth = last.getDate();
    const totalCells = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;

    return (
      <div key={`${baseYear}-${baseMonth}`} className="space-y-1">
        {monthsView > 1 && (
          <div className="flex items-center justify-between px-1">
            <div className="text-sm font-semibold text-slate-800">
              {months[baseMonth][0].toUpperCase() + months[baseMonth].slice(1)} {baseYear}
            </div>
            <div className="grid grid-cols-7 text-[11px] text-slate-500">
              {weekHead.map((d) => (
                <div key={d} className="px-2 py-0.5 text-center">
                  {d}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-7 gap-1 overflow-x-auto md:overflow-visible select-none">
          {Array.from({ length: totalCells }).map((_, idx) => {
            const dayNum = idx - firstWeekday + 1;
            const inMonth = dayNum >= 1 && dayNum <= daysInMonth;
            const dateObj = inMonth ? new Date(baseYear, baseMonth, dayNum) : null;
            const key = inMonth ? toKey(dateObj) : "";
            const items = inMonth
              ? [...(byDay[key] || []), ...(eventsByDay[key] || [])]
              : [];
            const isToday = inMonth && sameDay(dateObj, today);
            const highlighted = inMonth && inSelected(dateObj);

            return (
              <div
                key={idx}
                ref={inMonth && hoverKey === key ? anchorRef : null}
                className={`relative min-h-[110px] rounded-2xl border p-2 group focus-within:ring-2 focus-within:ring-indigo-300 transition
                  ${
                    inMonth
                      ? highlighted
                        ? "bg-indigo-50/70 border-indigo-200 shadow-sm"
                        : "bg-white/55 border-white/50 hover:bg-white/70"
                      : "bg-white/25 border-white/40 opacity-60"
                  }`}
                onMouseDownCapture={(e) => inMonth && onMouseDownDay(dateObj, e)}
                onMouseOverCapture={() => inMonth && onMouseEnterDay(dateObj)}
                onDoubleClick={() => inMonth && setModalKey(key)}
                onClick={(e) => inMonth && onDayClick(dateObj, e)}
                onMouseEnter={() => inMonth && setHoverKey(key)}
                onMouseLeave={() => setHoverKey((prev) => (prev === key ? null : prev))}
              >
                {/* Número de día + dots de estado */}
                <div className="flex items-center justify-between">
                  <button
                    onClick={(e) => { e.stopPropagation(); setModalKey(key); }}
                    className={`text-xs font-bold rounded-full px-2 py-0.5 ${
                      isToday ? "bg-indigo-600 text-white shadow" : "text-slate-800 hover:bg-slate-100"
                    }`}
                    title="Ver detalle del día"
                  >
                    {inMonth ? dayNum : ""}
                  </button>

                  <div className="flex -space-x-1">
                    {items.slice(0, 3).map((a, i) => (
                      <span
                        key={i}
                        className={`h-2.5 w-2.5 rounded-full border border-white shadow ${estadoDot[a.estado] || "bg-slate-400"}`}
                        title={`${a.estado} · ${a.tipo}`}
                      />
                    ))}
                    {items.length > 3 && <span className="text-[10px] text-slate-600 ml-1">+{items.length - 3}</span>}
                  </div>
                </div>

                {/* Badges tipo + parcial */}
                {items.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {items.slice(0, 3).map((a, i) => {
                      const tipo = (a.tipo || "").replaceAll("_", " ");
                      const rango =
                        a.parcial && a.hora_inicio && a.hora_fin ? ` · ${fmtHora(a.hora_inicio)}–${fmtHora(a.hora_fin)}` : "";
                      return (
                        <li
                          key={i}
                          className={`text-[11px] leading-tight px-2 py-1 rounded-lg ${getTipoBadge(a.tipo)} truncate`}
                          title={`${a.estado} · ${tipo}${rango}`}
                        >
                          <span className="font-semibold">{tipo}</span>
                          <span className="text-slate-600">{rango}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}

                {/* Overlay accesible solo focus teclado */}
                <button
                  tabIndex={-1}
                  className="absolute inset-0 outline-none rounded-2xl focus:ring-2 focus:ring-indigo-300 pointer-events-none"
                  aria-label={`Día ${dayNum}. ${items.length || "sin"} ausencias.`}
                />
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // Meses visibles
  const monthsGrid = [];
  for (let i = 0; i < monthsView; i++) {
    const d = new Date(cursor.getFullYear(), cursor.getMonth() + i, 1);
    monthsGrid.push(renderMonth(d.getFullYear(), d.getMonth()));
  }

  // Chips de rangos seleccionados
  const chips = mergeRanges(selectedRanges);

  return (
    <div className="space-y-4" onKeyDown={onKeyDown} onMouseUp={onMouseUp} tabIndex={0}>
      {/* Barra superior */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-2">
          <button onClick={goPrev} className="px-3 py-2 rounded-lg bg-white/40 hover:bg-white/60 border border-white/60 shadow-sm transition" title="Periodo anterior">‹</button>
          <button onClick={goToday} className="px-3 py-2 rounded-lg bg-white/40 hover:bg-white/60 border border-white/60 shadow-sm transition" title="Ir a hoy">Hoy</button>
          <button onClick={goNext} className="px-3 py-2 rounded-lg bg-white/40 hover:bg-white/60 border border-white/60 shadow-sm transition" title="Periodo siguiente">›</button>
        </div>

        {/* Mes/Año + Vista */}
        <div className="flex items-center gap-2">
          <select value={cursor.getMonth()} onChange={onChangeMonth} className="px-3 py-2 rounded-lg bg-white/60 border border-white/60 shadow-sm">
            {months.map((m, i) => <option key={m} value={i}>{m[0].toUpperCase() + m.slice(1)}</option>)}
          </select>
          <select value={cursor.getFullYear()} onChange={onChangeYear} className="px-3 py-2 rounded-lg bg-white/60 border border-white/60 shadow-sm">
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>

          <select value={monthsView} onChange={(e) => setMonthsView(parseInt(e.target.value, 10))} className="px-3 py-2 rounded-lg bg-white/60 border border-white/60 shadow-sm" title="Cambiar vista">
            <option value={1}>1 mes</option>
            <option value={2}>2 meses</option>
            <option value={6}>6 meses</option>
            <option value={12}>12 meses (año)</option>
          </select>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />Aprobada</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" />Pendiente</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Rechazada</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-sky-500" />Festivo</span>
          </div>

          <button onClick={onNeedData} className="px-3 py-2 rounded-lg bg-white/40 hover:bg-white/60 border border-white/60 shadow-sm transition" title="Refrescar">⟳</button>
        </div>
      </div>

      {/* Chips de rangos seleccionados */}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {chips.map((r, idx) => (
            <span key={idx} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/70 border border-white/60 backdrop-blur-md text-sm">
              {r.start.toLocaleDateString("es-ES")} — {r.end.toLocaleDateString("es-ES")}
              <button
                onClick={() =>
                  setSelectedRanges((prev) =>
                    prev.filter((x) => !(x.start.getTime() === r.start.getTime() && x.end.getTime() === r.end.getTime()))
                  )
                }
                className="ml-1 text-slate-600 hover:text-rose-600"
                title="Quitar rango"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {cargando ? (
        <p className="text-sm text-slate-600">Cargando calendario…</p>
      ) : (
        <>
          {monthsView === 1 && (
            <div className="grid grid-cols-7 text-xs font-semibold text-slate-700">
              {weekHead.map((d) => (
                <div key={d} className="px-2 py-1 text-center">
                  {d}
                </div>
              ))}
            </div>
          )}

          {/* Rejilla de meses */}
          <div
            className={
              monthsView === 1
                ? "space-y-3"
                : monthsView === 2
                ? "grid grid-cols-1 md:grid-cols-2 gap-4"
                : monthsView === 6
                ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
                : "grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-4"
            }
          >
            {monthsGrid}
          </div>

          {/* Barra de selección (stats + acciones) */}
          {selectionStats && (
            <div className="mt-3 rounded-2xl border border-white/60 bg-white/55 backdrop-blur-md p-3 flex flex-wrap items-center gap-3 text-sm">
              <span className="font-semibold">
                Selección: {selectionStats.rangesCount} rango(s), {selectionStats.days} día(s)
                {" · "}
                <span className="text-indigo-700">
                  Laborables:{" "}
                  <strong>
                    {typeof workingDaysCount === "number"
                      ? workingDaysCount
                      : (selectedRanges?.length ? "…" : "—")}
                  </strong>
                </span>
                {" · "}
                <span className="text-sky-700">
                  Festivos: <strong>{festivosEnSeleccion}</strong>
                </span>
              </span>

              <span className="text-slate-700">
                Ausencias: {selectionStats.total} · Parciales: {selectionStats.parciales}
              </span>

              <span className="inline-flex items-center gap-2">
                <span className="inline-flex items-center gap-1 text-emerald-700">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" /> {selectionStats.estados.APROBADA || 0}
                </span>
                <span className="inline-flex items-center gap-1 text-amber-700">
                  <span className="h-2 w-2 rounded-full bg-amber-500" /> {selectionStats.estados.PENDIENTE || 0}
                </span>
                <span className="inline-flex items-center gap-1 text-rose-700">
                  <span className="h-2 w-2 rounded-full bg-rose-500" /> {selectionStats.estados.RECHAZADA || 0}
                </span>
              </span>

              <div className="ml-auto flex items-center gap-2">
                <button onClick={() => exportarSeleccionCSV(data, selectedRanges)} className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700">
                  Exportar selección
                </button>
                <button onClick={solicitarConSeleccion} className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700">
                  Solicitar con estas fechas
                </button>
                <button
                  onClick={() => { setSelectedRanges([]); setAnchorDate(null); }}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
                >
                  Limpiar selección
                </button>
              </div>
            </div>
          )}




          {/* Leyenda por tipo */}
          <div className="flex flex-wrap items-center gap-2 text-[11px] mt-3">
            {["VACACIONES", "BAJA", "CITA MEDICA", "ASUNTOS_PROPIOS", "OTRA"].map((tipo) => (
              <span key={tipo} className={`px-2 py-1 rounded-md ${getTipoBadge(tipo)} capitalize`}>
                {tipo.replaceAll("_", " ").toLowerCase()}
              </span>
            ))}
            {["FESTIVO"].map((tipo) => (
              <span key={tipo} className={`px-2 py-1 rounded-md ${getTipoBadge(tipo)} capitalize`}>
                festivo
              </span>
            ))}
          </div>

          {/* Lista móvil */}
          <div className="mt-4 md:hidden">
            <h4 className="text-sm font-semibold mb-2">Lista (móvil)</h4>
            <div className="space-y-2">
              {Object.entries({ ...byDay, ...eventsByDay }).map(([k, _]) => {
                const arr = [...(byDay[k] || []), ...(eventsByDay[k] || [])];
                return (
                  <div key={k} className="rounded-xl border bg-white/60 backdrop-blur-md p-3">
                    <div className="text-sm font-medium mb-1">{new Date(k).toLocaleDateString("es-ES")}</div>
                    {arr.map((a, i) => (
                      <div key={i} className="text-xs text-slate-800">
                        <span className={`inline-block h-2 w-2 rounded-full align-middle mr-1 ${estadoDot[a.estado] || "bg-slate-400"}`} />
                        <span className="font-semibold">{(a.tipo || "").replaceAll("_", " ")}</span>
                        {a.parcial && a.hora_inicio && a.hora_fin && <span className="text-slate-600"> ({fmtHora(a.hora_inicio)}–{fmtHora(a.hora_fin)})</span>}
                        <span className="ml-2 text-slate-600">{a.estado}</span>
                        {a.motivo && <div className="text-[11px] opacity-80">“{a.motivo}”</div>}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Modal detalle del día */}
          <Modal
            open={!!modalKey}
            onClose={() => setModalKey(null)}
            title={
              modalKey
                ? fromKey(modalKey).toLocaleDateString("es-ES", {
                    weekday: "long",
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })
                : ""
            }
          >
            {modalKey ? (
              (() => {
                const merged = [...(byDay[modalKey] || []), ...(eventsByDay[modalKey] || [])];
                return merged.length > 0 ? (
                  <div className="space-y-2">
                    {merged.map((a, i) => (
                      <div key={i} className={`rounded-lg p-3 ${getTipoBadge(a.tipo)}`}>
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold">
                            {(a.tipo || "").replaceAll("_", " ")}
                            {a.parcial && a.hora_inicio && a.hora_fin && (
                              <span className="font-normal text-slate-700"> · {fmtHora(a.hora_inicio)}–{fmtHora(a.hora_fin)}</span>
                            )}
                          </div>
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-white/70">
                            <span className={`h-2 w-2 rounded-full ${estadoDot[a.estado] || "bg-slate-400"}`} />
                            {a.estado}
                          </span>
                        </div>
                        {a.motivo && <div className="text-sm mt-1 text-slate-800">“{a.motivo}”</div>}
                        <div className="text-xs text-slate-600 mt-1">
                          {new Date(a.fecha_inicio).toLocaleDateString("es-ES")} — {new Date(a.fecha_fin).toLocaleDateString("es-ES")}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-slate-700">Sin ausencias ni festivos este día.</div>
                );
              })()
            ) : (
              <div className="text-sm text-slate-700">Sin ausencias ni festivos este día.</div>
            )}
          </Modal>
        </>
      )}
    </div>
  );
}
