// src/components/admin/AdminPanel.jsx
import { useEffect, useState, useMemo } from 'react';
import Header from '../shared/Header';
import KPICard from './KPICard';
import TabGroup from './TabGroup';
import SolicitudesTab from './SolicitudesTab';
import GestionAusencias from './GestionAusencias';
import LogsTab from './LogsTab';
import UsuariosTab from './UsuariosTab';
import AdminSaldos from './AdminSaldos';            // 👈 NUEVO
import { api, API_URL } from '../../services/api.js';

export default function AdminPanel({ session, onLogout }) {
  const [solicitudes, setSolicitudes] = useState([]);
  const [ausencias, setAusencias]     = useState([]);
  const [logs, setLogs]               = useState([]);
  const [usuarios, setUsuarios]       = useState([]);
  const [msg, setMsg]                 = useState('');
  const [activeTab, setActiveTab]     = useState('Solicitudes');

  const [filtroInicialSolicitudes, setFiltroInicialSolicitudes] = useState(null);

  const token = session?.token;
  const user  = session?.user;

  if (!token || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-600 font-semibold">
        Error: Sesión inválida. Por favor inicia sesión nuevamente.
      </div>
    );
  }

  // --- helper de carga usando api (sin /api en las rutas)
  const fetchData = async (url, setter, extraHeaders = {}) => {
    try {
      const data = await api.get(url, token, extraHeaders);
      setter(Array.isArray(data) ? data : (data ?? []));
    } catch (err) {
      console.error(`❌ Error cargando ${url}:`, err);
    }
  };

  // Rutas reales del backend (sin prefijo)
  const cargarSolicitudes = () => fetchData('/solicitudes', setSolicitudes);
  const cargarAusencias   = () => fetchData('/ausencias', setAusencias);
  const cargarLogs        = () => fetchData('/logs', setLogs);
  const cargarUsuarios    = () => fetchData('/usuarios', setUsuarios);

  // --- resolver solicitud
  const resolver = async (id, aprobar) => {
    try {
      await api.post('/resolver-solicitud', { id, aprobar }, token);
      cargarSolicitudes();
    } catch (err) {
      console.error('❌ Error resolviendo solicitud:', err);
      alert(`❌ Error resolviendo solicitud: ${err.message}`);
    }
  };

  // --- admin: usuarios
  const crearUsuario = async ({ email, password, role }) => {
    try {
      await api.post('/registrar', { email, password, role }, token, { usuario: user.email });
      setMsg('✅ Usuario creado correctamente');
      cargarLogs();
      cargarUsuarios();
    } catch (err) {
      console.error('❌ Error creando usuario:', err);
      setMsg('❌ ' + (err.message || 'Error de conexión al crear usuario'));
    }
  };

  const eliminarUsuario = async (usuario) => {
    try {
      await api.delete(`/usuarios/${usuario.id}`, token, { usuario: user.email });
      cargarUsuarios();
    } catch (err) {
      console.error('❌ Error eliminando usuario:', err);
    }
  };

  const editarUsuario = async (id, cambios) => {
    try {
      await api.put(`/usuarios/${id}`, cambios, token, { usuario: user.email });
      cargarUsuarios();
    } catch (err) {
      console.error('❌ Error editando usuario:', err);
    }
  };

  const reestablecerPassword = async (usuario) => {
    try {
      await api.post(`/reestablecer-password/${usuario.id}`, null, token, { usuario: user.email });
      alert(`Nueva contraseña enviada a ${usuario.email}`);
    } catch (err) {
      console.error('❌ Error reestableciendo contraseña:', err);
    }
  };

  // --- deep-link inicial
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tab   = (params.get('tab')   || '').toLowerCase();
    const vista = (params.get('vista') || '').toLowerCase();

    if (tab === 'usuarios') setActiveTab('Usuarios');
    else if (tab === 'logs') setActiveTab('Logs');
    else if (tab === 'ausencias') setActiveTab('Ausencias');
    else if (tab === 'saldos') setActiveTab('Saldos');          // 👈 NUEVO
    else setActiveTab('Solicitudes');

    if (tab === 'solicitudes') {
      if (vista === 'aprobadas') {
        setFiltroInicialSolicitudes({ vista: 'aprobadas', estado: 'aprobada', solo_pendientes: false });
      } else if (vista === 'rechazadas') {
        setFiltroInicialSolicitudes({ vista: 'rechazadas', estado: 'rechazada', solo_pendientes: false });
      } else if (vista === 'historico' || vista === 'todas') {
        setFiltroInicialSolicitudes({ vista: 'historico', estado: 'all', solo_pendientes: false });
      } else {
        setFiltroInicialSolicitudes({ vista: 'pendientes', estado: 'pendiente', solo_pendientes: true });
      }
    }
  }, []);

  // --- reactiva desde el historial (back/forward)
  useEffect(() => {
    const onPop = () => {
      const params = new URLSearchParams(window.location.search);
      const tab   = (params.get('tab')   || '').toLowerCase();
      const vista = (params.get('vista') || '').toLowerCase();

      if (tab === 'usuarios') setActiveTab('Usuarios');
      else if (tab === 'logs') setActiveTab('Logs');
      else if (tab === 'ausencias') setActiveTab('Ausencias');
      else if (tab === 'saldos') setActiveTab('Saldos');        // 👈 NUEVO
      else setActiveTab('Solicitudes');

      if (tab === 'solicitudes') {
        if (vista === 'aprobadas') {
          setFiltroInicialSolicitudes({ vista: 'aprobadas', estado: 'aprobada', solo_pendientes: false });
        } else if (vista === 'rechazadas') {
          setFiltroInicialSolicitudes({ vista: 'rechazadas', estado: 'rechazada', solo_pendientes: false });
        } else if (vista === 'historico' || vista === 'todas') {
          setFiltroInicialSolicitudes({ vista: 'historico', estado: 'all', solo_pendientes: false });
        } else {
          setFiltroInicialSolicitudes({ vista: 'pendientes', estado: 'pendiente', solo_pendientes: true });
        }
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // --- carga inicial
  useEffect(() => {
    cargarSolicitudes();
    cargarAusencias();
    cargarLogs();
    cargarUsuarios();
  }, []);

  // KPIs
  const pendientes = useMemo(() => solicitudes.filter(s => s.estado === 'pendiente').length, [solicitudes]);
  const aprobadas  = useMemo(() => solicitudes.filter(s => s.estado === 'aprobada').length, [solicitudes]);
  const rechazadas = useMemo(() => solicitudes.filter(s => s.estado === 'rechazada').length, [solicitudes]);

  // KPI click -> abre pestaña + sincroniza query
  const abrirSolicitudes = (vista) => {
    setActiveTab('Solicitudes');
    if (vista === 'aprobadas') {
      setFiltroInicialSolicitudes({ vista: 'aprobadas', estado: 'aprobada', solo_pendientes: false });
    } else if (vista === 'rechazadas') {
      setFiltroInicialSolicitudes({ vista: 'rechazadas', estado: 'rechazada', solo_pendientes: false });
    } else if (vista === 'historico' || vista === 'todas') {
      setFiltroInicialSolicitudes({ vista: 'historico', estado: 'all', solo_pendientes: false });
    } else {
      setFiltroInicialSolicitudes({ vista: 'pendientes', estado: 'pendiente', solo_pendientes: true });
    }
    const url = `?tab=solicitudes&vista=${vista}`;
    window.history.pushState({}, '', url);
  };

  const vistaActiva = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    const v = (params.get('vista') || filtroInicialSolicitudes?.vista || 'pendientes').toLowerCase();
    if (v === 'historico') return 'todas';
    return v;
  }, [filtroInicialSolicitudes]);

  const tabs = [
    {
      name: 'Solicitudes',
      label: 'Solicitudes',
      icon: '📝',
      content: (
        <SolicitudesTab
          solicitudes={solicitudes}
          onResolver={resolver}
          filtroInicial={filtroInicialSolicitudes}
        />
      )
    },
    {
      name: 'Ausencias',
      label: 'Ausencias',
      icon: '📅',
      content: <GestionAusencias token={token} />
    },
    {
      name: 'Saldos',                         // 👈 NUEVO
      label: 'Saldos',
      icon: '💼',
      content: <AdminSaldos token={token} />
    },
    {
      name: 'Usuarios',
      label: 'Usuarios',
      icon: '👥',
      content: (
        <UsuariosTab
          usuarios={usuarios}
          onCrearUsuario={crearUsuario}
          msg={msg}
          token={token}
          API_URL={API_URL}
          onEliminar={eliminarUsuario}
          onEditar={editarUsuario}
          onReestablecer={reestablecerPassword}
        />
      )
    },
    {
      name: 'Logs',
      label: 'Logs',
      icon: '📁',
      content: <LogsTab logs={logs} />
    }
  ];

  const handleChangeTab = (tab) => {
    setActiveTab(tab.name);
    const params = new URLSearchParams(window.location.search);
    params.set('tab', tab.name.toLowerCase());
    if (tab.name !== 'Solicitudes') params.delete('vista');
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
  };

  const tabActual = tabs.find(t => t.name === activeTab)?.content;

  return (
    <div
      className="min-h-screen relative"
      style={{
        backgroundImage: "url('/fondo.png')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed'
      }}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/10 to-transparent" />
      <Header usuario={user} onLogout={onLogout} />
      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="rounded-3xl bg-white/55 backdrop-blur-xl border border-white/50 shadow-2xl shadow-black/5 p-6 sm:p-8 space-y-6">
          <h1 className="text-3xl font-extrabold text-blue-900 tracking-tight drop-shadow-sm">
            ⚙️ Panel de Administración
          </h1>

          <TabGroup
            tabs={tabs}
            activeTab={tabs.find(t => t.name === activeTab)}
            setActiveTab={handleChangeTab}
          />

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-2">
            <div role="button" tabIndex={0} onClick={() => abrirSolicitudes('pendientes')} className="outline-none focus:ring-2 focus:ring-blue-300 rounded-2xl transition">
              <KPICard title="Pendientes" value={pendientes} active={vistaActiva === 'pendientes'} />
            </div>
            <div role="button" tabIndex={0} onClick={() => abrirSolicitudes('aprobadas')} className="outline-none focus:ring-2 focus:ring-blue-300 rounded-2xl transition">
              <KPICard title="Aprobadas" value={aprobadas} active={vistaActiva === 'aprobadas'} />
            </div>
            <div role="button" tabIndex={0} onClick={() => abrirSolicitudes('rechazadas')} className="outline-none focus:ring-2 focus:ring-blue-300 rounded-2xl transition">
              <KPICard title="Rechazadas" value={rechazadas} active={vistaActiva === 'rechazadas'} />
            </div>
            <div role="button" tabIndex={0} onClick={() => abrirSolicitudes('todas')} className="outline-none focus:ring-2 focus:ring-blue-300 rounded-2xl transition">
              <KPICard title="Todas las solicitudes" value={solicitudes.length} active={vistaActiva === 'todas'} />
            </div>
          </div>

          <section className="mt-2">{tabActual}</section>
        </div>
      </main>
    </div>
  );
}
