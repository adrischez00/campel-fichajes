// src/components/admin/UsuarioTable.jsx
import React from 'react';
import { toast } from 'react-toastify';
import ConfirmModal from '../shared/ConfirmModal';

export default function UsuarioTable({ usuarios = [], onEliminar, onReestablecer, onEditar }) {
  const [editando, setEditando] = React.useState(null);
  const [nuevoValor, setNuevoValor] = React.useState({});
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [usuarioAEliminar, setUsuarioAEliminar] = React.useState(null);

  const iniciarEdicion = (u) => {
    setEditando(u.id);
    setNuevoValor({ email: u.email, role: u.role });
  };

  const guardar = async () => {
    try {
      await onEditar(editando, nuevoValor);
      toast.success('Usuario actualizado');
    } catch (err) {
      toast.error('Error al actualizar');
    }
    setEditando(null);
  };

  const cancelar = () => setEditando(null);

  const confirmarEliminar = (u) => {
    setUsuarioAEliminar(u);
    setConfirmOpen(true);
  };

  const eliminarConfirmado = async () => {
    try {
      await onEliminar(usuarioAEliminar.id);
      toast.success('Usuario eliminado');
    } catch (err) {
      toast.error('Error al eliminar');
    }
    setConfirmOpen(false);
  };

  const restablecer = async (u) => {
    try {
      await onReestablecer(u.id);
      toast.success('Contraseña restablecida');
    } catch (err) {
      toast.error('Error al restablecer contraseña');
    }
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200">
      <table className="min-w-full border border-gray-200 text-sm rounded-xl overflow-hidden">
        <thead>
          <tr className="bg-gray-100 text-gray-700 text-sm uppercase tracking-wider">
            <th className="px-4 py-3 text-left">Email</th>
            <th className="px-4 py-3 text-left">Rol</th>
            <th className="px-4 py-3 text-center">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.id} className="hover:bg-gray-50 transition">
              <td className="px-4 py-2 border-t">
                {editando === u.id ? (
                  <input
                    className="w-full rounded-lg border border-gray-300 px-3 py-1 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
                    value={nuevoValor.email}
                    onChange={e => setNuevoValor({ ...nuevoValor, email: e.target.value })}
                  />
                ) : (
                  u.email
                )}
              </td>
              <td className="px-4 py-2 border-t capitalize">
                {editando === u.id ? (
                  <select
                    className="w-full rounded-lg border border-gray-300 px-2 py-1 shadow-sm focus:ring-2 focus:ring-blue-500"
                    value={nuevoValor.role}
                    onChange={e => setNuevoValor({ ...nuevoValor, role: e.target.value })}
                  >
                    <option value="employee">Empleado</option>
                    <option value="admin">Administrador</option>
                  </select>
                ) : (
                  <span className={`font-semibold ${u.role === 'admin' ? 'text-blue-700' : 'text-green-700'}`}>
                    {u.role === 'admin' ? 'Admin' : 'Empleado'}
                  </span>
                )}
              </td>
              <td className="px-4 py-2 border-t text-center space-x-1">
                {editando === u.id ? (
                  <>
                    <button
                      onClick={guardar}
                      className="text-blue-600 hover:text-blue-800 transition text-lg"
                      title="Guardar"
                    >💾</button>
                    <button
                      onClick={cancelar}
                      className="text-gray-500 hover:text-gray-700 transition text-lg"
                      title="Cancelar"
                    >✖️</button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => iniciarEdicion(u)}
                      className="text-yellow-600 hover:text-yellow-800 transition text-lg"
                      title="Editar"
                    >✏️</button>
                    <button
                      onClick={() => confirmarEliminar(u)}
                      className="text-red-600 hover:text-red-800 transition text-lg"
                      title="Eliminar"
                    >🗑️</button>
                    <button
                      onClick={() => restablecer(u)}
                      className="text-indigo-600 hover:text-indigo-800 transition text-lg"
                      title="Restablecer contraseña"
                    >🔁</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ConfirmModal
        visible={confirmOpen}
        mensaje={`¿Eliminar usuario ${usuarioAEliminar?.email}?`}
        onClose={() => setConfirmOpen(false)}
        onConfirm={eliminarConfirmado}
      />
    </div>
  );
}
