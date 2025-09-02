// src/components/admin/SolicitudCard.jsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatDateTime } from '../../utils/formatDate';
import { useToast } from '../ui/ToastContext';

const estadoStyles = {
  pendiente: { pill: 'bg-yellow-100 text-yellow-800', border: 'border-l-4 border-yellow-300' },
  aprobada:  { pill: 'bg-emerald-100 text-emerald-800', border: 'border-l-4 border-emerald-300' },
  rechazada: { pill: 'bg-red-100 text-red-800',       border: 'border-l-4 border-red-300' }
};
const tipoStyles = {
  entrada: 'bg-emerald-100 text-emerald-800',
  salida:  'bg-indigo-100 text-indigo-800'
};

/* Texto utils para resaltado (tolerante a acentos) */
const strip = (s) =>
  (s || '')
    .toString()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');

function diacriticClassFor(ch) {
  switch (ch) {
    case 'a': return '[aàáâãäå]';
    case 'e': return '[eèéêë]';
    case 'i': return '[iìíîï]';
    case 'o': return '[oòóôõö]';
    case 'u': return '[uùúûü]';
    case 'n': return '[nñ]';
    case 'c': return '[cç]';
    default:  return ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
}
function termToRegex(term) {
  return Array.from(term).map(diacriticClassFor).join('');
}
const Highlighted = ({ text, tokens }) => {
  if (!text || !tokens?.length) return <>{text}</>;
  const cleanTokens = Array.from(new Set(tokens.map(strip).filter((t) => t && t.length >= 2)));
  if (!cleanTokens.length) return <>{text}</>;
  const pattern = cleanTokens.sort((a, b) => b.length - a.length).map(termToRegex).join('|');
  try {
    const re = new RegExp(`(${pattern})`, 'ig');
    const parts = String(text).split(re);
    return parts.map((p, i) =>
      i % 2 ? <mark key={i} className="rounded bg-yellow-100 px-0.5">{p}</mark> : <React.Fragment key={i}>{p}</React.Fragment>
    );
  } catch {
    return <>{text}</>;
  }
};

function SolicitudCardInner({ solicitud, onResolver, highlight }) {
  const { show } = useToast();
  const { usuario_email, tipo, fecha, hora, motivo, estado, id } = solicitud;
  const [accion, setAccion] = useState(null); // 'aprobar' | 'rechazar' | null
  const [expandido, setExpandido] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const cardRef = useRef(null);

  const est = estadoStyles[estado] ?? { pill: 'bg-gray-100 text-gray-800', border: 'border-l-4 border-gray-300' };
  const textoMotivo = (motivo || '').trim();
  const esLargo = textoMotivo.length > 140;

  const tokens = useMemo(
    () => (Array.isArray(highlight) ? highlight : strip(highlight).split(/\s+/).filter(Boolean)),
    [highlight]
  );

  const onAprobar = useCallback(async () => {
    try {
      setAccion('aprobar');
      await onResolver?.(id, true);
      show('Solicitud aprobada');
    } catch {
      show('Error al aprobar');
    } finally {
      setAccion(null);
    }
  }, [onResolver, id, show]);

  const onRechazar = useCallback(async () => {
    try {
      setAccion('rechazar');
      await onResolver?.(id, false);
      show('Solicitud rechazada');
    } catch {
      show('Error al rechazar');
    } finally {
      setAccion(null);
    }
  }, [onResolver, id, show]);

  const copiarMotivo = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(textoMotivo);
      setCopiado(true);
      show('Motivo copiado');
      setTimeout(() => setCopiado(false), 1000);
    } catch { /* no-op */ }
  }, [textoMotivo, show]);

  // Atajos A/R cuando la card tiene foco
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const onKey = (e) => {
      if (estado !== 'pendiente') return;
      if (e.key === 'a' && !e.metaKey && !e.ctrlKey) { e.preventDefault(); onAprobar(); }
      if (e.key === 'r' && !e.metaKey && !e.ctrlKey) { e.preventDefault(); onRechazar(); }
    };
    el.addEventListener('keydown', onKey);
    return () => el.removeEventListener('keydown', onKey);
  }, [estado, onAprobar, onRechazar]);

  return (
    <div
      ref={cardRef}
      className={`
        ${est.border}
        rounded-2xl border border-white/40 bg-white/60 backdrop-blur-md
        shadow-sm hover:shadow-md transition focus:outline-none focus:ring-2 focus:ring-blue-400/60
      `}
      role="listitem"
      tabIndex={0}
      aria-label={`Solicitud de ${usuario_email}, tipo ${tipo}, estado ${estado}`}
    >
      <div className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1 space-y-2">
            {/* Cabecera */}
            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-800">
              <span className="font-semibold"><Highlighted text={usuario_email} tokens={tokens} /></span>
              <span className="opacity-80">solicita</span>
              <span
                className={`inline-block rounded-full px-2 py-1 text-xs font-semibold uppercase tracking-wide ${tipoStyles[tipo] || 'bg-blue-100 text-blue-700'}`}
                title={`Tipo: ${tipo}`}
              >
                <Highlighted text={tipo} tokens={tokens} />
              </span>
              <span className={`ml-1 inline-block rounded-full px-2 py-1 text-xs font-semibold ${est.pill}`} title={`Estado: ${estado}`}>
                {estado}
              </span>
            </div>

            {/* Fecha/Hora */}
            <p className="text-xs text-gray-600/90">{formatDateTime(fecha, hora)}</p>

            {/* Motivo (glass + plegado y copiar) */}
            {textoMotivo && (
              <div className="rounded-xl bg-white/50 backdrop-blur border border-white/40 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <span aria-hidden>📝</span>
                    <span className="font-semibold">Motivo</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={copiarMotivo}
                      className="text-xs rounded-md border border-gray-300/60 bg-white/70 px-2 py-1 hover:bg-white"
                      title="Copiar motivo"
                    >
                      {copiado ? 'Copiado' : 'Copiar'}
                    </button>
                    {esLargo && (
                      <button
                        onClick={() => setExpandido((x) => !x)}
                        className="text-xs rounded-md border border-gray-300/60 bg-white/70 px-2 py-1 hover:bg-white"
                        aria-expanded={expandido}
                        aria-controls={`motivo-${id}`}
                      >
                        {expandido ? 'Ocultar' : 'Ver más'}
                      </button>
                    )}
                  </div>
                </div>

                <div
                  id={`motivo-${id}`}
                  className={`text-sm text-gray-900 whitespace-pre-wrap transition-[max-height] duration-200 ease-in-out ${expandido ? 'max-h-[9999px]' : 'max-h-16 overflow-hidden'}`}
                >
                  <Highlighted text={textoMotivo} tokens={tokens} />
                </div>

                {!expandido && esLargo && (
                  <div className="pointer-events-none -mt-6 h-6 w-full bg-gradient-to-t from-white/60 to-transparent" />
                )}
              </div>
            )}
          </div>

          {/* Acciones */}
          {estado === 'pendiente' && (
            <div className="flex gap-2 self-end sm:self-auto">
              <button
                onClick={onAprobar}
                disabled={accion !== null}
                className={`rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-md ${
                  accion === 'aprobar' ? 'bg-emerald-400 cursor-wait' : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
                aria-busy={accion === 'aprobar'}
              >
                {accion === 'aprobar' ? 'Aprobando…' : '✅ Aprobar'}
              </button>
              <button
                onClick={onRechazar}
                disabled={accion !== null}
                className={`rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-md ${
                  accion === 'rechazar' ? 'bg-red-400 cursor-wait' : 'bg-red-600 hover:bg-red-700'
                }`}
                aria-busy={accion === 'rechazar'}
              >
                {accion === 'rechazar' ? 'Rechazando…' : '❌ Rechazar'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ✅ Memo: re-render solo si cambia la solicitud o las claves de resaltado
export default React.memo(SolicitudCardInner, (prev, next) => {
  const prevKey = Array.isArray(prev.highlight) ? prev.highlight.join('|') : prev.highlight;
  const nextKey = Array.isArray(next.highlight) ? next.highlight.join('|') : next.highlight;
  return prev.solicitud === next.solicitud && prevKey === nextKey;
  });