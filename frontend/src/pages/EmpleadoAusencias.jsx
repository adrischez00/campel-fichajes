// src/pages/EmpleadoAusencias.jsx
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import SolicitarAusenciaForm from "../components/empleado/SolicitarAusenciaForm";
import MisAusencias from "../components/empleado/MisAusencias";
import AusenciasCalendario from "../components/empleado/AusenciasCalendario";

import { ausenciasService } from "../services/ausencias";
import { API_URL, doLogout } from "../services/api";

// Header global reutilizado (mismo que admin)
import Header from "../components/shared/Header";

export default function EmpleadoAusencias({ session }) {
  // ---- sesión ---------------------------------------------------------------
  const token = session?.token || session?.accessToken || null;
  const user = session?.user || {};
  const userId = user?.id ?? null;
  const emailUsuario = user?.email || user || "";

  // ---- router ---------------------------------------------------------------
  const navigate = useNavigate();
  const location = useLocation();
  const qs = new URLSearchParams(location.search);
  const initialTab = ["solicitar", "mis", "calendario"].includes(qs.get("tab"))
    ? qs.get("tab")
    : "solicitar";

  const [tab, setTab] = useState(initialTab);
  const [misAusencias, setMisAusencias] = useState([]);
  const [cargando, setCargando] = useState(false);

  // Raíz del backend SIN /api ni barra final (el componente añade /api/…)
  const apiRoot = useMemo(() => {
    return (API_URL || "")
      .replace(/\/+$/, "")     // sin barra final
      .replace(/\/api$/i, ""); // sin sufijo /api
  }, []);

  const goTab = (t) => {
    setTab(t);
    const p = new URLSearchParams(location.search);
    p.set("tab", t);
    navigate({ search: p.toString() }, { replace: true });
  };

  async function cargarMias() {
    setCargando(true);
    try {
      const datos = await ausenciasService.listarMiasPorEmail(
        token,
        emailUsuario
      );
      setMisAusencias(Array.isArray(datos) ? datos : []);
    } catch (err) {
      console.error("Error cargando ausencias:", err);
      setMisAusencias([]);
    } finally {
      setCargando(false);
    }
  }

  async function handleLogout() {
    try {
      await doLogout(); // limpia tokens + redirige a /login
    } catch {
      navigate("/login");
    }
  }

  useEffect(() => {
    if (tab === "mis" || tab === "calendario") {
      cargarMias();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  return (
    <div
      className="min-h-screen relative"
      style={{
        backgroundImage: "url('/fondo.png')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
        backgroundAttachment: "fixed",
      }}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-black/10 to-transparent" />

      <Header usuario={emailUsuario} onLogout={handleLogout} />

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Encabezado de sección */}
        <header className="flex items-center justify-between backdrop-blur-md bg-white/30 border border-white/40 rounded-2xl px-5 py-3 shadow-lg">
          <div>
            <h1 className="text-2xl font-bold text-[#004B87]">
              Ausencias y Vacaciones
            </h1>
            <p className="text-sm text-slate-700">{emailUsuario}</p>
          </div>
          <button
            onClick={() => navigate("/")}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm shadow-md transition"
          >
            ⬅ Volver al inicio
          </button>
        </header>

        {/* Tabs */}
        <div className="flex gap-2">
          {[
            { k: "solicitar", label: "Solicitar" },
            { k: "mis", label: "Mis solicitudes" },
            { k: "calendario", label: "Calendario" },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => goTab(t.k)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                tab === t.k
                  ? "bg-indigo-600 text-white shadow"
                  : "bg-white/60 hover:bg-white/80 border border-slate-300 text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Contenido */}
        <section className="backdrop-blur-lg bg-white/40 border border-white/50 rounded-2xl shadow-lg p-4">
          {tab === "solicitar" && (
            <div className="max-w-4xl mx-auto">
              <SolicitarAusenciaForm token={token} emailUsuario={emailUsuario} />
            </div>
          )}

          {tab === "mis" && (
            <div className="max-w-5xl mx-auto">
              <MisAusencias
                token={token}
                emailUsuario={emailUsuario}
                data={misAusencias}
                cargando={cargando}
                onRefrescar={cargarMias}
              />
            </div>
          )}

          {tab === "calendario" && (
            <div className="max-w-5xl mx-auto">
              <AusenciasCalendario
                data={misAusencias}
                cargando={cargando}
                onNeedData={cargarMias}
                userId={userId}
                apiRoot={apiRoot} /* raíz backend; el componente añade /api/... */
              />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

/*
Si quieres que al seleccionar fechas en el calendario se prefije
automáticamente el formulario y se salte a la pestaña "Solicitar",
usa esta prop en <AusenciasCalendario /> (quitar el comentario):

onPrefill={(start, end) => {
  sessionStorage.setItem(
    "ausencias_prefill",
    JSON.stringify({
      fecha_inicio: start.toISOString().slice(0, 10),
      fecha_fin: end.toISOString().slice(0, 10),
    })
  );
  goTab("solicitar");
}}

*/
