// Idioma de la página + enlaces de descarga. Todo se pone con textContent:
// nada de HTML inyectado.
(function () {
  'use strict';
  var VERSION = '1.1.0';
  var REPO = 'https://github.com/Sergi122/sonido-de-kill';
  var ARCHIVOS = {
    win: 'SonidoDeKill-' + VERSION + '-Setup.exe',
    linux: 'SonidoDeKill-' + VERSION + '-linux.tar.gz',
  };
  // mismas huellas que SHA256SUMS.txt del release (que en GitHub es inmutable)
  var SHA256 = {};
  SHA256[ARCHIVOS.win] = 'fd92647cb7c14474412dfe7e754122331c2735cb57a06bae1567a73f0835f3c1';
  SHA256[ARCHIVOS.linux] = '9de8074d6daeffdbb379f69273d5d2618f59b3992af9f36df5673c7eb6962561';

  var codigos = window.IDIOMAS.map(function (x) { return x[0]; });

  function normalizar(c) {
    if (!c) return null;
    c = String(c).replace('-', '_');
    if (codigos.indexOf(c) >= 0) return c;
    var base = c.split('_')[0].toLowerCase();
    if (base === 'zh') return /TW|HK|MO|Hant/i.test(c) ? 'zh_TW' : 'zh_CN';
    if (base === 'pt') return 'pt_BR';
    return codigos.indexOf(base) >= 0 ? base : null;
  }

  function guardado() {
    try { return localStorage.getItem('idioma'); } catch (e) { return null; }
  }

  function elegir() {
    var param = new URLSearchParams(location.search).get('lang');
    var c = normalizar(param) || normalizar(guardado());
    if (c) return c;
    var nav = navigator.languages || [navigator.language];
    for (var i = 0; i < nav.length; i++) {
      c = normalizar(nav[i]);
      if (c) return c;
    }
    return 'en';
  }

  function poner(codigo) {
    var T = window.TEXTOS[codigo] || window.TEXTOS.en;
    document.documentElement.lang = codigo.replace('_', '-');
    document.querySelectorAll('[data-t]').forEach(function (el) {
      var k = el.getAttribute('data-t');
      if (T[k] != null) el.textContent = T[k];
    });
    document.getElementById('meta').textContent = T.meta.replace('{v}', VERSION);
    document.title = T.app + ' — War Thunder';
    var img = document.getElementById('captura');
    img.src = 'img/app_' + codigo + '.webp';
    img.alt = T.captura;
    document.getElementById('idioma').value = codigo;
    try { localStorage.setItem('idioma', codigo); } catch (e) { /* sin almacenamiento */ }
  }

  function iniciar() {
    var sel = document.getElementById('idioma');
    window.IDIOMAS.forEach(function (x) {
      var o = document.createElement('option');
      o.value = x[0];
      o.textContent = x[1];
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () { poner(sel.value); });

    var base = REPO + '/releases/download/v' + VERSION + '/';
    document.getElementById('dl-win').href = base + ARCHIVOS.win;
    document.getElementById('dl-linux').href = base + ARCHIVOS.linux;
    document.getElementById('versiones').href = REPO + '/releases';
    document.querySelectorAll('.ver').forEach(function (el) { el.textContent = VERSION; });

    var dl = document.getElementById('hashes');
    Object.keys(SHA256).forEach(function (nombre) {
      var dt = document.createElement('dt');
      dt.textContent = nombre;
      var dd = document.createElement('dd');
      dd.textContent = SHA256[nombre];
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    poner(elegir());
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
