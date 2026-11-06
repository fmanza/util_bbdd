# AUDIT_CODE — Grupo C (`catalog.json`, `llms*.txt`, `mkdocs.yml`, Mermaid local)

Revisión contra `PLAN_GRUPO_C.md`.

## Puertas

| Comando | Resultado |
|---|---|
| `ruff format` / `ruff check src tests` | Limpio |
| `mypy src tests/unit/test_protocol_conformance.py` | Sin errores (368 ficheros) |
| `pytest` (shell sin variables del banco) | **7018 passed, 618 skipped** (`build/logs/grupo_c_pytest.txt`) |
| `zensical build --strict` (sitio del repo, con ADR-006 en `nav`) | Sin incidencias |
| `zensical build --strict` con el `mkdocs.yml` **generado** | Sin incidencias (`test_zensical_strict_build`) |

## Condiciones

- **CC1** ✅ ADR-006 (`docs/adr/ADR-006-catalogo-documentacion-markdown.md`) aprobado por el usuario el 2026-11-06:
  estado ACEPTADO.
- **CC2** ✅ (`cc2_mermaid_local/`). Playwright con toda petición externa bloqueada, sobre dos sitios Zensical
  construidos con el `mkdocs.yml` generado:

  | Sitio | Peticiones externas intentadas | Diagrama |
  |---|---|---|
  | Con `markdown.mermaid_js` (Mermaid 12.2.0 de util_bbdd_web) | Solo Google Fonts del tema; **ninguna a unpkg** | Dibujado (captura `cc2_local.png`, aspecto `neo` de Mermaid 12) |
  | Sin `mermaid_js` | Google Fonts y `unpkg.com/mermaid@11` | No se dibuja (el riesgo T15, confirmado) |

## Hallazgos

| # | Tipo | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|
| C-1 | Diseño (mejora acordada C4) | `_writer.py` | Un huérfano se borra solo si su hash coincide con el del manifiesto anterior; un fichero generado y editado por el usuario se conserva. Test `test_modified_orphan_is_kept` | Hecho |
| C-2 | Diseño | `documentation_orchestrator.py` | La validación de `mermaid_js` va en `DocumentationBootstrap.settings()` con un `if` (sin inyectar función, a diferencia de lo previsto en CT4): no necesita infraestructura | Aceptado (más simple) |
| C-3 | Decisión del usuario (2026-11-06) | `mkdocs.yml` generado | Sin `nav`, la barra lateral listaba **todas** las páginas (500 tablas = 500 entradas) con carpetas en inglés (`Tables`) | **Hecho**: `nav` corta (Inicio, Tablas, Vistas, Rutinas, páginas de BD). `zensical build --strict` no avisa por páginas fuera de `nav`; se publican y se enlazan desde los índices (verificado) |
| C-4 | Decisión del usuario (2026-11-06) | Tema `material` | Sin Internet, el tema intenta cargar Google Fonts | **Hecho**: `theme.font: false` solo con `mermaid_js` (señal de sitio sin Internet). Tests de las dos variantes |
| C-6 | Entorno (no es código) | venv local | `library_version()` lee los metadatos instalados: el venv tiene una instalación editable de la 3.4.1 (`util_bbdd-3.4.1.dist-info`), así que `mkdocs.yml` y `manifest.json` dicen «3.4.1» en local. Con un wheel sale la versión real | Avisado al usuario: `pip install -e .` refresca los metadatos |
| C-5 | Rendimiento | `llms-full.txt` | Escrito por partes; el hash del manifiesto coincide con el del fichero (test) | Hecho |

## Veredicto

**APROBADO.**
