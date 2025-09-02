// src/components/admin/KPIBloque.jsx
import KPICard from "./KPICard";

/**
 * Renderiza un grid de KPIs. Cada item debe tener:
 * { title, value, icon, tooltip, onClick }
 */
export default function KPIBloque({ items = [] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-3">
      {items.map((it, idx) => (
        <KPICard
          key={idx}
          title={it.title}
          value={it.value}
          icon={it.icon}
          tooltip={it.tooltip}
          onClick={it.onClick}
        />
      ))}
    </div>
  );
}
