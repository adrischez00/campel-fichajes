import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function Header({
  usuario,                 // string o { email }
  onLogout,                // si no lo pasas, no muestra el botón
  title,                   // opcional: título de la página
  subtitle,                // opcional: subtítulo (p.ej. email del usuario)
  showBack = false,        // opcional: muestra botón volver
  onBack,                  // opcional: callback propio del botón volver
  logoSrc = "/logo.png", // compat con tu versión actual
  children,                // acciones extra a la derecha (botones, filtros...)
}) {
  const isLoggedIn = !!usuario;
  const navigate = useNavigate();
  const userLabel = typeof usuario === "string" ? usuario : usuario?.email;

  const handleBack = () => {
    if (onBack) onBack();
    else navigate(-1);
  };

  return (
    <header className="bg-white/90 backdrop-blur border-b shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-5 flex items-center justify-between">
        {/* Izquierda: back + logo + títulos */}
        <div className="flex items-center gap-3 sm:gap-4">
          {showBack && (
            <button
              onClick={handleBack}
              className="px-3 py-2 rounded-md bg-white hover:bg-slate-50 border border-slate-200 shadow-sm"
              title="Volver"
            >
              ←
            </button>
          )}

          {/* Logo + nombre empresa */}
          <img
            src={logoSrc}
            alt="Logo Campel"
            className="w-[50px] sm:w-[90px] h-[50px] sm:h-[90px] object-contain"
          />

          {/* Títulos */}
          <div className="flex flex-col">
            <h1 className="text-lg sm:text-3xl font-semibold text-[#004B87] tracking-tight">
              {title || "Asesoría Campel"}
            </h1>
            {subtitle && (
              <span className="text-xs sm:text-sm text-slate-600">{subtitle}</span>
            )}
          </div>
        </div>

        {/* Derecha: acciones extra + usuario + logout */}
        <div className="flex items-center gap-3 sm:gap-4">
          {children /* CTA/filtros opcionales */}

          {isLoggedIn ? (
            <div className="flex items-center gap-3 sm:gap-4 text-sm sm:text-base text-gray-700">
              <div className="relative group">
                <span className="text-xl cursor-default">👤</span>
                <span className="hidden sm:inline font-medium">{userLabel}</span>
                <div className="absolute hidden group-hover:block sm:hidden bg-white border rounded shadow px-2 py-1 text-xs left-1/2 -translate-x-1/2 top-full mt-1 whitespace-nowrap z-10">
                  {userLabel}
                </div>
              </div>

              {onLogout && (
                <button
                  onClick={onLogout}
                  className="bg-[#004B87] text-white px-3 sm:px-4 py-2 rounded-md hover:bg-[#003B6D] transition whitespace-nowrap"
                >
                  Cerrar sesión
                </button>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-600 whitespace-nowrap">
              Inicia sesión para acceder
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
