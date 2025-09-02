// src/components/shared/ConfirmModal.jsx
import React from 'react';

export default function ConfirmModal({ visible, onClose, onConfirm, mensaje }) {
  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-sm space-y-4 animate-fadeIn">
        <h2 className="text-lg font-bold text-gray-800 text-center">¿Confirmar acción?</h2>
        <p className="text-sm text-gray-600 text-center">{mensaje}</p>
        <div className="flex flex-col sm:flex-row justify-center sm:justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-all"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white bg-red-600 hover:bg-red-700 transition-all"
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}

