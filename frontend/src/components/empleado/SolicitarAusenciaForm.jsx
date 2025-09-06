// src/components/empleado/SolicitarAusenciaForm.jsx
import React from "react";
import { TIPOS, SUBTIPOS, TIPO_THEME, PARCIAL_SUGERENCIAS } from "../../utils/ausenciasCatalogo";
import { ausenciasService } from "../../services/ausencias";

const fmtH = (t) => (t ? String(t).slice(0, 5) : "");
const fmtFechaES = (iso) => {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  return iso;
};

// Fallback local (solo descuenta sábados y domingos) cuando no podamos validar
function diasLaborablesFallback(desde, hasta) {
  if (!desde || !hasta) return 0;
  const a = new Date(`${desde}T00:00:00`);
  const b = new Date(`${hasta}T00:00:00`);
  if (b < a) return 0;
  let c = 0;
  for (let d = new Date(a); d <= b; d.setDate(d.getDate() + 1)) {
    const wd = d.getDay(); // 0 D, 6 S
    if (wd !== 0 && wd !== 6) c += 1;
  }
  return c;
}

export default function SolicitarAusenciaForm({ token, emailUsuario }) {
  // Selección
  const [tipo, setTipo] = React.useState(TIPOS[1]); // por defecto Permisos
  const [subtipo, setSubtipo] = React.useState(null);

  // Rango y horas
  const [fechaInicio, setFechaInicio] = React.useState("");
  const [fechaFin, setFechaFin] = React.useState("");
  const [horaInicio, setHoraInicio] = React.useState("");
  const [horaFin, setHoraFin] = React.useState("");

  // Flags y campos
  const [parcial, setParcial] = React.useState(false);
  const [retribuida, setRetribuida] = React.useState(true);
  const [motivo, setMotivo] = React.useState("");

  // Estado de red/validación
  const [enviando, setEnviando] = React.useState(false);
  const [msg, setMsg] = React.useState("");
  const [rules, setRules] = React.useState([]);     // reglas de convenio
  const [reglaTipo, setReglaTipo] = React.useState(null);
  const [check, setCheck] = React.useState(null);   // respuesta /ausencias/validar
  const [checking, setChecking] = React.useState(false);
  const [valError, setValError] = React.useState("");

  // ===== efectos de inicialización =====
  // Cargar reglas una vez
  React.useEffect(() => {
    let mounted = true;
    ausenciasService
      .reglas(token)
      .then((r) => mounted && setRules(r?.rules || []))
      .catch(() => mounted && setRules([]));
    return () => (mounted = false);
  }, [token]);

  // Cuando cambie tipo → reset de subtipo y defaults del tipo
  React.useEffect(() => {
    const subs = SUBTIPOS[tipo.modelTipo] || [];
    setSubtipo(subs[0] || null);
    setParcial(Boolean(tipo.fixed?.parcial));
    setRetribuida(tipo.fixed?.retribuida ?? true);
  }, [tipo]);

  // Cuando cambie subtipo → aplicar defaults/sugerencias del subtipo
  React.useEffect(() => {
    if (!subtipo) return;
    const defs = subtipo.defaults || {};
    if (defs.parcial !== undefined) setParcial(defs.parcial);
    if (defs.retribuida !== undefined) setRetribuida(defs.retribuida);

    if ((defs.parcial || parcial) && subtipo.modelSubtipo in PARCIAL_SUGERENCIAS) {
      const s = PARCIAL_SUGERENCIAS[subtipo.modelSubtipo];
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
    if (tipo.modelTipo === "VACACIONES") {
      setParcial(false);
      setRetribuida(true);
      setHoraInicio("");
      setHoraFin("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subtipo]);

  // Regla activa del tipo seleccionado (permite mediodía, cómputo…)
  React.useEffect(() => {
    const r = (rules || []).find((x) => x.tipo === tipo.modelTipo) || null;
    setReglaTipo(r);
  }, [rules, tipo]);

  // ===== validación en vivo (debounce) =====
  const debounceRef = React.useRef(null);

  React.useEffect(() => {
    setValError("");
    setCheck(null);

    if (!fechaInicio || !fechaFin) return;
    if (new Date(`${fechaFin}T00:00:00`) < new Date(`${fechaInicio}T00:00:00`)) {
      setValError("El rango de fechas es inválido (hasta < desde).");
      return;
    }

    // Si el tipo no permite medio día, fuerza parcial=false
    if (parcial && (tipo.modelTipo === "VACACIONES" || !reglaTipo?.permite_mediodia)) {
      setParcial(false);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setChecking(true);
      try {
        const res = await ausenciasService.validar(token, {
          tipo: tipo.modelTipo,
          desde: fechaInicio,
          hasta: fechaFin,
          medio_dia: !!parcial,
        });
        setCheck(res);
        setValError(res.allowed ? "" : res.reason || "Solicitud no permitida");
      } catch (e) {
        // sin validador: no bloqueamos; mostramos fallback informativo
        setCheck(null);
        setValError(e?.message || "No se pudo validar (modo estimado).");
      } finally {
        setChecking(false);
      }
    }, 300);

    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [token, tipo.modelTipo, fechaInicio, fechaFin, parcial, reglaTipo]);

  // ===== cálculos derivados =====
  const theme = TIPO_THEME[tipo.modelTipo];

  const horasParciales = React.useMemo(() => {
    if (!parcial || !horaInicio || !horaFin) return 0;
    const [h1, m1] = horaInicio.split(":").map(Number);
    const [h2, m2] = horaFin.split(":").map(Number);
    const min = h2 * 60 + m2 - (h1 * 60 + m1);
    return Math.max(0, min);
  }, [parcial, horaInicio, horaFin]);

  const requestedDays = React.useMemo(() => {
    if (check?.requested_days != null) return check.requested_days;
    // fallback si no tenemos /validar
    if (!parcial) return diasLaborablesFallback(fechaInicio, fechaFin);
    return 0.5; // parcial sin validador → estimamos 0.5
  }, [check, parcial, fechaInicio, fechaFin]);

  const puedeEnviar =
    !!emailUsuario &&
    !!subtipo &&
    !!fechaInicio &&
    !!fechaFin &&
    !checking &&
    // si tenemos check, obedecemos allowed; si no, permitimos (fallback)
    (check ? !!check.allowed : true) &&
    // para parcial, horas coherentes
    (!parcial || (horaInicio && horaFin && horaFin > horaInicio));

  // ===== validaciones síncronas previas al submit =====
  function validateFields() {
    if (!emailUsuario) return "Usuario no válido.";
    if (!subtipo) return "Selecciona un motivo.";
    if (!fechaInicio || !fechaFin) return "Selecciona el rango de fechas.";
    if (new Date(`${fechaFin}T00:00:00`) < new Date(`${fechaInicio}T00:00:00`)) return "La fecha fin no puede ser anterior a la de inicio.";
    if (tipo.modelTipo === "VACACIONES" && parcial) return "Las vacaciones no pueden ser parciales.";
    if (parcial) {
      if (!horaInicio || !horaFin) return "Indica hora inicio y hora fin.";
      if (horaFin <= horaInicio) return "La hora fin debe ser mayor que la hora inicio.";
      if (reglaTipo && !reglaTipo.permite_mediodia) return "El convenio no permite medio día para este tipo.";
    }
    return null;
  }

  // ===== submit =====
  async function onSubmit(e) {
    e.preventDefault();
    setMsg("");
    const error = validateFields();
    if (error) {
      setMsg("❌ " + error);
      return;
    }

    // Revalida justo antes de enviar
    try {
      setChecking(true);
      const res = await ausenciasService.validar(token, {
        tipo: tipo.modelTipo,
        desde: fechaInicio,
        hasta: fechaFin,
        medio_dia: !!parcial,
      });
      setCheck(res);
      if (!res.allowed) {
        setMsg(
          "❌ " +
            (res.reason === "saldo_insuficiente"
              ? `No hay saldo suficiente. Pides ${res.requested_days}, disponibles ${res.available_days}.`
              : res.reason === "medio_dia_no_permitido"
              ? "El convenio no permite medio día para este tipo."
              : "Solicitud no permitida.")
        );
        return;
      }
    } catch {
      // si la validación falla por red, seguimos (pero lo indicamos)
      setMsg("⚠ No se pudo validar con el servidor; enviando igualmente…");
    } finally {
      setChecking(false);
    }

    // Construir payload para crear
    const payload = {
      usuario_email: emailUsuario,
      tipo: tipo.modelTipo,
      subtipo: subtipo.modelSubtipo,
      fecha_inicio: fechaInicio,
      fecha_fin: fechaFin,
      parcial: !!parcial,
      retribuida: !!retribuida,
      hora_inicio: parcial ? `${horaInicio}:00` : null,
      hora_fin: parcial ? `${horaFin}:00` : null,
      motivo: (motivo || "").trim(),
    };

    setEnviando(true);
    try {
      const created = await ausenciasService.crear(token, payload);
      setMsg(`✅ Solicitud enviada correctamente (#${created.id})`);
      // limpiar suave, manteniendo tipo/subtipo
      setFechaInicio("");
      setFechaFin("");
      setHoraInicio("");
      setHoraFin("");
      setParcial(Boolean(tipo.fixed?.parcial));
      setRetribuida(tipo.fixed?.retribuida ?? true);
      setMotivo("");
      setCheck(null);
    } catch (err) {
      setMsg("❌ " + (err?.message || "Error al crear la solicitud"));
    } finally {
      setEnviando(false);
    }
  }

  const subopts = SUBTIPOS[tipo.modelTipo] || [];
  const permiteMedio = !!reglaTipo?.permite_mediodia && tipo.modelTipo !== "VACACIONES";

  return (
    <form onSubmit={onSubmit} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Columna izquierda: formulario */}
      <div className="rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow p-5 space-y-4">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${TIPO_THEME[tipo.modelTipo]?.dot || "bg-slate-400"}`} />
          <h3 className="text-lg font-semibold text-slate-900">Solicitar Ausencia o Vacaciones</h3>
        </div>

        {/* Tipo / Subtipo */}
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
                <option key={t.modelTipo} value={t.modelTipo}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-600">Motivo / Subtipo</label>
            <select
              className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={subtipo?.modelSubtipo || ""}
              onChange={(e) => setSubtipo(subopts.find((s) => s.modelSubtipo === e.target.value) || null)}
            >
              {subopts.map((s) => (
                <option key={s.modelSubtipo} value={s.modelSubtipo}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Fechas */}
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-600">Fecha inicio</label>
            <input
              type="date"
              className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={fechaInicio}
              onChange={(e) => setFechaInicio(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">Fecha fin</label>
            <input
              type="date"
              className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
              value={fechaFin}
              onChange={(e) => setFechaFin(e.target.value)}
            />
          </div>
        </div>

        {/* Parcial / Retribuida */}
        <div className="flex flex-wrap items-center gap-6">
          <label className="inline-flex items-center gap-2" title={permiteMedio ? "" : "El convenio o el tipo no permite medio día"}>
            <input
              type="checkbox"
              className="accent-indigo-600"
              checked={parcial}
              onChange={(e) => setParcial(e.target.checked)}
              disabled={!permiteMedio}
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
                disabled={tipo.modelTipo === "VACACIONES"}
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
              <input
                type="time"
                className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
                value={horaInicio}
                onChange={(e) => setHoraInicio(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Hora fin</label>
              <input
                type="time"
                className="mt-1 w-full px-3 py-2 rounded-lg bg-white/70 border border-white/60 shadow-sm"
                value={horaFin}
                onChange={(e) => setHoraFin(e.target.value)}
              />
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
            disabled={enviando || !puedeEnviar}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 shadow"
          >
            {enviando ? "Enviando…" : "Solicitar"}
          </button>
          <button
            type="button"
            onClick={() => {
              setFechaInicio("");
              setFechaFin("");
              setHoraInicio("");
              setHoraFin("");
              setMotivo("");
              setParcial(Boolean(tipo.fixed?.parcial));
              setRetribuida(tipo.fixed?.retribuida ?? true);
              setMsg("");
              setCheck(null);
              setValError("");
            }}
            className="px-4 py-2 rounded-lg bg-white/70 hover:bg-white border border-white/60 shadow-sm"
          >
            Limpiar
          </button>
          {(msg || valError) && (
            <span
              className={`text-sm ${
                (msg && msg.startsWith("✅")) || (!msg && !valError) ? "text-emerald-700" : "text-rose-700"
              }`}
            >
              {msg || `❌ ${valError}`}
            </span>
          )}
        </div>
      </div>

      {/* Columna derecha: resumen en vivo */}
      <aside className="rounded-2xl bg-white/55 backdrop-blur-xl border border-white/50 shadow p-5 space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Resumen</h3>

        <div className={`p-3 rounded-xl ring-1 ${TIPO_THEME[tipo.modelTipo]?.ring || "ring-slate-300/40"} ${TIPO_THEME[tipo.modelTipo]?.bg || "bg-slate-500/10"}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className={`h-2.5 w-2.5 rounded-full ${TIPO_THEME[tipo.modelTipo]?.dot || "bg-slate-400"}`} />
            <span className={`text-sm font-medium ${TIPO_THEME[tipo.modelTipo]?.text || "text-slate-800"}`}>
              {tipo.label} · {subtipo?.label || "—"}
            </span>
          </div>
          <div className="text-sm text-slate-700">
            <div>
              <strong>Desde:</strong> {fmtFechaES(fechaInicio)} {parcial && horaInicio ? `(${fmtH(horaInicio)})` : ""}
            </div>
            <div>
              <strong>Hasta:</strong> {fmtFechaES(fechaFin)} {parcial && horaFin ? `(${fmtH(horaFin)})` : ""}
            </div>
            {!parcial ? (
              <div className="mt-1">
                <strong>Días solicitados:</strong>{" "}
                {checking ? "…" : check?.requested_days ?? diasLaborablesFallback(fechaInicio, fechaFin)}
                {check && (
                  <> &nbsp;· <strong>Disponibles:</strong> {check.available_days}</>
                )}
              </div>
            ) : (
              <div className="mt-1">
                <strong>Duración parcial:</strong> {Math.floor((horasParciales || 0) / 60)}h {(horasParciales || 0) % 60}m
              </div>
            )}
            <div className="mt-1">
              <strong>Cómputo:</strong> {check?.computo?.toLowerCase?.() || reglaTipo?.computo?.toLowerCase?.() || "laborables"} ·{" "}
              <strong>Mediodía:</strong> {reglaTipo?.permite_mediodia ? "sí" : "no"}
            </div>
            {check && !check.allowed && (
              <div className="mt-1 text-rose-700">
                {check.reason === "saldo_insuficiente"
                  ? `No hay saldo suficiente. Pides ${check.requested_days}, disponibles ${check.available_days}.`
                  : check.reason === "medio_dia_no_permitido"
                  ? "El convenio no permite medio día para este tipo."
                  : "Solicitud no permitida."}
              </div>
            )}
          </div>
        </div>

        {tipo.modelTipo === "VACACIONES" && (
          <div className="text-xs text-slate-600">Las vacaciones son de día completo y retribuidas. No se permiten parciales.</div>
        )}
      </aside>
    </form>
  );
}
