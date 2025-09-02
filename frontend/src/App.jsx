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

// 👇 helpers del wrapper pro (Opción B)
import { getAccessToken, doLogout } from "./services/api";

export default function App() {
  const [session, setSession] = useState(null);

  // Rehidratación en arranque: lee el access desde storage (session/local)
  useEffect(() => {
    const token =
      getAccessToken() ||
      (typeof sessionStorage !== "undefined" && sessionStorage.getItem("token")); // compat antigua

    if (!token) return;
    try {
      const payload = JSON.parse(atob(token.split(".")[1] || ""));
      // payload.sub = email; payload.role si lo incluyes
      const role = payload.role || "employee";
      const user = payload.sub || null;
      setSession({ token, role, user });
    } catch {
      // si el token viejo no es decodificable, lo limpiamos
      try {
        sessionStorage.removeItem("token");
      } catch {}
    }
  }, []);

  // Cuando Login te devuelva (según tu Login.jsx):
  // - Si ya usas doLogin() dentro de Login.jsx, aquí basta con decodificar el nuevo token.
  const handleLogin = (s) => {
    // s puede ser { access_token, user... } o un objeto de tu Login.jsx.
    // Releer del storage para no depender del shape de s:
    const token = getAccessToken();
    if (!token) {
      setSession(null);
      return;
    }
    try {
      const payload = JSON.parse(atob(token.split(".")[1] || ""));
      const role = payload.role || "employee";
      const user = payload.sub || null;
      setSession({ token, role, user });
    } catch {
      setSession(null);
    }
  };

  const handleLogout = async () => {
    await doLogout(); // borra cookie httpOnly (refresh) y limpia storage
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
