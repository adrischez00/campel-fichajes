// src/utils/ausenciasCatalogo.js

// Paleta por tipo para usar en badges/calendario
export const TIPO_THEME = {
  VACACIONES:  { dot: "bg-indigo-500",  bg: "bg-indigo-500/10",  text: "text-indigo-800",  ring: "ring-indigo-300/40" },
  PERMISO:     { dot: "bg-sky-500",     bg: "bg-sky-500/10",     text: "text-sky-800",     ring: "ring-sky-300/40" },
  REGISTRO_JORNADA: { dot: "bg-emerald-500",  bg: "bg-emerald-500/10",  text: "text-emerald-800",  ring: "ring-emerald-300/40" },
};

export const TIPOS = [
  // code visible solo si quieres mostrarlo; el backend recibe modelTipo
  { code: "100", label: "Vacaciones", modelTipo: "VACACIONES", fixed: { parcial: false, retribuida: true } },
  { code: "200", label: "Permisos",   modelTipo: "PERMISO" },
  { code: "300", label: "Registro de jornada / Compensaciones", modelTipo: "REGISTRO_JORNADA" },
];

// Subtipos por tipo (el backend recibe modelSubtipo)
export const SUBTIPOS = {
  VACACIONES: [
    { code: "100", label: "Vacaciones",               modelSubtipo: "VACACIONES" },
    { code: "101", label: "Vacaciones año anterior",  modelSubtipo: "VACACIONES_ANTERIOR" },
  ],
  PERMISO: [
    { code: "334", label: "Accidente / enfermedad familiar",         modelSubtipo: "ACCIDENTE_FAMILIAR", defaults: { retribuida: true } },
    { code: "331", label: "Acompañamiento médico (no retribuido)",   modelSubtipo: "ACOMP_MEDICO_NR",    defaults: { retribuida: false, parcial: true } },
    { code: "CITA",label: "Cita médica",                              modelSubtipo: "CITA_MEDICA",        defaults: { parcial: true, retribuida: true } },
    { code: "AP",  label: "Asuntos propios",                          modelSubtipo: "ASUNTOS_PROPIOS",    defaults: { parcial: false, retribuida: false } },
    { code: "VIA", label: "Viaje",                                    modelSubtipo: "VIAJE",              defaults: { parcial: false, retribuida: false } },
    { code: "307", label: "Baja",                                     modelSubtipo: "BAJA",               defaults: { parcial: false, retribuida: true } },
    { code: "303", label: "Baja IT",                                  modelSubtipo: "BAJA_IT",            defaults: { parcial: false, retribuida: true } },
    { code: "304", label: "Cuidado del lactante",                     modelSubtipo: "CUIDADO_LACTANTE",   defaults: { parcial: true,  retribuida: true } },
    { code: "323", label: "Deber inexcusable público/personal",       modelSubtipo: "DEBER_INEXCUSABLE",  defaults: { parcial: false, retribuida: true } },
    { code: "510", label: "Examen oficial",                           modelSubtipo: "EXAMEN_OFICIAL",     defaults: { parcial: true,  retribuida: true } },
    { code: "OTR", label: "Otro",                                     modelSubtipo: "OTRO" },
  ],
  REGISTRO_JORNADA: [
    { code: "302", label: "Compensación por trabajo",         modelSubtipo: "COMPENSACION_TRABAJO", defaults: { retribuida: true } },
    { code: "306", label: "Día a compensar por guardia",      modelSubtipo: "COMPENSAR_GUARDIA",    defaults: { retribuida: true } },
    { code: "301", label: "Día a compensar (año anterior)",   modelSubtipo: "COMPENSAR_ANTERIOR",   defaults: { retribuida: true } },
  ],
};

// Sugerencias de duración para parciales (solo UX)
export const PARCIAL_SUGERENCIAS = {
  CITA_MEDICA:  { horas: 2,  minutos: 0 },
  EXAMEN_OFICIAL: { horas: 3, minutos: 0 },
};
