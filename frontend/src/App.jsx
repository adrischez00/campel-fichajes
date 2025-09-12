// src/App.jsx
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./Login";
import AdminPanel from "./components/admin/AdminPanel";
import EmpleadoPanel from "./components/empleado/EmpleadoPanel";
import EmpleadoAusencias from "./pages/EmpleadoAusencias";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { ToastProvider } from "./components/ui/ToastContext";

// Helpers del wrapper
import { getAccessToken, doLogout } from "./services/api";

// --- helpers de persistencia para role/user ---
const ROLE_KEY = "role";
const USER_KEY = "user";

function getSaved(key) {
  try {
    return (
      (typeof localStorage !== "undefined" && localStorage.getItem(key)) ??
      (typeof sessionStorage !== "undefined" && sessionStorage.getItem(key)) ??
      null
    );
  } catch {
    return null;
  }
}
function setSaved(key, value) {
  try {
    // Si el access está en localStorage (recordarme), guarda ahí; si no, en sessionStorage
    const useLocal =
      typeof localStorage !== "undefined" &&
      localStorage.getItem("access") != null;
    if (useLocal && typeof localStorage !== "undefined") {
      localStorage.setItem(key, value);
    } else if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(key, value);
    }
  } catch {}
}
function clearSaved(keys) {
  try {
    for (const k of keys) {
      if (typeof localStorage !== "undefined") localStorage.removeItem(k);
      if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(k);
    }
  } catch {}
}

export default function App() {
  const [session, setSession] = useState(null);

  // Rehidratación en arranque
  useEffect(() => {
    const token =
      getAccessToken() ||
      (typeof sessionStorage !== "undefined" &&
        sessionStorage.getItem("token")); // compat antigua

    if (!token) return;

    // 1) Intentar role/user persistidos por Login.jsx
    const roleSaved = (getSaved(ROLE_KEY) || "").toLowerCase();
    const userSaved = getSaved(USER_KEY);

    if (roleSaved) {
      setSession({ token, role: roleSaved, user: userSaved });
      return;
    }

    // 2) Fallback: decodificar JWT (por si en el futuro incluyes role en el token)
    try {
      const payload = JSON.parse(atob(token.split(".")[1] || ""));
      const role = (payload.role || "employee").toLowerCase();
      const user = payload.sub || null;
      setSession({ token, role, user });
    } catch {
      // token inválido -> limpiar compat antigua
      try {
        if (typeof sessionStorage !== "undefined")
          sessionStorage.removeItem("token");
      } catch {}
    }
  }, []);

  // Llamado desde <Login onLogin={...}/>
  const handleLogin = (s) => {
    // s viene de Login.jsx: { token, role, user }
    const token = getAccessToken();
    if (!token) {
      setSession(null);
      return;
    }
    const role = (s?.role || "employee").toLowerCase();
    const user = s?.user || null;

    // Guardar role/user para rehidratado correcto
    setSaved(ROLE_KEY, role);
    if (user) setSaved(USER_KEY, user);

    setSession({ token, role, user });
  };

  const handleLogout = async () => {
    await doLogout(); // limpia access y hace redirect a /login
    clearSaved([ROLE_KEY, USER_KEY]);
    setSession(null);
  };

  return (
    <ToastProvider>
      <BrowserRouter>
        <div
          className="min-h-screen"
          style={{
            backgroundImage: "url('/fondo.png')",
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat",
            backgroundAttachment: "fixed",
          }}
        >
          {!session ? (
            <Login onLogin={handleLogin} />
          ) : (
            <Routes>
              {session.role === "admin" ? (
                <Route
                  path="*"
                  element={<AdminPanel session={session} onLogout={handleLogout} />}
                />
              ) : (
                <>
                  <Route
                    path="/"
                    element={<EmpleadoPanel session={session} onLogout={handleLogout} />}
                  />
                  <Route
                    path="/ausencias"
                    element={<EmpleadoAusencias session={session} />}
                  />
                  <Route path="*" element={<Navigate to="/" />} />
                </>
              )}
            </Routes>
          )}
        </div>

        <ToastContainer position="top-right" autoClose={3000} />
      </BrowserRouter>
    </ToastProvider>
  );
}
