// src/config.js
const RAW = (import.meta.env?.VITE_API_URL || '').trim();
// fallback útil para dev local si no has definido el .env
const FALLBACK = 'http://localhost:8080';

// quita la barra final para evitar // en las peticiones
export const API_URL = (RAW || FALLBACK).replace(/\/$/, '');


