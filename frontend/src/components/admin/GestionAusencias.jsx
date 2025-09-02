// src/components/admin/GestionAusencias.jsx
import React, { useEffect, useState } from "react";
import { ausenciasService } from "../../services/ausencias";
import { toast } from "react-toastify";

export default function GestionAusencias({ token }) {
  const [ausencias, setAusencias] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filtroEstado, setFiltroEstado] = useState("PENDIENTE");

  function formatFecha(fecha) {
    return new Date(fecha).toLocaleDateString("es-ES");
  }

  async function cargarAusencias() {
    try {
      setLoading(true);
      const data = await ausenciasService.listarTodas(token);
      setAusencias(data);
    } catch (e) {
      toast.error(e.message || "Error al cargar ausencias");
    } finally {
      setLoading(false);
    }
  }

  async function aprobar(id) {
    if (!window.confirm("¿Aprobar esta ausencia?")) return;
    try {
      await ausenciasService.aprobar(token, id);
      toast.success("Ausencia aprobada ✅");
      cargarAusencias();
    } catch (e) {
      toast.error(e.message);
    }
  }

  async function rechazar(id) {
    const motivo = prompt("Motivo del rechazo:");
    if (!motivo) return;
    try {
      await ausenciasService.rechazar(token, id, motivo);
      toast.info("Ausencia rechazada");
      cargarAusencias();
    } catch (e) {
      toast.error(e.message);
    }
  }

  useEffect(() => {
    cargarAusencias();
  }, []);

  const filtradas = ausencias
    .filter(a => filtroEstado === "TODAS" ? true : a.estado === filtroEstado)
    .sort((a, b) => new Date(b.fecha_inicio) - new Date(a.fecha_inicio));

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Gestión de ausencias</h2>

      {/* Filtro por estado */}
      <div className="flex gap-2">
        {["PENDIENTE", "APROBADA", "RECHAZADA", "TODAS"].map(est => (
          <button
            key={est}
            className={`px-3 py-1 rounded-lg border text-sm ${
              filtroEstado === est
                ? "bg-indigo-600 text-white"
                : "bg-white text-slate-700 hover:bg-slate-50"
            }`}
            onClick={() => setFiltroEstado(est)}
          >
            {est.charAt(0) + est.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Tabla */}
      <div className="overflow-x-auto bg-white rounded-xl border">
        <table className="w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-4 py-2 text-left">Empleado</th>
              <th className="px-4 py-2 text-left">Tipo</th>
              <th className="px-4 py-2 text-left">Fechas</th>
              <th className="px-4 py-2 text-left">Parcial</th>
              <th className="px-4 py-2 text-left">Retribuida</th>
              <th className="px-4 py-2 text-left">Estado</th>
              <th className="px-4 py-2 text-left">Motivo</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {filtradas.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                  No hay solicitudes
                </td>
              </tr>
            )}
            {filtradas.map(a => (
              <tr key={a.id} className="border-t">
                <td className="px-4 py-2">{a.usuario_email}</td>
                <td className="px-4 py-2">{a.tipo.replace("_", " ")}</td>
                <td className="px-4 py-2">
                  {formatFecha(a.fecha_inicio)} → {formatFecha(a.fecha_fin)}
                  {a.parcial &&
                    ` (${a.hora_inicio?.slice(0,5)} - ${a.hora_fin?.slice(0,5)})`}
                </td>
                <td className="px-4 py-2">{a.parcial ? "Sí" : "No"}</td>
                <td className="px-4 py-2">{a.retribuida ? "Sí" : "No"}</td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-1 rounded-lg text-xs font-medium ${
                      a.estado === "PENDIENTE"
                        ? "bg-yellow-100 text-yellow-700"
                        : a.estado === "APROBADA"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {a.estado}
                  </span>
                </td>
                <td className="px-4 py-2">{a.motivo || "—"}</td>
                <td className="px-4 py-2 flex gap-2">
                  {a.estado === "PENDIENTE" && (
                    <>
                      <button
                        onClick={() => aprobar(a.id)}
                        className="px-2 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Aprobar
                      </button>
                      <button
                        onClick={() => rechazar(a.id)}
                        className="px-2 py-1 bg-red-600 text-white rounded-lg hover:bg-red-700"
                      >
                        Rechazar
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {loading && <p className="text-sm text-slate-500">Cargando…</p>}
    </div>
  );
}

