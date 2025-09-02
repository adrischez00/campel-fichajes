// src/components/shared/Paginacion.jsx
import React, { useMemo } from "react";

export default function Paginacion({
  pagina,
  totalPaginas,
  onAnterior,
  onSiguiente,
  onGoToPage,             // opcional: (n) => void
  totalItems,             // opcional: muestra "X–Y de N"
  porPagina,              // opcional: junto a totalItems
  showSummary = true,     // muestra el resumen compacto
  showFirstLast = false,  // añade ⏮/⏭
  maxButtons = 5,         // nº de botones numéricos visibles (responsive)
}) {
  const canPrev = pagina > 1;
  const canNext = pagina < totalPaginas;

  const { start, end } = useMemo(() => {
    if (!totalItems || !porPagina) return { start: null, end: null };
    const s = (pagina - 1) * porPagina + 1;
    const e = Math.min(pagina * porPagina, totalItems);
    return { start: s, end: e };
  }, [pagina, porPagina, totalItems]);

  // Ventana de páginas con elipsis
  const pages = useMemo(() => {
    const p = Math.max(1, Math.min(pagina, totalPaginas));
    const total = Math.max(1, totalPaginas);
    const max = Math.max(3, maxButtons);

    if (total <= max) return Array.from({ length: total }, (_, i) => i + 1);

    const left = Math.max(2, p - Math.floor((max - 2) / 2));
    const right = Math.min(total - 1, left + (max - 3));
    const adjustedLeft = Math.max(2, right - (max - 3));

    const arr = [1];
    if (adjustedLeft > 2) arr.push("ellipsis-left");
    for (let i = adjustedLeft; i <= right; i++) arr.push(i);
    if (right < total - 1) arr.push("ellipsis-right");
    arr.push(total);
    return arr;
  }, [pagina, totalPaginas, maxButtons]);

  const renderBtn = (key, label, { onClick, disabled = false, current = false, title }) => (
    <button
      key={key}
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      aria-current={current ? "page" : undefined}
      title={title}
      className={[
        "px-3 py-2 rounded-xl border text-sm transition tabular-nums",
        disabled
          ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
          : current
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-700 border-gray-300 hover:border-gray-400 hover:bg-gray-50",
      ].join(" ")}
    >
      {label}
    </button>
  );

  return (
    <div
      className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between
                 rounded-2xl border border-gray-200 bg-white/90 px-4 py-3 shadow-sm"
      role="navigation"
      aria-label="Paginación"
    >
      {/* Resumen compacto */}
      {showSummary ? (
        <div className="text-sm text-gray-600">
          {start && end ? (
            <>
              Mostrando{" "}
              <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-800">
                {start}–{end}
              </span>{" "}
              de <span className="font-medium text-gray-800">{totalItems}</span>
            </>
          ) : (
            <>
              Página <span className="font-medium text-gray-800">{pagina}</span> de{" "}
              <span className="font-medium text-gray-800">{totalPaginas}</span>
            </>
          )}
        </div>
      ) : (
        <span />
      )}

      {/* Controles */}
      <div className="flex items-center gap-2">
        {showFirstLast &&
          renderBtn(
            "first",
            "⏮ Primera",
            {
              onClick: () => onGoToPage && onGoToPage(1),
              disabled: !onGoToPage || !canPrev,
              title: "Primera página",
            }
          )}

        {renderBtn("prev", "← Anterior", { onClick: onAnterior, disabled: !canPrev, title: "Página anterior" })}

        {/* Números con elipsis */}
        <div className="flex items-center gap-1">
          {pages.map((n, idx) =>
            typeof n === "number"
              ? renderBtn(
                  `p-${n}`,
                  n,
                  {
                    onClick: () => onGoToPage && onGoToPage(n),
                    disabled: !onGoToPage,
                    current: n === pagina,
                    title: `Ir a la página ${n}`,
                  }
                )
              : (
                <span key={`${n}-${idx}`} className="px-2 text-gray-400 select-none">…</span>
              )
          )}
        </div>

        {renderBtn("next", "Siguiente →", { onClick: onSiguiente, disabled: !canNext, title: "Página siguiente" })}

        {showFirstLast &&
          renderBtn(
            "last",
            "Última ⏭",
            {
              onClick: () => onGoToPage && onGoToPage(totalPaginas),
              disabled: !onGoToPage || !canNext,
              title: "Última página",
            }
          )}
      </div>
    </div>
  );
}