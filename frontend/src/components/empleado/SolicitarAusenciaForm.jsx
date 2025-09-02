// src/components/empleado/SolicitarAusenciaForm.jsx
import React from "react";
import { TIPOS, SUBTIPOS, TIPO_THEME, PARCIAL_SUGERENCIAS } from "../../utils/ausenciasCatalogo";
import { API_URL } from "../../services/api";

const fmtH = (t) => (t ? String(t).slice(0, 5) : "");
const toDate = (v) => (v ? new Date(v + "T00:00:00") : null);
const fmtFechaES = (iso) => {
  if (!iso) return "—";
  // ya viene como YYYY-MM-DD desde <input type="date">
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  // si alguna vez llega dd/mm/aaaa, devuélvelo tal cual
  return iso;
};


// Fallback local (solo descuenta sábados y domingos) por si falla la API
function diasLaborablesFallback(fechaIni, fechaFin) {
  if (!fechaIni || !fechaFin) return 0;
  const a = toDate(fechaIni);
  const b = toDate(fechaFin);
  if (b < a) return 0;
  let c = 0;
  for (let d = new Date(a); d <= b; d.setDate(d.getDate() + 1)) {
    const wd = d.getDay(); // 0 D, 6 S
    if (wd !== 0 && wd !== 6) c += 1;
  }
  return c;
}

export default function SolicitarAusenciaForm({ token, emailUsuario }) {
  const [tipo, setTipo] = React.useState(TIPOS[1]); // por defecto Permisos
  const [subtipo, setSubtipo] = React.useState(null);

  const [fechaInicio, setFechaInicio] = React.useState("");
  const [fechaFin, setFechaFin] = React.useState("");
  const [horaInicio, setHoraInicio] = React.useState("");
  const [horaFin, setHoraFin] = React.useState("");

  const [parcial, setParcial] = React.useState(false);
  const [retribuida, setRetribuida] = React.useState(true);
  const [motivo, setMotivo] = React.useState("");
  const [enviando, setEnviando] = React.useState(false);
  const [msg, setMsg] = React.useState("");

  // NUEVO: estado para los días laborables calculados por backend
  const [dias, setDias] = React.useState(0);

  // Cuando cambie tipo → reset subtipo y defaults
  React.useEffect(() => {
    const subs = SUBTIPOS[tipo.modelTipo] || [];
    setSubtipo(subs[0] || null);

    // Defaults por tipo
    setParcial(Boolean(tipo.fixed?.parcial));
    setRetribuida(tipo.fixed?.retribuida ?? true);
  }, [tipo]);

  // Cuando cambie subtipo → aplicar defaults de subtipo si existen
  React.useEffect(() => {
    if (!subtipo) return;
    const defs = subtipo.defaults || {};
    if (defs.parcial !== undefined) setParcial(defs.parcial);
    if (defs.retribuida !== undefined) setRetribuida(defs.retribuida);

    // Sugerencias parciales
    if ((defs.parcial || parcial) && subtipo.modelSubtipo in PARCIAL_SUGERENCIAS) {
      const s = PARCIAL_SUGERENCIAS[subtipo.modelSubtipo];
      // si no hay horas puestas, sugerimos
      if (!horaInicio) setHoraInicio("09:00");
      if (!horaFin) {
        const [h, m] = (horaInicio || "09:00").split(":").map(Number);
        const hi = h * 60 + m;
        const hf = hi + (s.horas || 0) * 60 + (s.minutos || 0);
        const H = String(Math.floor(hf / 60)).padStart(2, "0");
        const M = String(hf % 60).padStart(2, "0");
        setHoraFin(`${H}:${M}`);
      }
    }
    // Vacaciones: forzar no parcial + retribuida true
    if (tipo.modelTipo === "VACACIONES") {
      setParcial(false);
      setRetribuida(true);
      setHoraInicio("");
      setHoraFin("");
    }
  }, [subtipo]); // eslint-disable-line

  const theme = TIPO_THEME[tipo.modelTipo];

  // NUEVO: cálculo de días laborables desde el backend (descuenta festivos)
  React.useEffect(() => {
    const run = async () => {
      if (parcial || !fechaInicio || !fechaFin) { setDias(0); return; }
      try {
        const url = `${API_URL}/calendar/working-days?start=${fechaInicio}&end=${fechaFin}`;
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setDias(Number(data?.working_days ?? 0));
        } else {
          // Fallback local si falla la API
          setDias(diasLaborablesFallback(fechaInicio, fechaFin));
        }
      } catch {
        setDias(diasLaborablesFallback(fechaInicio, fechaFin));
      }
    };
    run();
  }, [fechaInicio, fechaFin, parcial, token]);

  const horasParciales = React.useMemo(() => {
    if (!parcial || !horaInicio || !horaFin) return 0;
    const [h1, m1] = horaInicio.split(":").map(Number);
    const [h2, m2] = horaFin.split(":").map(Number);
    const min = h2 * 60 + m2 - (h1 * 60 + m1);
    return Math.max(0, min);
  }, [parcial, horaInicio, horaFin]);

  function validate() {
    setMsg("");
    if (!emailUsuario) return "Usuario no válido.";
    if (!subtipo) return "Selecciona un motivo.";
    if (!fechaInicio || !fechaFin) return "Selecciona el rango de fechas.";
    if (new Date(fechaFin) < new Date(fechaInicio)) return "La fecha fin no puede ser anterior a la de inicio.";

    if (tipo.modelTipo === "VACACIONES" && parcial) return "Las vacaciones no pueden ser parciales.";
    if (parcial) {
      if (!horaInicio || !horaFin) return "Indica hora inicio y hora fin.";
      if (horaFin <= horaInicio) return "La hora fin debe ser mayor que la hora inicio.";
    }
    return null;
  }

  async function onSubmit(e) {
    e.preventDefault();
    const error = validate();
    if (error) {
      setMsg("❌ " + error);
      return;
    }
    setEnviando(true);
    try {
      const res = await fetch(`${API_URL}/ausencias/crear`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          usuario_email: emailUsuario,
          tipo: tipo.modelTipo,
          subtipo: subtipo.modelSubtipo,
          fecha_inicio: fechaInicio,
          fecha_fin: fechaFin,
          hora_inicio: parcial ? `${horaInicio}:00` : null,
          hora_fin: parcial ? `${horaFin}:00` : null,
          parcial,
          retribuida,
          motivo: (motivo || "").trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Error al crear la solicitud");
      }
      setMsg("✅ Solicitud enviada correctamente");
      // limpiar suave, manteniendo tipo/subtipo
      setFechaInicio("");
      setFechaFin("");
      setHoraInicio("");
      setHoraFin("");
      setParcial(Boolean(tipo.fixed?.parcial));
      setRetribuida(tipo.fixed?.retribuida ?? true);
      setMotivo("");
    } catch (err) {
      setMsg("❌ " + err.message);
    } finally {
      setEnviando(false);
    }
  }

  const subopts = SUBTIPOS[tipo.modelTipo] || [];

  return (
    <form onSubmit={onSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Columna izquierda: formulario */}
      <div className="rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow p-5 space-y-4">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${theme?.dot || "bg-slate-400"}`} />
          <h3 className="text-lg font-semibold text-slate-900">Solicitar Ausencia o Vacaciones</h3>
        </div>

        {/* Tipo */}
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-600">Tipo de solicitud</label>
            <select
              className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={tipo.modelTipo}
              onChange={(e) => {
                const t = TIPOS.find((x) => x.modelTipo === e.target.value);
                setTipo(t || TIPOS[0]);
              }}
            >
              {TIPOS.map((t) => (
                <option key={t.modelTipo} value={t.modelTipo}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-600">Motivo / Subtipo</label>
            <select
              className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={subtipo?.modelSubtipo || ""}
              onChange={(e) => setSubtipo(subopts.find(s => s.modelSubtipo === e.target.value) || null)}
            >
              {subopts.map((s) => (
                <option key={s.modelSubtipo} value={s.modelSubtipo}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Fechas y horas */}
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-600">Fecha inicio</label>
            <input type="date" className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">Fecha fin</label>
            <input type="date" className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={fechaFin} onChange={(e) => setFechaFin(e.target.value)} />
          </div>
        </div>

        {/* Parcial / Retribuida */}
        <div className="flex flex-wrap items-center gap-6">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              className="accent-indigo-600"
              checked={parcial}
              onChange={(e) => setParcial(e.target.checked)}
              disabled={tipo.modelTipo === "VACACIONES" || Boolean(tipo.fixed?.parcial)}
            />
            <span className="text-sm">Parcial</span>
          </label>

          <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                className="accent-indigo-600"
                checked={retribuida}
                onChange={(e) => setRetribuida(e.target.checked)}
                disabled={tipo.modelTipo === "VACACIONES"} // vacaciones siempre retribuidas
              />
              <span className="text-sm">Retribuida</span>
            </label>
            <span className="text-xs text-slate-500">(si la política lo permite)</span>
          </div>
        </div>

        {/* Horas si parcial */}
        {parcial && (
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-600">Hora inicio</label>
              <input type="time" className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
                value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Hora fin</label>
              <input type="time" className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
                value={horaFin} onChange={(e) => setHoraFin(e.target.value)} />
            </div>
          </div>
        )}

        {/* Observaciones */}
        <div>
          <label className="text-xs font-medium text-slate-600">Motivo (opcional)</label>
          <textarea
            rows={3}
            className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Añade detalles si es necesario…"
          />
        </div>

        {/* Acciones */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={enviando}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 shadow"
          >
            {enviando ? "Enviando…" : "Solicitar"}
          </button>
          <button
            type="button"
            onClick={() => {
              setFechaInicio(""); setFechaFin(""); setHoraInicio(""); setHoraFin("");
              setMotivo(""); setParcial(Boolean(tipo.fixed?.parcial)); setRetribuida(tipo.fixed?.retribuida ?? true);
            }}
            className="px-4 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 shadow-sm"
          >
            Limpiar
          </button>
          {msg && (
            <span className={`text-sm ${msg.startsWith("✅") ? "text-emerald-700" : "text-rose-700"}`}>{msg}</span>
          )}
        </div>
      </div>

      {/* Columna derecha: resumen en vivo */}
      <aside className="rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow p-5 space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Resumen</h3>

        <div className={`p-3 rounded-xl ring-1 ${theme?.ring || "ring-slate-300/40"} ${theme?.bg || "bg-slate-500/10"}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className={`h-2.5 w-2.5 rounded-full ${theme?.dot || "bg-slate-400"}`} />
            <span className={`text-sm font-medium ${theme?.text || "text-slate-800"}`}>
              {tipo.label} · {subtipo?.label || "—"}
            </span>
          </div>
          <div className="text-sm text-slate-700">
            <div><strong>Desde:</strong> {fmtFechaES(fechaInicio)} {parcial && horaInicio ? `(${fmtH(horaInicio)})` : ""}</div>
            <div><strong>Hasta:</strong> {fmtFechaES(fechaFin)} {parcial && horaFin ? `(${fmtH(horaFin)})` : ""}</div>
            {!parcial ? (
              <div className="mt-1"><strong>Días laborables:</strong> {dias || 0}</div>
            ) : (
              <div className="mt-1"><strong>Duración parcial:</strong> {Math.floor(horasParciales/60)}h {horasParciales%60}m</div>
            )}
            <div className="mt-1"><strong>Retribuida:</strong> {retribuida ? "Sí" : "No"}</div>
          </div>
        </div>

        {/* Panel informativo por tipo */}
        {tipo.modelTipo === "VACACIONES" && (
          <div className="text-xs text-slate-600">
            Las vacaciones son de día completo y retribuidas. No se permiten parciales.
          </div>
        )}
        {tipo.modelTipo === "REGISTRO_JORNADA" && (
          <div className="text-xs text-slate-600">
            Las compensaciones descuentan del saldo de horas y **bloquean el fichaje** en el tramo seleccionado (ya cubierto por el backend).
          </div>
        )}
      </aside>
    </form>
  );
}
