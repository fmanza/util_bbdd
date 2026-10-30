// Botón ◀/▶ para ocultar/mostrar la sidebar primaria en desktop.
// El estado persiste entre páginas y recargas mediante localStorage.
// El botón solo se inyecta en viewport ≥ 76.1875em (umbral de Material para
// el layout de tres columnas); en móvil Material gestiona su propio drawer.

(function () {
  var STORAGE_KEY = 'util_bbdd_sidebar_collapsed';
  var COLLAPSED_CLASS = 'sidebar-collapsed';

  function isDesktop() {
    return window.matchMedia('(min-width: 76.1875em)').matches;
  }

  function createButton() {
    var btn = document.createElement('button');
    btn.id = 'sidebar-toggle';
    document.body.appendChild(btn);
    return btn;
  }

  function updateButton(btn, collapsed) {
    btn.textContent = collapsed ? '▶' : '◀';
    btn.title = collapsed ? 'Expandir menú' : 'Contraer menú';
    btn.setAttribute('aria-label', btn.title);
    btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  }

  function applyState(collapsed) {
    if (collapsed) {
      document.body.classList.add(COLLAPSED_CLASS);
    } else {
      document.body.classList.remove(COLLAPSED_CLASS);
    }
  }

  function init() {
    if (!isDesktop()) return;

    var stored = localStorage.getItem(STORAGE_KEY);
    var collapsed = stored === '1';

    applyState(collapsed);

    var btn = createButton();
    updateButton(btn, collapsed);

    btn.addEventListener('click', function () {
      collapsed = !collapsed;
      applyState(collapsed);
      updateButton(btn, collapsed);
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
    });

    // Re-evaluar si cambia el tamaño de ventana (p.ej. rotar tablet)
    window.matchMedia('(min-width: 76.1875em)').addEventListener('change', function (e) {
      btn.style.display = e.matches ? '' : 'none';
      if (!e.matches) {
        // En móvil, restaurar sidebar para no interferir con el drawer de Material
        applyState(false);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
