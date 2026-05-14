// Inicialización explícita de Mermaid para MkDocs.
//
// Con scripts al final de <body>, readyState ya es 'interactive' cuando
// mermaid.min.js ejecuta, por lo que su listener DOMContentLoaded puede
// dispararse antes de que Mermaid lo registre.
// Solución: startOnLoad:false + mermaid.run() explícito.

function init() {
  if (typeof mermaid === 'undefined') {
    console.warn('[mermaid] Mermaid no encontrado');
    return;
  }
  mermaid.initialize({ startOnLoad: false, theme: 'default' });
  mermaid.run({ querySelector: '.mermaid', suppressErrors: true })
    .catch(function(e) { console.warn('[mermaid] render error:', e.message || e); });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
