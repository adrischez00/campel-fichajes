// src/components/admin/TabGroup.jsx
import { useEffect, useMemo, useRef } from "react";

export default function TabGroup({ tabs, activeTab, setActiveTab }) {
  // Sanitiza un id estable (para aria-controls / aria-labelledby)
  const toId = (name) =>
    `tab-${String(name).toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9\-]/g, "")}`;

  const ids = useMemo(() => tabs.map(t => toId(t.name)), [tabs]);
  const activeIndex = Math.max(0, tabs.findIndex(t => t.name === activeTab?.name));
  const refs = useRef([]);

  // Enfoca el tab activo al montar/cambiar
  useEffect(() => {
    const el = refs.current[activeIndex];
    if (el && document.activeElement?.getAttribute("role") === "tab") return; // no robar foco si el usuario navega
    // Opcional: comenta la línea si no quieres enfoque automático
    // el?.focus();
  }, [activeIndex]);

  const onKeyDown = (e, index) => {
    const max = tabs.length - 1;
    let next = index;

    switch (e.key) {
      case "ArrowRight": next = index === max ? 0 : index + 1; break;
      case "ArrowLeft":  next = index === 0   ? max : index - 1; break;
      case "Home":       next = 0; break;
      case "End":        next = max; break;
      default: return;
    }

    e.preventDefault();
    const tab = tabs[next];
    setActiveTab(tab);
    refs.current[next]?.focus();
  };

  return (
    <div
      className="
        sticky top-0 z-30 -mx-6 px-6 pb-3 pt-2
        bg-[#F4F6F8]/70 backdrop-blur supports-[backdrop-filter]:backdrop-blur
      "
    >
      <div
        role="tablist"
        aria-label="Secciones del panel de administración"
        className="inline-flex gap-2 rounded-2xl border border-gray-200 bg-white/90 p-1 shadow-sm"
      >
        {tabs.map((t, i) => {
          const isActive = activeTab?.name === t.name;
          const id = ids[i];
          return (
            <button
              key={t.name}
              id={`${id}-tab`}
              ref={(el) => refs.current[i] = el}
              role="tab"
              aria-selected={isActive}
              aria-controls={`${id}-panel`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActiveTab(t)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={[
                "inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition outline-none",
                isActive
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-gray-700 hover:bg-gray-100",
                "focus-visible:ring-2 focus-visible:ring-blue-300"
              ].join(" ")}
              title={t.label}
            >
              <span aria-hidden>{t.icon ?? "●"}</span>
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
