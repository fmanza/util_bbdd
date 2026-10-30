# TRACEABILITY

## Session metadata
- id: 2026-10-30-web-gaps-ola10
- fecha: 2026-10-30
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE por fase + VERSION de la ola 10 (v5.2.0); PLAN y AUDIT_PLAN aprobados en el plan

## Prompt issued
Ola 10 del plan de huecos de util_bbdd_web (Grupo 10, fases U-10.1 a U-10.4: G48, G47, G46, G45), un commit por
fase, sin cambios de API, SemVer MINOR 5.2.0 (D10-1); si Mermaid 12 no es compatible, U-10.4 sale de la ola (D10-4).
Plan canónico: `docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (Grupo 10 y AUDIT_PLAN de la ola 10, GO_CONDICIONAL
con D10-1 a D10-5 aprobadas el 2026-10-30).

## Context sources
- `src/util_bbdd/bulk/_support/sql_helpers.py` (`_LiteralTemplate`, `_json_as_string_literals`, caminos por fila).
- `src/util_bbdd/dump/_fk_graph.py` (`bfs_component`) y su uso en `dump/orchestrator.py:1239` (orden de carga).
- `src/util_bbdd/comparar/reporters/_base.py`, `markdown_reporter.py`, `html_reporter.py` y
  `templates/diff_report.html.j2` (`initialize`/`run`).
- npm: `mermaid@12.2.0` (publicada el 2026-10-13), tarball y `integrity` del registro; `package-lock.json` del
  frontend de util_bbdd_web (misma `integrity`).
- Banco: 6 motores (PostgreSQL, MySQL, MariaDB, SQL Server en 51833, Oracle Free, HSQLDB con `JAVA_HOME` del JDK 25).

## AI output summary
- U-10.1 `87e53862` G48: reproducido en SQLite, PostgreSQL, SQL Server, Oracle y MySQL (`CompileError` en VALUES y
  SET; el WHERE ya funcionaba porque `coerce_compared_value` da `String` para un `str`). `_TEMPORAL_TYPES` y
  `_LiteralTemplate._temporal_processor` (decide por valor: `str` → `render_literal_value(valor, String())`; el resto,
  el procesador del tipo); en el camino por fila, `_json_as_string_literals` también envuelve esos `str`. Nota de
  `NLS_DATE_FORMAT` en el docstring de `dry_run` (R10-2). 27 tests (`tests/unit/bulk/test_temporal_text_literals.py`).
- U-10.2 `f1c07373` G47: `bfs_component` recorre `sorted(adj[node])`. 3 tests, uno con 6 `PYTHONHASHSEED` en
  subprocesos (`tests/unit/dump/test_fk_graph_cycle_order.py`).
- U-10.3 `ad9fe85c` G46: `escape_mermaid_label` pasa a espacio C0, DEL, C1, U+2028 y U+2029, y `%(?=%)` → `% ` (sin
  pares `%%`, también con `%%%`). `_mermaid_node_id` en el Markdown (`[^A-Za-z0-9_]` → `_`, sufijo `_2`… con los ids
  de todo el diagrama). 12 tests con snapshot del bloque Markdown y de las líneas de nodo del HTML
  (`tests/comparar/test_mermaid_injection.py`).
- U-10.4 `c3a1d554` G45: `MERMAID_VERSION = "12.2.0"` y su SRI (`sha384-8xUh…NYgp`) calculado sobre
  `dist/mermaid.min.js` del tarball, cuya sha512 coincide con la `integrity` del registro. Plantilla comprobada en
  Chromium headless (Playwright) con red: SRI aceptado, `initialize`/`run` sin errores, los 3 diagramas iguales que con
  10.9.8; con un SRI incorrecto el script se bloquea (`no-mermaid`). Test unitario de las constantes y test
  `integration` del SRI contra jsDelivr (se salta sin red). `docs/api/schema_comparator.md` actualizado.
- Evidencias por fase (shell sin variables del banco): pytest 6900 / 6903 / 6915 / 6917 passed, 618 skipped
  (`build/logs/u10_{1,2,3,4}_pytest.txt`); ruff, `ruff format` y mypy (356 ficheros) limpios en cada fase;
  `zensical build --strict` limpio (`build/logs/u10_4_zensical.txt`).
- G48 en motores reales (script del scratchpad, tabla `ola10_g48`): el SQL de `dry_run=True` (INSERT y UPDATE con fechas
  en texto) se ejecuta tal cual en PostgreSQL, MySQL, MariaDB, SQL Server y Oracle (Oracle con `NLS_DATE_FORMAT` y
  `NLS_TIMESTAMP_FORMAT` ISO en la sesión) y deja los valores esperados.
- Integración (`-m integration`, 6 motores, `JAVA_HOME` del JDK 25): 667 passed, 8 skipped y 8 failed de entorno
  (`build/logs/ola10_integration.txt`): `asyncpg` y `aioodbc` no están en el venv local (PostgreSQL async y SQL
  Server async), como en los cierres de 4.3.0 a 4.6.0; ninguno en `bulk`, `dump` ni `comparar`.
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas; 356 ficheros; SVG sin cambios de contenido.
- Wheel: `python -m build` correcto; `dist/util_bbdd-5.2.0-py3-none-any.whl` con `.sha256` (`592f76c0…63e5b4`),
  instalado en un venv limpio (versión 5.2.0, `MERMAID_VERSION` 12.2.0, escape y BFS nuevos).
- VERSION: `release: v5.2.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fechas en texto (G48) | `src/util_bbdd/bulk/_support/sql_helpers.py`, docstring de `dry_run` en `bulk/crud.py` | completado (v5.2.0) |
| Ciclos estables (G47) | `src/util_bbdd/dump/_fk_graph.py` | completado (v5.2.0) |
| Escape Mermaid (G46) | `src/util_bbdd/comparar/reporters/_base.py`, `comparar/reporters/markdown_reporter.py` | completado (v5.2.0) |
| Mermaid 12 (G45) | `src/util_bbdd/comparar/reporters/html_reporter.py`, `docs/api/schema_comparator.md` | completado (v5.2.0) |
| Tests | `tests/unit/bulk/test_temporal_text_literals.py`, `tests/unit/dump/test_fk_graph_cycle_order.py`, `tests/comparar/test_mermaid_injection.py`, `tests/comparar/test_diff_reporters.py` | completado |

## Desviaciones del plan
- U-10.1: en el WHERE no hizo falta cambio (ya funcionaba); el cambio se limita a VALUES y SET.
- U-10.1: la ejecución en SQLite con fechas en texto falla en el tipo `Date` de SQLAlchemy («SQLite Date type only
  accepts Python date objects»), antes y después; queda fijado en un test. No afecta a la vista previa de W-10.1.
- U-10.3: además de `\r`, `\n` y C0, se pasan a espacio DEL, C1 y U+2028/U+2029 (fin de línea en JavaScript).
- U-10.4: la «prueba manual del HTML con red» se hizo automatizada en Chromium headless; el SRI contra el fichero queda
  además como test `integration`.

## Notas para las fases W-10 de util_bbdd_web
- W-10.0: wheel 5.2.0; `exclude-newer` necesita la excepción para util_bbdd (release del 2026-10-30).
- W-10.1: la vista previa de un CSV con `DATE`/`DATETIME` en texto genera el SQL con los textos tal cual; en SQLite
  la carga real (`dry_run=False`) con texto en `DATE` sigue fallando en SQLAlchemy, en MariaDB funciona.
- W-10.2: `plan().cycles` ya sale estable, pero los rodeos (`structure_hash` ordenado, `stripMermaidConfig`) se
  mantienen (D10-2). Los ids de nodo del Markdown cambian para nombres fuera de `[A-Za-z0-9_ ]`.

## Directrices para Futuras IAs
- **[bulk]**: el renderizado de literales del modo seco decide primero por columna (`_processor`: binario → temporal →
  WHERE → procesador directo) y, para JSON y fechas en texto, por valor; el camino por fila equivalente es
  `_json_as_string_literals`. Un tipo nuevo que necesite tratamiento por valor va en los dos sitios.
- **[bulk]**: en el WHERE, `coerce_compared_value(operators.eq, valor)` ya adapta el tipo al valor (`str` → `String`);
  no hace falta tratar allí lo que se trata en VALUES/SET.
- **[dump]**: `cycles` es solo presentación; el orden de carga de las tablas en ciclo sale de `ordered + cycle_tables`
  (orden de entrada), no de `cycles`.
- **[comparar]**: Mermaid busca directivas `%%{…}%%` en cualquier parte del texto, no solo a principio de línea; el
  escape de labels debe romper todo par `%%`. El HTML usa ids `A{n}`/`M{n}`/`R{n}` y no depende del nombre.
- **[comparar]**: para cambiar `MERMAID_VERSION`, calcular el SRI sobre `dist/mermaid.min.js` del tarball de npm
  (verificado con su `integrity` sha512) y comprobar la plantilla en Chromium: Python Playwright y Chromium están
  instalados en el equipo (`%LOCALAPPDATA%/ms-playwright`).
- **[tests]**: `tests/comparar/test_diff_reporters.py::test_mermaid_sri_matches_the_cdn_file` es `integration` pero
  `pytest.ini` no filtra por marcador: se ejecuta en el `pytest` normal y se salta sin red.

## Veredicto final
Veredicto: CLOSED (ola 10, v5.2.0)
Pendientes al cierre:
- Push de `develop`, tag `v5.2.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (el usuario).
- Hacer W-10.0, W-10.1 y W-10.2 en util_bbdd_web y su `release: v1.9.0` (D10-5).
