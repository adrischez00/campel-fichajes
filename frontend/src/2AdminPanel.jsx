import { useEffect, useState } from 'react';
import { API_URL } from './api';
import Header from './Header';

export default function AdminPanel({ session, onLogout }) {
  const [solicitudes, setSolicitudes] = useState([]);
  const [logs, setLogs] = useState([]);
  const [msg, setMsg] = useState('');
  const [mostrarLogs, setMostrarLogs] = useState(false);
  const [mostrarRegistro, setMostrarRegistro] = useState(false);
  const { token, user } = session;

  const cargarSolicitudes = async () => {
    try {
      const res = await fetch(`${API_URL}/solicitudes`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setSolicitudes(data);
    } catch (err) {
      console.error("❌ Error cargando solicitudes:", err);
    }
  };

  const cargarLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/logs`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setLogs(data);
    } catch (err) {
      console.error("❌ Error cargando logs:", err);
    }
  };

  const resolver = async (id, aprobar) => {
    try {
      await fetch(`${API_URL}/resolver-solicitud`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ id, aprobar })
      });
      cargarSolicitudes();
    } catch (err) {
      console.error("❌ Error resolviendo solicitud:", err);
    }
  };

  const exportarLogsCSV = () => {
    const csv = logs.map(l =>
      `${l.usuario_email || "desconocido"},${l.accion},${l.detalle.replace(/,/g, ' ')},${new Date(l.timestamp).toLocaleString()}`
    ).join('\n');
    const blob = new Blob(["Usuario,Acción,Detalle,Fecha\n" + csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'logs_auditoria.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    cargarSolicitudes();
    cargarLogs();
  }, []);

  const crearUsuario = async (e) => {
    e.preventDefault();
    const form = e.target;
    const nuevo = {
      email: form.email.value,
      password: form.password.value,
      role: form.role.value,
    };
    try {
      const res = await fetch(`${API_URL}/registrar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          usuario: user
        },
        body: JSON.stringify(nuevo),
      });
      if (res.ok) {
        setMsg("✅ Usuario creado correctamente");
        form.reset();
        cargarLogs();
      } else {
        const err = await res.json();
        setMsg("❌ " + err.detail);
      }
    } catch (err) {
      console.error("❌ Error creando usuario:", err);
      setMsg("❌ Error de conexión al crear usuario");
    }
  };

  return (
    <div className="min-h-screen bg-[#F4F6F8]">
      <Header usuario={user} onLogout={onLogout} />

      <main className="max-w-3xl mx-auto p-6 space-y-8">
        <section className="bg-white p-6 rounded-2xl shadow">
          <button
            onClick={() => {
              const email = prompt("¿Email del empleado?");
              if (!email) return;
              window.open(`${API_URL}/exportar-pdf?usuario=${email}`, "_blank");
            }}
            className="bg-blue-700 text-white px-4 py-2 rounded hover:bg-blue-800 transition"
          >
            Exportar fichajes a PDF
          </button>
        </section>

        <section className="bg-white p-6 rounded-2xl shadow">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-xl font-semibold text-[#004B87]">Registrar nuevo usuario</h2>
            <button
              onClick={() => setMostrarRegistro(!mostrarRegistro)}
              className="text-sm text-indigo-600 hover:underline"
            >
              {mostrarRegistro ? 'Ocultar' : 'Mostrar'}
            </button>
          </div>

          {mostrarRegistro && (
            <form onSubmit={crearUsuario} className="space-y-3 max-w-md">
              <input name="email" type="email" required placeholder="Correo" className="border p-2 w-full rounded" />
              <input name="password" type="password" required placeholder="Contraseña" className="border p-2 w-full rounded" />
              <select name="role" className="border p-2 w-full rounded">
                <option value="employee">Empleado</option>
                <option value="admin">Administrador</option>
              </select>
              <button className="bg-green-700 text-white px-4 py-2 rounded w-full hover:bg-green-800 transition">
                Crear usuario
              </button>
              {msg && <p className="text-sm mt-2">{msg}</p>}
            </form>
          )}
        </section>

        <section className="bg-white p-6 rounded-2xl shadow">
          <h2 className="text-xl font-semibold text-[#004B87] mb-4">Solicitudes de fichajes manuales</h2>
          <ul className="space-y-2">
            {solicitudes.map((s) => (
              <li key={s.id} className="border p-4 rounded">
                <p><strong>{s.usuario_email || "Usuario desconocido"}</strong> solicita <strong>{s.tipo}</strong> el {s.fecha} a las {s.hora}</p>
                <p>Motivo: {s.motivo}</p>
                <p>Estado: <span className="font-semibold">{s.estado}</span></p>
                {s.estado === "pendiente" && (
                  <div className="mt-3 flex gap-2">
                    <button className="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 transition" onClick={() => resolver(s.id, true)}>Aprobar</button>
                    <button className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 transition" onClick={() => resolver(s.id, false)}>Rechazar</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-white p-6 rounded-2xl shadow">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-xl font-semibold text-[#004B87]">Logs de auditoría</h2>
            <button
              onClick={() => setMostrarLogs(!mostrarLogs)}
              className="text-sm text-indigo-600 hover:underline"
            >
              {mostrarLogs ? 'Ocultar' : 'Mostrar'}
            </button>
          </div>

          {mostrarLogs && (
            <>
              <ul className="text-sm divide-y divide-gray-200">
                {logs.map((l, i) => (
                  <li key={i} className="py-2">
                    <strong>{l.usuario_email}</strong> → {l.accion}: {l.detalle} ({new Date(l.timestamp).toLocaleString()})
                  </li>
                ))}
              </ul>
              <button
                onClick={exportarLogsCSV}
                className="mt-4 bg-indigo-600 text-white px-4 py-1 rounded hover:bg-indigo-700 transition"
              >
                Exportar logs a CSV
              </button>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
