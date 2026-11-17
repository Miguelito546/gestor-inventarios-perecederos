/* Comportamiento común de la interfaz: menú, tema, tablas en celular, estados de carga y avisos. */
(function () {
  'use strict';
  const raiz = document.documentElement;
  const cuerpo = document.body;

  /* ---------- Menú lateral desplegable (tablet y celular) ---------- */
  const botonMenu = document.querySelector('[data-menu]');
  function abrirMenu(abrir) {
    cuerpo.classList.toggle('menu-abierto', abrir);
    if (botonMenu) {
      botonMenu.setAttribute('aria-expanded', String(abrir));
      botonMenu.setAttribute('aria-label', abrir ? 'Cerrar menú' : 'Abrir menú');
    }
    if (abrir) { const primero = document.querySelector('#menu-lateral a'); if (primero) primero.focus(); }
  }
  if (botonMenu) botonMenu.addEventListener('click', () => abrirMenu(!cuerpo.classList.contains('menu-abierto')));
  document.querySelectorAll('[data-cerrar-menu]').forEach(el => el.addEventListener('click', () => abrirMenu(false)));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && cuerpo.classList.contains('menu-abierto')) { abrirMenu(false); if (botonMenu) botonMenu.focus(); }
  });

  /* ---------- Modo claro / oscuro ---------- */
  const botonTema = document.querySelector('[data-tema]');
  function temaActual() {
    return raiz.dataset.tema || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro');
  }
  function rotularTema() {
    if (botonTema) botonTema.setAttribute('aria-label', temaActual() === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
  }
  if (botonTema) {
    rotularTema();
    botonTema.addEventListener('click', () => {
      const nuevo = temaActual() === 'oscuro' ? 'claro' : 'oscuro';
      raiz.dataset.tema = nuevo;
      try { localStorage.setItem('tema', nuevo); } catch (e) { /* sin almacenamiento: solo esta pantalla */ }
      rotularTema();
      window.dispatchEvent(new Event('cambio-tema'));
    });
  }

  /* ---------- Tablas: en celular cada fila se muestra como tarjeta ---------- */
  document.querySelectorAll('table.tabla').forEach(tabla => {
    const filas = Array.from(tabla.rows);
    const encabezado = filas.find(f => f.querySelector('th'));
    if (!encabezado) return;
    encabezado.classList.add('encabezados');
    const titulos = [];
    Array.from(encabezado.cells).forEach(c => {
      if (c.tagName === 'TH' && !c.hasAttribute('scope')) c.setAttribute('scope', 'col');
      for (let i = 0; i < (c.colSpan || 1); i++) titulos.push(c.textContent.trim());
    });
    filas.forEach(fila => {
      if (fila === encabezado) return;
      let i = 0;
      Array.from(fila.cells).forEach(celda => {
        if (celda.colSpan === 1 && titulos[i] !== undefined) celda.dataset.etiqueta = titulos[i];
        i += celda.colSpan || 1;
      });
    });
    tabla.classList.add('apilada');
  });

  /* ---------- Avisos que se pueden cerrar ---------- */
  document.addEventListener('click', e => {
    const boton = e.target.closest('[data-cerrar-aviso]');
    if (boton) boton.closest('.aviso').remove();
  });

  /* ---------- Estados de carga al cambiar de pantalla ---------- */
  let temporizador = null, seguro = null;
  function iniciarCarga() {
    cuerpo.classList.add('cargando');
    const principal = document.getElementById('principal');
    if (principal) principal.setAttribute('aria-busy', 'true');
    const estado = document.getElementById('estado-carga');
    if (estado) estado.textContent = 'Cargando…';
    // Solo muestra el esqueleto si la pantalla tarda (con la base en la nube puede tardar un poco)
    temporizador = setTimeout(() => cuerpo.classList.add('mostrar-esqueleto'), 350);
    seguro = setTimeout(terminarCarga, 15000);
  }
  function terminarCarga() {
    clearTimeout(temporizador); clearTimeout(seguro);
    cuerpo.classList.remove('cargando', 'mostrar-esqueleto');
    const principal = document.getElementById('principal');
    if (principal) principal.removeAttribute('aria-busy');
    document.querySelectorAll('.btn.ocupado').forEach(b => { b.classList.remove('ocupado'); b.removeAttribute('aria-busy'); });
    document.querySelectorAll('form[data-enviando]').forEach(f => delete f.dataset.enviando);
  }
  window.addEventListener('pageshow', terminarCarga);  // al volver con "Atrás"

  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest('a[href]');
    if (!a || a.target || a.hasAttribute('download') || a.dataset.sinCarga !== undefined) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.hash && url.pathname === location.pathname && url.search === location.search) return;
    if (/\/(logout|static)\b/.test(url.pathname)) return;
    iniciarCarga();
  });

  document.addEventListener('submit', e => {
    const form = e.target;
    if (e.defaultPrevented) return;
    if (form.dataset.enviando) { e.preventDefault(); return; }  // evita enviar dos veces
    const boton = e.submitter;
    // Exportar PDF o CSV descarga un archivo y no cambia de pantalla
    const descarga = boton && boton.name === 'formato' && /^(pdf|csv)$/.test(boton.value) || boton && boton.value === 'csv';
    if (descarga) return;
    form.dataset.enviando = '1';
    if (boton && boton.classList.contains('btn')) { boton.classList.add('ocupado'); boton.setAttribute('aria-busy', 'true'); }
    iniciarCarga();
  });

})();
