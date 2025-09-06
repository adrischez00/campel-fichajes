// src/components/empleado/SaldoVacacionesWidget.jsx
import { useEffect, useState } from "react";
import { ausenciasService } from "@/services/ausencias"; // ⬅️ cambia el import

export default function SaldoVacacionesWidget({ tipos = ["VACACIONES", "LIBRE_DISPOSICION"] }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let mounted = true;
    ausenciasService
      .balance() // ⬅️ antes getBalance()
      .then((d) => mounted && setData(d))
      .catch((e) => mounted && setErr(e.message || "Error"));
    return () => { mounted = false; };
  }, []);

  if (err) return <div className="saldo error">Error: {err}</div>;
  if (!data) return <div className="saldo loading">Cargando saldos…</div>;

  const saldos = (data.saldos || []).filter((s) => tipos.includes(s.tipo));
  const anio = data.anio ?? new Date().getFullYear();

  return (
    <div className="saldo grid" style={{ display: "grid", gap: 12 }}>
      <h3>Mis saldos {anio}</h3>
      {saldos.map((s) => {
        const total = (s.asignado || 0) + (s.arrastre || 0);
        const used = s.gastado || 0;
        const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
        return (
          <div key={s.tipo} className="card" style={{ border: "1px solid #e3e3e3", borderRadius: 8, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <strong>{s.tipo}</strong>
              <span>Disponible: <b>{s.disponible}</b></span>
            </div>
            <div title={`Gastado ${used}/${total}`}>
              <div style={{ height: 8, background: "#eee", borderRadius: 999 }}>
                <div style={{ width: `${pct}%`, height: 8, borderRadius: 999, background: "#1a73e8" }} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: "#666", marginTop: 6 }}>
              Cómputo: {s.computo} · Mediodía: {s.permite_mediodia ? "sí" : "no"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
