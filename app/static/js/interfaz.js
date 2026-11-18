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
  const botonTema = document.querySelector('[data-cambiar-tema]');
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
    if (descarga) {
      // En la ventana del programa (.exe) se usa el cuadro "Guardar como" de Windows,
      // que siempre deja la extensión .pdf o .csv aunque se cambie el nombre.
      if (window.pywebview && window.pywebview.api && window.pywebview.api.guardar_archivo) {
        e.preventDefault();
        guardarEnEscritorio(form, boton);
      }
      return;
    }
    form.dataset.enviando = '1';
    if (boton && boton.classList.contains('btn')) { boton.classList.add('ocupado'); boton.setAttribute('aria-busy', 'true'); }
    iniciarCarga();
  });

  /* ---------- Guardar reportes desde la ventana del programa (.exe) ---------- */
  function nombreDeArchivo(respuesta, boton) {
    const cabecera = respuesta.headers.get('Content-Disposition') || '';
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cabecera);
    return m ? decodeURIComponent(m[1]) : 'reporte.' + (boton.value === 'csv' ? 'csv' : 'pdf');
  }
  function aBase64(blob) {
    return new Promise((ok, mal) => {
      const lector = new FileReader();
      lector.onload = () => ok(String(lector.result).split(',')[1] || '');
      lector.onerror = () => mal(lector.error);
      lector.readAsDataURL(blob);
    });
  }
  function avisoFlotante(html, tipo) {
    document.querySelectorAll('.aviso-flotante').forEach(a => a.remove());
    const aviso = document.createElement('div');
    aviso.className = 'aviso-cambios aviso-flotante' + (tipo ? ' ' + tipo : '');
    aviso.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
    aviso.innerHTML = html + '<button type="button" class="btn chico fantasma" aria-label="Cerrar aviso" data-cerrar>✕</button>';
    aviso.querySelector('[data-cerrar]').addEventListener('click', () => aviso.remove());
    cuerpo.appendChild(aviso);
    return aviso;
  }
  async function guardarEnEscritorio(form, boton) {
    if (boton.classList.contains('ocupado')) return;
    boton.classList.add('ocupado'); boton.setAttribute('aria-busy', 'true');
    try {
      const datos = new FormData(form);
      datos.append(boton.name, boton.value);
      const metodo = (form.method || 'get').toLowerCase();
      const url = new URL(form.getAttribute('action') || location.href, location.href);
      let respuesta;
      if (metodo === 'get') {
        url.search = new URLSearchParams(datos).toString();
        respuesta = await fetch(url, { cache: 'no-store' });
      } else {
        respuesta = await fetch(url, { method: 'POST', body: datos });
      }
      const tipo = respuesta.headers.get('Content-Type') || '';
      if (!respuesta.ok || tipo.startsWith('text/html')) { location.href = respuesta.url; return; }  // aviso o sesión cerrada
      const nombre = nombreDeArchivo(respuesta, boton);
      const ruta = await window.pywebview.api.guardar_archivo(nombre, await aBase64(await respuesta.blob()));
      if (!ruta) return;  // canceló el cuadro de guardar
      const archivo = ruta.split(/[\\/]/).pop();
      const aviso = avisoFlotante('<span>Se guardó <b></b></span>' +
        '<button type="button" class="btn chico" data-abrir>Abrir</button>' +
        '<button type="button" class="btn chico claro" data-carpeta>Ver en carpeta</button>');
      aviso.querySelector('b').textContent = archivo;
      aviso.querySelector('[data-abrir]').addEventListener('click', () => window.pywebview.api.abrir_guardado(ruta));
      aviso.querySelector('[data-carpeta]').addEventListener('click', () => window.pywebview.api.mostrar_guardado(ruta));
    } catch (err) {
      avisoFlotante('<span>No se pudo guardar el archivo. Revisa la conexión e inténtalo de nuevo.</span>', 'error');
    } finally {
      boton.classList.remove('ocupado'); boton.removeAttribute('aria-busy');
    }
  }

  /* ---------- Cambios hechos en otros equipos (consulta cada 10 s) ---------- */
  // Todos usan la misma base de datos. Cada 10 s se pregunta si hubo cambios; si los hay:
  //  - Monitoreo actualiza su gráfica sin recargar,
  //  - las demás pantallas se recargan solas (conservando la posición),
  //  - pero si estás escribiendo en un formulario, solo aparece un aviso para no borrar lo escrito.
  const urlCambios = cuerpo.dataset.cambios;
  if (urlCambios) {
    const CADA_MS = 10000;
    let huella = cuerpo.dataset.huella || null;
    let escribiendo = false, aviso = null, consultando = false;
    const marcarEscritura = e => { if (e.target.closest && e.target.closest('form')) escribiendo = true; };
    document.addEventListener('input', marcarEscritura);
    document.addEventListener('change', marcarEscritura);

    function hayEdicionEnCurso() {
      if (escribiendo) return true;
      const activo = document.activeElement;
      return !!(activo && activo.matches && activo.matches('input:not([type=button]):not([type=submit]), textarea, select'));
    }
    function recargar() {
      if (cuerpo.dataset.recargable !== undefined) location.reload();
      else location.href = location.pathname + location.search;   // pantalla que salió de un formulario: vuelve a pedirla
    }
    function mostrarAviso() {
      if (aviso) return;
      aviso = document.createElement('div');
      aviso.className = 'aviso-cambios';
      aviso.setAttribute('role', 'status');
      aviso.innerHTML = '<span>Hay cambios nuevos de otros usuarios.</span>' +
        '<button type="button" class="btn chico">Actualizar</button>' +
        '<button type="button" class="btn chico fantasma" aria-label="Cerrar aviso">✕</button>';
      const [actualizar, cerrar] = aviso.querySelectorAll('button');
      actualizar.addEventListener('click', recargar);
      cerrar.addEventListener('click', () => { aviso.remove(); aviso = null; });
      cuerpo.appendChild(aviso);
    }
    function hubieronCambios() {
      if (typeof window.alActualizarDatos === 'function') { window.alActualizarDatos(); return; }
      if (hayEdicionEnCurso() || cuerpo.classList.contains('menu-abierto')) mostrarAviso();
      else recargar();
    }
    async function revisar() {
      if (consultando || document.hidden || cuerpo.classList.contains('cargando')) return;
      consultando = true;
      try {
        const r = await fetch(urlCambios, { cache: 'no-store' });
        if (r.redirected || !r.ok) return;            // sesión cerrada o falla momentánea: se reintenta luego
        const d = await r.json();
        if (!huella) { huella = d.h; return; }
        if (d.h !== huella) { huella = d.h; hubieronCambios(); }
      } catch (e) {
        /* sin conexión por un momento: se vuelve a intentar en la siguiente vuelta */
      } finally {
        consultando = false;
      }
    }
    setInterval(revisar, CADA_MS);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) revisar(); });
  }

})();
