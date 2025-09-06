// src/components/empleado/SaldoVacacionesWidget.jsx
import { useEffect, useState } from "react";
import { getBalance } from "../../services/ausencias";      // ✅ ruta correcta
import { getAccessToken } from "../../services/api";        // ✅ ruta correcta

export default function SaldoVacacionesWidget({
  tipos = ["VACACIONES", "LIBRE_DISPOSICION"],
}) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let mounted = true;
    const token = getAccessToken();
    getBalance(token)
      .then((d) => mounted && setData(d))
      .catch((e) => mounted && setErr(e?.message || "Error"));
    return () => {
      mounted = false;
    };
  }, []);

  if (err) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 text-rose-700 p-3 text-sm">
        Error cargando saldos: {err}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white/60 p-3 text-sm">
        Cargando saldos…
      </div>
    );
  }

  const saldos = (data.saldos || []).filter((s) => tipos.includes(s.tipo));

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-slate-800">
        Mis saldos {data.anio}
      </h4>

      {saldos.map((s) => {
        const total = (s.asignado || 0) + (s.arrastre || 0);
        const used = s.gastado || 0;
        const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;

        return (
          <div
            key={s.tipo}
            className="rounded-xl border border-white/60 bg-white/70 p-3 shadow-sm"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="text-sm font-medium text-slate-800">{s.tipo}</div>
              <div className="text-xs text-slate-600">
                Disponible: <b>{s.disponible}</b>
              </div>
            </div>

            <div className="h-2 w-full rounded-full bg-slate-200" title={`Gastado ${used}/${total}`}>
              <div
                className="h-2 rounded-full bg-blue-600"
                style={{ width: `${pct}%` }}
              />
            </div>

            <div className="mt-1 text-[11px] text-slate-500">
              Cómputo: {s.computo} · Mediodía: {s.permite_mediodia ? "sí" : "no"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
