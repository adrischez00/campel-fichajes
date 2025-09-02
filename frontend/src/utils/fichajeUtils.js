export function obtenerFichajesDeHoy(fichajes, hoy) {
  return fichajes
    .filter(f =>
      new Date(f.timestamp).toLocaleDateString('es-ES', { timeZone: 'Europe/Madrid' }).split('/').reverse().join('-') === hoy
    )
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

export function calcularTiempoTotal(fichajesHoy) {
  let totalMs = 0;
  for (let i = 0; i < fichajesHoy.length; i += 2) {
    const entrada = new Date(fichajesHoy[i].timestamp);
    const salida = fichajesHoy[i + 1] ? new Date(fichajesHoy[i + 1].timestamp) : new Date();
    totalMs += salida - entrada;
  }
  const horas = Math.floor(totalMs / 3600000);
  const minutos = Math.floor((totalMs % 3600000) / 60000);
  const segundos = Math.floor((totalMs % 60000) / 1000);
  return `${horas}h ${minutos}min ${segundos}s`;
}

export function obtenerEstadoActual(fichajesHoy) {
  const ultimo = fichajesHoy[fichajesHoy.length - 1];
  return ultimo?.tipo === 'entrada' ? 'fichado' : 'descanso';
}

export function agruparFichajesPorFechaConIntervalos(fichajes) {
  const fichajesPorDia = {};

  // Agrupar por fecha
  fichajes.forEach(f => {
    const fecha = new Date(f.timestamp).toLocaleDateString('es-ES', { timeZone: 'Europe/Madrid' });
    if (!fichajesPorDia[fecha]) fichajesPorDia[fecha] = [];
    fichajesPorDia[fecha].push(f);
  });

  const resultado = [];

  // Procesar cada día
  for (const fecha in fichajesPorDia) {
    const lista = fichajesPorDia[fecha].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const intervalos = [];
    let totalMs = 0;

    for (let i = 0; i < lista.length; i += 2) {
      const entrada = lista[i];
      const salida = lista[i + 1] || null;

      const tEntrada = new Date(entrada.timestamp);
      const tSalida = salida ? new Date(salida.timestamp) : null;

      const duracionMs = tSalida ? tSalida - tEntrada : null;
      const duracion = duracionMs
        ? `${Math.floor(duracionMs / 3600000)}h ${Math.floor((duracionMs / 60000) % 60)}min`
        : 'En curso';

      if (duracionMs) totalMs += duracionMs;

      intervalos.push({
        entrada,
        salida,
        duracion,
      });
    }

    const total = `${Math.floor(totalMs / 3600000)}h ${Math.floor((totalMs / 60000) % 60)}min`;

    resultado.push({
      fecha,
      intervalos,
      total
    });
  }

  return resultado.sort((a, b) => {
    const d1 = new Date(a.fecha.split('/').reverse().join('-'));
    const d2 = new Date(b.fecha.split('/').reverse().join('-'));
    return d2 - d1; // Orden descendente
  });
}
