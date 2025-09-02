// src/components/admin/KPICard.jsx
export default function KPICard({
  title,
  value,
  icon = "📊",
  tooltip,
  onClick,
  active = false,
}) {
  const Base = onClick ? "button" : "div";
  const ariaLabel = tooltip || `${title}: ${value}`;

  return (
    <Base
      type={onClick ? "button" : undefined}
      onClick={onClick}
      title={ariaLabel}
      aria-label={ariaLabel}
      className={[
        "group relative flex items-center gap-4 rounded-2xl border p-5 shadow-sm transition-all duration-300",
        "backdrop-blur-md",
        active
          ? "bg-gradient-to-br from-blue-600/80 to-indigo-600/80 text-white border-blue-400 shadow-lg shadow-blue-500/40"
          : "bg-white/90 border-gray-200 hover:shadow-md hover:border-blue-200",
        onClick ? "cursor-pointer" : "",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
      ].join(" ")}
    >
      {/* Icono */}
      <div
        className={[
          "flex h-11 w-11 items-center justify-center rounded-xl ring-1 transition-all duration-300",
          active
            ? "bg-white/20 text-white ring-white/30 shadow-inner"
            : "bg-blue-50 text-blue-600 ring-blue-100 group-hover:bg-blue-100"
        ].join(" ")}
        aria-hidden
      >
        <span className="text-lg">{icon}</span>
      </div>

      {/* Texto */}
      <div className="min-w-0">
        <p className={`text-sm ${active ? "text-white/80" : "text-gray-500"}`}>
          {title}
        </p>
        <p
          className={`text-2xl font-extrabold tracking-tight ${
            active ? "text-white" : "text-blue-900"
          }`}
        >
          {value}
        </p>
      </div>

      {/* Flecha ↗ */}
      {onClick && (
        <span
          className={`ml-auto select-none transition-colors ${
            active
              ? "text-white/60 group-hover:text-white"
              : "text-gray-300 group-hover:text-gray-400"
          }`}
          aria-hidden
        >
          ↗
        </span>
      )}
    </Base>
  );
}