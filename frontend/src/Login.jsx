// src/Login.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "./components/shared/Header";
import { doLogin, getAccessToken } from "./services/api";

// Decodificador local de JWT (sin depender de api.js)
function decodeJwt(token) {
  try {
    const b64 = token.split(".")[1] || "";
    const padded = b64
      .replace(/-/g, "+")
      .replace(/_/g, "/")
      .padEnd(Math.ceil(b64.length / 4) * 4, "=");
    return JSON.parse(atob(padded));
  } catch {
    return {};
  }
}

export default function Login({ onLogin }) {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [remember, setRemember] = useState(false);

  useEffect(() => {
    setEmail("");
    setPassword("");
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMsg("");
    setLoading(true);
    try {
      // Llama a /auth/login-json y guarda el access en storage (y refresh en cookie httpOnly)
      const data = await doLogin(email, password, remember);

      // Lee el token guardado por el wrapper
      const token = getAccessToken();
      if (!token) throw new Error("Token no recibido");

      // Saca role y usuario: el JWT actual no lleva role, así que priorizamos el body
      const payload = decodeJwt(token);
      const userFromResp = data?.user || data?.usuario || null;
      const role =
        (userFromResp?.role ||
          userFromResp?.rol ||
          payload.role ||
          "employee").toLowerCase();
      const user = payload.sub || payload.email || userFromResp?.email || email;

      // Propaga al estado global si tu App lo usa
      if (typeof onLogin === "function") {
        onLogin({ token, role, user });
      }

      // Redirige según rol
      const target = role === "admin" ? "/admin" : "/";
      navigate(target, { replace: true });
    } catch (err) {
      console.error("[LOGIN] error:", err);
      setMsg("Correo o contraseña incorrectos.");
    } finally {
      setLoading(false);
    }
  };

  const backgroundURL = `/fondo.png`;

  return (
    <div
      className="relative min-h-screen bg-cover bg-center bg-no-repeat flex flex-col"
      style={{ backgroundImage: `url('${backgroundURL}')` }}
    >
      <Header />

      <main className="flex flex-col items-center justify-center flex-1 px-4 py-8">
        <div className="w-full max-w-md bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl p-8 animate-fade-in">
          <h2 className="text-2xl font-semibold text-gray-800 mb-6 text-center">
            Accede a tu cuenta
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="on">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Correo electrónico
              </label>
              <input
                type="email"
                id="email"
                name="username"
                autoComplete="email"
                placeholder="usuario@campel.com"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Contraseña
              </label>
              <input
                type="password"
                id="password"
                name="password"
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              Recordarme en este dispositivo
            </label>

            {msg && <p className="text-red-600 text-sm text-center">{msg}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 transition-colors text-white font-semibold rounded-lg shadow-md focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-50"
            >
              {loading ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
