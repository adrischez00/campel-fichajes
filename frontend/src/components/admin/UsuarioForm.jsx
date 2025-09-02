// src/components/admin/UsuarioForm.jsx
import React, { useState } from 'react';

export default function UsuarioForm({ onCrearUsuario, msg }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [rol, setRol] = useState('employee');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  const validar = () => {
    if (!email.includes('@')) return 'Correo inválido';
    if (password.length < 8 || !/\d/.test(password)) return 'Contraseña insegura';
    if (password !== confirmar) return 'Las contraseñas no coinciden';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validar();
    if (err) return setError(err);
    setError('');
    setEnviando(true);
    await onCrearUsuario({ email, password, role: rol });
    setEnviando(false);
    setEmail('');
    setPassword('');
    setConfirmar('');
    setRol('employee');
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 space-y-5">
      <h3 className="text-xl font-bold text-blue-900">➕ Registrar nuevo usuario</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <input
          type="email"
          placeholder="Correo electrónico"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="border border-gray-300 rounded-xl px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
        />

        <select
          value={rol}
          onChange={(e) => setRol(e.target.value)}
          className="border border-gray-300 rounded-xl px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
        >
          <option value="employee">Empleado</option>
          <option value="admin">Administrador</option>
        </select>

        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="border border-gray-300 rounded-xl px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
        />

        <input
          type="password"
          placeholder="Confirmar contraseña"
          value={confirmar}
          onChange={(e) => setConfirmar(e.target.value)}
          required
          className="border border-gray-300 rounded-xl px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
        />
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}

      <button
        type="submit"
        disabled={enviando}
        className="bg-blue-700 hover:bg-blue-800 transition-all duration-200 text-white px-6 py-2 rounded-xl font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
      >
        {enviando ? (
          <>
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 01-8-8z"></path>
            </svg>
            Creando...
          </>
        ) : (
          'Crear usuario'
        )}
      </button>

      {msg && <p className="text-sm text-gray-700">{msg}</p>}
    </form>
  );
}
