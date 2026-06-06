================================================================================
    📚 util_bbdd - Documentación Offline
================================================================================

Bienvenido a la documentación offline de util_bbdd.

INICIO RÁPIDO
=============

Opción 1: Servidor Local Automático (RECOMENDADO)
---------------------------------------------------
Windows:
  1. Abre PowerShell en esta carpeta (Shift + Clic derecho → "Abrir PowerShell")
  2. Ejecuta: python start-server.py
  3. El navegador se abrirá automáticamente en http://localhost:8000

Linux / macOS:
  1. Abre terminal en esta carpeta
  2. Ejecuta: python3 start-server.py
  3. El navegador se abrirá automáticamente en http://localhost:8000

Opción 2: Abrir Directamente (Limitada)
----------------------------------------
  1. Haz doble clic en "index.html"
  2. Verás la documentación, pero la búsqueda no funcionará
  3. Los menús y navegación funcionan correctamente

POR QUÉ USAR EL SERVIDOR LOCAL
===============================

Al abrir archivos directamente desde el disco (file:///), los navegadores
modernos restringen características de seguridad que impiden que ciertos
JavaScript funcionen correctamente. Por eso la búsqueda no funciona.

El servidor local resuelve esto sirviendo la documentación a través de
http://, lo que permite todas las funcionalidades:
  ✅ Búsqueda completa
  ✅ Menús interactivos
  ✅ Diagramas Mermaid
  ✅ Ejemplos de código

REQUISITOS
==========

Para usar "start-server.py" necesitas Python 3.7+ instalado.
Verifica con: python --version  (Windows/macOS)
             python3 --version (Linux)

SOLUCIÓN DE PROBLEMAS
=====================

P: El navegador no se abre automáticamente
R: Abre manualmente http://localhost:8000 en tu navegador

P: "Puerto 8000 en uso"
R: El script busca automáticamente otros puertos (8001, 8002, ...)
   Revisa la terminal para ver qué puerto se está usando

P: "No se encontró Python"
R: Instálalo desde https://www.python.org/ o usa la Opción 2 (ver arriba)

P: "Permission denied" (Linux/macOS)
R: Ejecuta: chmod +x start-server.py
   Luego: ./start-server.py

INFORMACIÓN ADICIONAL
=====================

Proyecto: util_bbdd
Versión: 0.10.0
Repositorio: https://github.com/fmanza/util_bbdd
Documentación online: https://fmanza.github.io/util_bbdd/
PyPI: https://pypi.org/project/util-bbdd/

ESTRUCTURA DEL CONTENIDO
========================

  index.html              → Página principal
  INSTALLATION.md         → Guía de instalación
  ARCHITECTURE.md         → Arquitectura del proyecto
  api/                    → Referencia técnica de API
  functional/             → Documentación funcional (usuarios)
  examples/               → Ejemplos de código
  search/                 → Índice de búsqueda
  assets/                 → Estilos e iconos
  start-server.py         → Este servidor local

SOPORTE
=======

Si encuentras problemas:
  1. Revisa la documentación online: https://fmanza.github.io/util_bbdd/
  2. Abre una issue: https://github.com/fmanza/util_bbdd/issues
  3. Consulta TROUBLESHOOTING.md en la documentación

================================================================================
Generado: 2026-06-06
================================================================================
