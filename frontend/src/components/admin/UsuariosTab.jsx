import { useState, useMemo } from 'react';
import UsuarioForm from './UsuarioForm';
import UsuarioTable from './UsuarioTable';
import Paginacion from '../shared/Paginacion';

const USUARIOS_POR_PAGINA = 5;

export default function UsuariosTab({ usuarios = [], onCrearUsuario, msg, token, API_URL, onEliminar, onEditar, onReestablecer }) {
  const [filtro, setFiltro] = useState('');
  const [rolFiltro, setRolFiltro] = useState('todos');
  const [pagina, setPagina] = useState(1);

  if (!Array.isArray(usuarios)) usuarios = [];

  const filtrados = useMemo(() => {
    return usuarios.filter(u =>
      u.email.toLowerCase().includes(filtro.toLowerCase()) &&
      (rolFiltro === 'todos' || u.role === rolFiltro)
    );
  }, [usuarios, filtro, rolFiltro]);

  const totalPaginas = Math.ceil(filtrados.length / USUARIOS_POR_PAGINA);
  const visibles = filtrados.slice((pagina - 1) * USUARIOS_POR_PAGINA, pagina * USUARIOS_POR_PAGINA);

  return (
    <div className="space-y-8">
      <UsuarioForm onCrearUsuario={onCrearUsuario} msg={msg} />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-xl font-bold text-blue-900">👥 Listado de usuarios</h2>
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
          <input
            type="text"
            placeholder="🔍 Buscar por email..."
            value={filtro}
            onChange={(e) => {
              setFiltro(e.target.value);
              setPagina(1);
            }}
            className="px-4 py-2 rounded-xl border border-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition w-full sm:w-64"
          />
          <select
            value={rolFiltro}
            onChange={(e) => {
              setRolFiltro(e.target.value);
              setPagina(1);
            }}
            className="px-4 py-2 rounded-xl border border-gray-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition w-full sm:w-48"
          >
            <option value="todos">Todos</option>
            <option value="admin">Administrador</option>
            <option value="employee">Empleado</option>
          </select>
        </div>
      </div>

      {visibles.length > 0 ? (
        <>
          <UsuarioTable
            usuarios={visibles}
            token={token}
            API_URL={API_URL}
            onEliminar={onEliminar}
            onEditar={onEditar}
            onReestablecer={onReestablecer}
          />

          {totalPaginas > 1 && (
            <Paginacion
              pagina={pagina}
              totalPaginas={totalPaginas}
              onAnterior={() => setPagina(p => Math.max(1, p - 1))}
              onSiguiente={() => setPagina(p => Math.min(totalPaginas, p + 1))}
            />
          )}
        </>
      ) : (
        <p className="text-sm text-gray-500 italic text-center">
          No se encontraron usuarios con ese filtro.
        </p>
      )}
    </div>
  );
}
