export function formatDateTime(fechaStr, horaStr) {
  if (!fechaStr || !horaStr) return 'Fecha u hora no válida';

  try {
    const horaCompleta = horaStr.length === 5 ? `${horaStr}:00` : horaStr;

    let fechaISO;
    if (fechaStr.includes('/')) {
      const [dd, mm, yyyy] = fechaStr.split('/');
      fechaISO = `${yyyy}-${mm}-${dd}`;
    } else if (fechaStr.includes('-')) {
      fechaISO = fechaStr;
    } else {
      return 'Formato de fecha inválido';
    }

    const fechaHoraISO = `${fechaISO}T${horaCompleta}`;
    const fechaObj = new Date(fechaHoraISO);

    if (isNaN(fechaObj.getTime())) {
      return 'Formato inválido';
    }

    // 🔹 Formato más moderno: "31 jul 2025 · 10:02"
    const fechaStrFmt = fechaObj.toLocaleDateString('es-ES', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'Europe/Madrid',
    }).replace('.', ''); // quita punto de abreviatura del mes

    const horaStrFmt = fechaObj.toLocaleTimeString('es-ES', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Europe/Madrid',
    });

    return `${fechaStrFmt} · ${horaStrFmt}`;
  } catch (e) {
    return 'Formato inválido';
  }
}
