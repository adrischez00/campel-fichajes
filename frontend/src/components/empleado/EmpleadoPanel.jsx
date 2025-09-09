// src/components/empleado/EmpleadoPanel.jsx
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api.js'; // base URL + auto-refresh centralizados
import Header from '../shared/Header';
import { toast } from 'react-toastify';
import FichajeBloque from './FichajeBloque';
import SolicitudManualForm from './SolicitudManualForm.jsx';
import Paginacion from '../shared/Paginacion';
import SaldoVacacionesWidget from './SaldoVacacionesWidget.jsx';

// Helpers (Madrid + ISO sin zona => UTC)
import { parseISO, yyyymmddTZ, fmtHoraISO, fmtFechaISO } from '../../utils/fecha';

// Helper aviso “desde…”
const formateaAviso = (iso) => {
  if (!iso) return '';
  const ts = parseISO(iso);
  if (!ts || isNaN(ts)) return '';

  const hoyISO = yyyymmddTZ(new Date());
  const diaISO = yyyymmddTZ(ts);

  const diffDias = Math.floor(
    (new Date(hoyISO + 'T00:00:00Z') - new Date(diaISO + 'T00:00:00Z')) / 86400000
  );

  const hora = fmtHoraISO(ts.toISOString());

  if (diffDias === 0) return `desde las ${hora}`;
  if (diffDias === 1) return `desde Ayer a las ${hora}`;
  return `desde el ${fmtFechaISO(ts.toISOString())} a las ${hora} (hace ${diffDias} días)`;
};

export default function EmpleadoPanel({ session, onLogout }) {
  const navigate = useNavigate();

  const [resumenFichajes, setResumenFichajes] = useState({});
  const [meta, setMeta] = useState({});
  const [tiempoHoy, setTiempoHoy] = useState(0);
  const [mostrarResumen, setMostrarResumen] = useState(false);
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [estadoActual, setEstadoActual] = useState(null);
  const [loadingFichar, setLoadingFichar] = useState(false);
  const [cargandoResumen, setCargandoResumen] = useState(false);
  const [pagina, setPagina] = useState(1);
  const porPagina = 3;

  // refresco del widget de saldos cuando el usuario ficha
  const [saldoRefreshKey, setSaldoRefreshKey] = useState(0);
  const bumpSaldo = () => setSaldoRefreshKey((k) => k + 1);

  const { token, user } = session;
  const usuarioEmail = user?.email || user;

  // “Hoy” en Europe/Madrid
  const hoyISO = yyyymmddTZ(new Date());

  // Cargar resumen + meta (usa cliente api -> evita /api/api y mixed content)
  const cargarResumenFichajes = useCallback(async () => {
    setCargandoResumen(true);
    try {
      const data = await api.get('/resumen-fichajes', token);
      const resumen = data?.resumen || data || {};
      const metaRx = data?._meta || {};
      setResumenFichajes(resumen);
      setMeta(metaRx);

      if (metaRx?.turno_abierto?.desde) {
        toast.warning(`Tienes un turno abierto ${formateaAviso(metaRx.turno_abierto.desde)}.`, { autoClose: 7000 });
      }
      if (Array.isArray(metaRx?.fichajes_futuros) && metaRx.fichajes_futuros.length > 0) {
        toast.error('⚠️ Se han detectado fichajes con fecha FUTURA. Corrige antes de continuar.', { autoClose: 10000 });
      }
    } catch (e) {
      toast.error(`❌ Error al cargar el resumen de fichajes${e?.message ? `: ${e.message}` : ''}`);
      setResumenFichajes({});
      setMeta({});
    } finally {
      setCargandoResumen(false);
    }
  }, [token]);

  const tieneFuturos = Array.isArray(meta?.fichajes_futuros) && meta.fichajes_futuros.length > 0;

  // Fichar (FormData + auto-refresh con api.postForm)
  const fichar = async (tipo) => {
    if (tieneFuturos) {
      toast.error('⛔ Fichaje bloqueado por fichajes futuros. Corrige primero.');
      return;
    }
    setLoadingFichar(true);
    try {
      const form = new FormData();
      form.append('tipo', tipo);

      await api.postForm('/fichar', form, token);

      toast.success(tipo === 'entrada' ? '✅ Entrada registrada' : '✅ Salida registrada');
      await cargarResumenFichajes();
      bumpSaldo(); // refresca widget de saldo
    } catch (e) {
      toast.error(`❌ ${e?.message || 'Error al fichar'}`);
    } finally {
      setLoadingFichar(false);
    }
  };

  useEffect(() => { cargarResumenFichajes(); }, [cargarResumenFichajes]);

  // ⏱️ Ticker “tiempo trabajado hoy” (todo en Madrid)
  useEffect(() => {
    const interval = setInterval(() => {
      const totalHoyBase = (resumenFichajes[hoyISO]?.total) || 0;
      const abiertoIso = meta?.turno_abierto?.desde || null;

      if (abiertoIso) {
        const inicio = parseISO(abiertoIso);
        const abiertoDiaISO = yyyymmddTZ(inicio);
        const esDeHoy = (abiertoDiaISO === hoyISO);

        const extra = esDeHoy ? Math.max(0, Math.floor((Date.now() - inicio.getTime()) / 1000)) : 0;
        setTiempoHoy(totalHoyBase + extra);
        setEstadoActual('fichado');
      } else {
        setTiempoHoy(totalHoyBase);
        setEstadoActual('descanso');
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [resumenFichajes, meta, hoyISO]);

  const bloquesHoy = resumenFichajes[hoyISO]?.bloques || [];

  const formatSegundos = (s = 0) => {
    const safe = Number.isFinite(s) ? s : 0;
    const h = Math.floor(safe / 3600);
    const m = Math.floor((safe % 3600) / 60);
    const sec = Math.floor(safe % 60);
    return `${h}h ${m}min ${sec}s`;
  };

  const hayAbierto = !!meta?.turno_abierto?.desde;

  // === util: quedarnos solo con fichajes reales (no bloques de “ausencia”) ===
  const soloBloquesTrabajo = (bloques = []) =>
    bloques.filter(
      (b) => !b?.ausencia && (b?.entrada || b?.salida || (typeof b?.duracion === 'number' && b.duracion > 0))
    );

  return (
    <div
      className="min-h-screen relative overflow-y-auto"
      style={{
        backgroundImage: "url('/fondo.png')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed'
      }}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/10 to-transparent" />

      <Header usuario={usuarioEmail} onLogout={onLogout}/>
      <main className="max-w-3xl mx-auto p-6 md:p-8 space-y-8">
        <div className="rounded-3xl bg-white/60 backdrop-blur-md border border-white/40 shadow-xl p-6 sm:p-8 space-y-8">
          {/* === Sección fichar === */}
          <section className="rounded-2xl bg-white/60 backdrop-blur-md border border-white/40 shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-[#004B87]">Fichar ahora</h2>
              <button
                onClick={cargarResumenFichajes}
                className="text-sm px-3 py-1 rounded-lg border hover:bg-slate-50"
                disabled={cargandoResumen}
                title="Recargar resumen"
              >
                {cargandoResumen ? 'Actualizando…' : 'Refrescar'}
              </button>
            </div>

            {hayAbierto && (
              <div className="mb-4 rounded-xl border border-amber-300/60 bg-amber-50/80 p-4 text-amber-900">
                <div className="font-semibold mb-2">
                  🕒 Tienes un turno abierto {formateaAviso(meta.turno_abierto.desde)}
                </div>
                <div className="text-sm text-gray-700">
                  Puedes fichar <b>salida ahora</b> o enviar una <b>solicitud manual</b> con la hora real.
                </div>
              </div>
            )}

            <div className="flex gap-4 flex-wrap">
              <button
                disabled={loadingFichar || hayAbierto || tieneFuturos}
                onClick={() => fichar('entrada')}
                className={`flex items-center gap-2 px-6 py-3 rounded-2xl text-base font-semibold text-white shadow-md transition-all duration-200 ${
                  (hayAbierto || tieneFuturos)
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-green-500 to-green-600 hover:scale-[1.03]'
                }`}
                title={tieneFuturos ? 'Bloqueado por fichaje futuro' : (hayAbierto ? 'Ya tienes un turno abierto' : 'Fichar entrada')}
              >
                🟢 Fichar entrada
              </button>

              <button
                disabled={loadingFichar || !hayAbierto || tieneFuturos}
                onClick={() => fichar('salida')}
                className={`flex items-center gap-2 px-6 py-3 rounded-2xl text-base font-semibold text-white shadow-md transition-all duration-200 ${
                  (!hayAbierto || tieneFuturos)
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-blue-500 to-blue-600 hover:scale-[1.03]'
                }`}
                title={tieneFuturos ? 'Bloqueado por fichaje futuro' : (!hayAbierto ? 'No hay turno abierto' : 'Fichar salida')}
              >
                🔵 Fichar salida
              </button>
            </div>

            {tieneFuturos && (
              <p className="mt-3 text-sm text-red-700">
                ⛔ Fichaje bloqueado por fichajes con fecha FUTURA. Corrige esos registros o solicita al admin que los ajuste.
              </p>
            )}

            {estadoActual && (
              <div className="mt-2 text-sm flex items-center gap-2">
                {estadoActual === 'fichado'
                  ? <span className="text-green-700">🟢 Fichado (trabajando)</span>
                  : <span className="text-red-600">🔴 En descanso</span>}
              </div>
            )}

            <div className="mt-4 text-sm text-gray-800 space-y-2">
              <p>⏰ <strong>Tiempo trabajado hoy:</strong> {formatSegundos(tiempoHoy)}</p>
              {soloBloquesTrabajo(bloquesHoy).map((b, i) => (
                <FichajeBloque key={i} entrada={b.entrada} salida={b.salida} duracion={b.duracion} anomalia={b.anomalia}/>
              ))}
            </div>
          </section>

          {/* === Atajos Ausencias & Vacaciones + Saldo === */}
          <section className="rounded-2xl bg-white/60 backdrop-blur-md border border-white/40 shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-[#004B87]">Ausencias y Vacaciones</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate("/ausencias?tab=solicitar")}
                  className="px-3 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
                >
                  ➕ Solicitar
                </button>
                <button
                  onClick={() => navigate("/ausencias?tab=mis")}
                  className="px-3 py-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800"
                >
                  📄 Mis solicitudes
                </button>
              </div>
            </div>
            {/* Widget de saldo; se refresca tras fichar via key */}
            <SaldoVacacionesWidget key={saldoRefreshKey} />
          </section>

          {/* === Solicitud de fichaje manual === */}
          <section className="rounded-2xl bg-white/60 backdrop-blur-md border border-white/40 shadow p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-[#004B87]">Solicitar fichaje manual</h3>
              <button onClick={() => setMostrarFormulario(!mostrarFormulario)} className="text-sm text-indigo-600 hover:underline">
                {mostrarFormulario ? 'Ocultar' : 'Mostrar más'}
              </button>
            </div>
            {mostrarFormulario && (
              <SolicitudManualForm usuarioEmail={usuarioEmail} token={token}/>
            )}
          </section>

          {/* === Resumen de fichajes por día === */}
          <section className="rounded-2xl bg-white/60 backdrop-blur-md border border-white/40 shadow p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-[#004B87]">Tus fichajes</h3>
              <button onClick={() => setMostrarResumen(!mostrarResumen)} className="text-sm text-indigo-600 hover:underline">
                {mostrarResumen ? 'Ocultar' : 'Ver resumen'} por día
              </button>
            </div>

            {mostrarResumen && (() => {
              // Filtrar días: solo aquellos con fichajes reales (ignorar días de solo ausencias)
              const diasConBloques = Object.entries(resumenFichajes || {})
                .filter(([k, d]) =>
                  k !== '_meta' &&
                  Array.isArray(d?.bloques) &&
                  soloBloquesTrabajo(d.bloques).length > 0
                )
                .sort(([a], [b]) => new Date(b) - new Date(a));

              const totalPaginas = Math.max(1, Math.ceil(diasConBloques.length / porPagina));
              const inicio = (pagina - 1) * porPagina;
              const paginados = diasConBloques.slice(inicio, inicio + porPagina);

              const formatTotal = (s=0) => {
                const safe = Number.isFinite(s) ? s : 0;
                const h = Math.floor(safe / 3600);
                const m = Math.floor((safe % 3600) / 60);
                return `${h}h ${m}min`;
              };

              return (
                <>
                  {paginados.map(([fecha, { total = 0, bloques = [] }]) => (
                    <div key={fecha} className="bg-white/60 backdrop-blur border border-white/40 rounded-2xl shadow-sm p-5 mb-6">
                      <h4 className="font-semibold text-blue-800 text-lg mb-3">
                        📅 {fmtFechaISO(`${fecha}T00:00:00Z`)}
                      </h4>
                      <div className="space-y-4">
                        {soloBloquesTrabajo(bloques).map((b, i) => (
                          <FichajeBloque key={i} entrada={b.entrada} salida={b.salida} duracion={b.duracion} anomalia={b.anomalia}/>
                        ))}
                      </div>
                      <p className="text-sm text-gray-600 italic mt-3">
                        ⏱️ <span className="font-medium">Total:</span> {formatTotal(total)}
                      </p>
                    </div>
                  ))}
                  <Paginacion
                    pagina={pagina}
                    totalPaginas={totalPaginas}
                    onAnterior={() => setPagina((p) => Math.max(p - 1, 1))}
                    onSiguiente={() => setPagina((p) => Math.min(p + 1, totalPaginas))}
                  />
                </>
              );
            })()}
          </section>
        </div>
      </main>
    </div>
  );
}
