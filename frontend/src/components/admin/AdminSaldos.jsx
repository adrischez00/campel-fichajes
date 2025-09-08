// src/components/admin/AdminSaldos.jsx
import React from "react";
import { api } from "../../services/api";
import { ausenciasService } from "../../services/ausencias";

const yearsAround = (n = 2) => {
  const y = new Date().getFullYear();
  return Array.from({ length: n * 2 + 1 }, (_, i) => y - n + i);
};

export default function AdminSaldos({ token }) {
  const [usuarios, setUsuarios] = React.useState([]);
  const [email, setEmail] = React.useState("");
  const [year, setYear] = React.useState(new Date().getFullYear());
  const [loading, setLoading] = React.useState(false);
  const [saldos, setSaldos] = React.useState([]);

  // carga usuarios (solo admin) para el selector
  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const list = await api.get("/usuarios", token);
        if (mounted) setUsuarios(list || []);
      } catch {
        if (mounted) setUsuarios([]);
      }
    })();
    return () => (mounted = false);
  }, [token]);

  const cargar = React.useCallback(async () => {
    if (!email) return;
    setLoading(true);
    try {
      const r = await ausenciasService.getBalance(token, { email, year });
      setSaldos(r?.saldos || []);
    } catch {
      setSaldos([]);
    } finally {
      setLoading(false);
    }
  }, [token, email, year]);

  // acción: ajustar saldo (modal simplificado via prompt)
  async function onAjustar(tipo) {
    const deltaStr = window.prompt(`Delta en días para ${tipo} (ej: +1, -0.5):`, "");
    if (!deltaStr) return;
    const delta = Number(deltaStr.replace(",", "."));
    if (!Number.isFinite(delta) || delta === 0) return;

    const motivo = window.prompt("Motivo del ajuste:", "") || "";
    const fecha = new Date().toISOString().slice(0, 10);

    try {
      await ausenciasService.crearMovimiento(token, {
        usuario_email: email,
        year,
        tipo,
        fecha,
        delta,
        motivo,
      });
      await cargar();
      alert("Ajuste creado correctamente.");
    } catch (e) {
      alert(`Error creando ajuste: ${e?.message || "desconocido"}`);
    }
  }

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex flex-wrap items-end gap-3 bg-white/60 border border-white/40 rounded-xl p-4">
        <div>
          <label className="block text-xs text-slate-600">Usuario (email)</label>
          <select
            className="mt-1 px-3 py-2 rounded-lg border bg-white/80 min-w-[260px]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          >
            <option value="">— Selecciona usuario —</option>
            {usuarios.map((u) => (
              <option key={u.id} value={u.email}>{u.email}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-600">Año</label>
          <select
            className="mt-1 px-3 py-2 rounded-lg border bg-white/80"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {yearsAround(2).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <button
          onClick={cargar}
          disabled={!email || loading}
          className="px-4 h-10 rounded-lg bg-indigo-600 text-white disabled:opacity-50"
        >
          {loading ? "Cargando…" : "Cargar"}
        </button>
      </div>

      {/* Tabla de saldos */}
      <div className="bg-white/60 border border-white/40 rounded-xl p-4">
        {!email ? (
          <p className="text-sm text-slate-600">Selecciona un usuario para ver sus saldos…</p>
        ) : saldos.length === 0 ? (
          <p className="text-sm text-slate-600">No hay saldos para {email} en {year}.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th className="px-3 py-2">Tipo</th>
                  <th className="px-3 py-2">Cómputo</th>
                  <th className="px-3 py-2">Mediodía</th>
                  <th className="px-3 py-2">D. anuales</th>
                  <th className="px-3 py-2">Asignado</th>
                  <th className="px-3 py-2">Arrastre</th>
                  <th className="px-3 py-2">Gastado</th>
                  <th className="px-3 py-2 font-semibold">Disponible</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {saldos.map((s) => (
                  <tr key={s.tipo} className="border-t">
                    <td className="px-3 py-2 font-medium">{s.tipo}</td>
                    <td className="px-3 py-2">{s.computo}</td>
                    <td className="px-3 py-2">{s.permite_mediodia ? "sí" : "no"}</td>
                    <td className="px-3 py-2">{s.dias_anuales}</td>
                    <td className="px-3 py-2">{s.asignado}</td>
                    <td className="px-3 py-2">{s.arrastre}</td>
                    <td className="px-3 py-2">{s.gastado}</td>
                    <td className="px-3 py-2 font-semibold">{s.disponible}</td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => onAjustar(s.tipo)}
                        className="px-3 py-1 rounded bg-emerald-600 text-white text-xs"
                      >
                        Ajustar…
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
