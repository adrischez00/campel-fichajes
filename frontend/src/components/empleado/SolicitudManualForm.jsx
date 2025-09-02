import { useState } from "react";
import { toast } from "react-toastify";
import { API_URL } from "../../config";

export default function SolicitudManualForm({ usuarioEmail, token }) {
  const [fecha, setFecha] = useState("");
  const [hora, setHora] = useState("");
  const [tipo, setTipo] = useState("entrada");
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setEnviando(true);
    const data = { fecha, hora, tipo, motivo };

    try {
      const res = await fetch(`${API_URL}/solicitar-fichaje-manual`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          usuario: usuarioEmail,
        },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Error desconocido");
      }

      toast.success("✅ Solicitud enviada correctamente");
      setFecha("");
      setHora("");
      setTipo("entrada");
      setMotivo("");
    } catch (err) {
      toast.error(`❌ Error: ${err.message}`);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex flex-col md:flex-row gap-4">
        <input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          className="w-full md:max-w-[14rem] rounded-xl border border-gray-300 bg-white p-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <input
          type="time"
          value={hora}
          onChange={(e) => setHora(e.target.value)}
          className="w-full md:max-w-[10rem] rounded-xl border border-gray-300 bg-white p-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="w-full md:max-w-[12rem] rounded-xl border border-gray-300 bg-white p-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="entrada">Entrada</option>
          <option value="salida">Salida</option>
        </select>
      </div>

      <textarea
        value={motivo}
        onChange={(e) => setMotivo(e.target.value)}
        placeholder="Motivo de la solicitud"
        className="w-full rounded-xl border border-gray-300 bg-white p-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        rows={3}
      />

      <button
        type="submit"
        disabled={enviando}
        className={`w-full md:w-auto px-6 py-2 rounded-2xl text-white font-semibold shadow-md transition-all duration-200 ${
          enviando
            ? "bg-gray-400 cursor-not-allowed"
            : "bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 hover:scale-[1.03]"
        }`}
      >
        {enviando ? "✉️ Enviando..." : "✍️ Enviar solicitud"}
      </button>
    </form>
  );
}
