# PLAN + AUDIT_PLAN — pendientes tras v5.6.0

- Fecha: 2026-11-13 · Rama: `develop` (= `main` = `origin`, `3ccdc70c`) · Versión publicada: 5.6.0
- Fuera de alcance (ya en ejecución en otra sesión): commit G55 de util_bbdd_web y adaptación de la web a 5.6.0.
- Inventario verificado el 2026-11-13 contra git, GitHub (`gh`) y el código; cada fase cita su evidencia.

---

## PLAN

### F0 — Estado interno al día (docs, sin versión) · esfuerzo S

Evidencia: `.ai/CURRENT_STATE.md` § «Próximos pasos» da como pendientes R6 (tags 3.1.1–3.3.0) y R8 (4.0.0), ya
publicados (121 tags en `origin`, `v3.3.0` y `v4.0.0` incluidos), y D3.3 «pendiente (1.2.0)», ya hecho
(`DumpResult.constraint_reactivation_error`). `docs/roadmap.md` § «En curso» dice «Sin trabajo abierto tras v1.1.1».

1. Cerrar R6, R8 y D3.3 en la tabla; dar de alta las filas de este plan (F1–F5) con su estado.
2. «En curso» del roadmap: «Sin trabajo abierto tras v5.6.0» + enlace a este plan solo si se publica algo de él.
3. Commit `docs: estado y roadmap al día tras v5.6.0`.

### F1 — PR #26 de Dependabot: acciones de GitHub · esfuerzo S–M

Evidencia: PR abierta desde 2026-10-27, CI en verde en su momento, `mergeable: UNKNOWN`. Toca `docs.yml`,
`docs-zip-release.yml`, `docs-release.yml` (modificados en 5.6.0), `tests.yml` e `integration.yml`. Saltos de
**versión mayor**: `actions/checkout` 5→7, `actions/setup-python` 6→7, `actions/upload-artifact` 4→7,
`codecov/codecov-action` 4→7, `softprops/action-gh-release` 2→3.

1. Leer las notas de versión de las cinco acciones (cambios de inputs, Node 24, token de Codecov).
2. Opción A (recomendada): pedir `@dependabot rebase` en la PR, revisar el diff resultante, esperar CI y fusionar en
   `develop`. Opción B: aplicar los mismos saltos a mano en `develop` y cerrar la PR.
3. Verificar en Actions: `CI` (6 combinaciones), `Docs`, `Build and Publish Docs ZIP`; `Docs Release ZIP` y
   `integration.yml` no se disparan solos → `workflow_dispatch` de `docs-zip-release.yml` como prueba.
4. Commit/merge `chore(ci): acciones de GitHub a checkout@v7, setup-python@v7…`. Sin versión de la librería.

### F2 — G49: validador público del mapa de trazabilidad · esfuerzo M · MINOR (5.7.0)

Evidencia: `TraceMap.load` (`doc/infrastructure/renderers/markdown/_trace.py:92`) es privado; lo llaman
`database_documentation.py:186` y `markdown_generator.py:134`. Sus mensajes llevan la ruta completa
(`_trace.py:105,111`); los de `markdown.previous` también (`_changes.py:91,94,100,102`). `util_bbdd.doc` ya es
importable (`__all__ = ["DatabaseDocumentation", "DocumentationResult"]`). Pedido por util_bbdd_web (G49, abierto).

1. Función pública `validate_trace_map(path) -> None` en `util_bbdd.doc` (añadir a `__all__`): lanza
   `DocumentationConfigError` con **todos** los errores, sin conexión a la BD; reutiliza `TraceMap.load` (un único
   validador, sin duplicar reglas).
2. Mensajes con `file.name`, nunca la ruta absoluta, en `TraceMap.load` y `load_previous` (los de «no se puede leer»
   conservan el error del SO, sin la ruta).
3. ¿Exponer también `validate_previous(path)`? → decisión D2 (G49 solo pide el mapa).
4. Tests: válido, cada clase de error, varios errores juntos, mensaje sin ruta absoluta (`str(tmp_path)` no aparece),
   sin manager ni BD; test de superficie pública si existe.
5. Docs: `docs/api/database_documentation.md` (función nueva), guía Markdown § mapa de trazabilidad, autodoc de
   `doc`, CHANGELOG `[Unreleased]` Added/Changed.

### F3 — A2: driver ODBC de SQL Server por defecto · esfuerzo M · MINOR (5.7.0)

Evidencia: `driver_name` vale «ODBC Driver 17 for SQL Server» en cuatro sitios (`connection/config.py:626` y `:653`,
`connection/builder.py:197`, `connection/sqlserver/async_connection_sqlserver.py:38`); con solo el 18 instalado hay
que indicarlo a mano. `Encrypt` y `TrustServerCertificate` se escriben siempre en la cadena
(`connection_sqlserver.py:200-201`, `async_connection_sqlserver.py:50-51`), así que el cifrado por defecto del Driver
18 no cambia el comportamiento. Estado «Por decidir» desde 2026-10.

1. Si `driver_name` **no** se indica y el driver es pyodbc/aioodbc: elegir el «ODBC Driver NN for SQL Server» de
   número más alto de `pyodbc.drivers()`; si no hay ninguno, mantener «ODBC Driver 17…» (error del driver como hoy).
   Un `driver_name` explícito manda siempre.
2. Un único punto: helper en `connection/sqlserver/` usado por los cuatro sitios (hoy duplicados); `pyodbc` importado
   de forma perezosa (pymssql no lo necesita).
3. Log DEBUG con el driver elegido.
4. Tests unitarios con `pyodbc.drivers` simulado (17, 18, 17+18, ninguno, explícito); integración con el banco
   (SQL Server en 51833, ODBC 18 instalado) sin `driver_name`.
5. Docs: `connection_guide.md` § SQL Server, `api/connection_factory.md` si lista el default; CHANGELOG Changed.

### F4 — `jaydebeapi` en el entorno de referencia · esfuerzo S · sin versión

Evidencia: `tests/unit/connection/test_drivers_p2_sqlserver_sqlite_hsqldb_oracle.py:113` se salta sin `jaydebeapi`;
el extra `hsqldb` existe (`pyproject.toml:63`) pero `dev-full` no lo incluye; el CI instala `.[dev-full]`.

1. Decisión D4: añadir `hsqldb` a `dev-full` o dejarlo fuera a propósito (documentarlo).
2. Si se añade: comprobar wheels de `JPype1` para Python 3.12–3.14 en ubuntu y windows; el test solo importa
   `jaydebeapi` (no arranca JVM). Repetir el venv limpio `.[dev-full]` y el CI.

### F5 — Externos y largo plazo · sin trabajo de código ahora

- P7: borrador de issue ORA-03106 para python-oracledb (`.ai/sessions/2026-10-01y-ora03106-repro/ISSUE_DRAFT.md`,
  «no publicado»): lo publica el usuario; antes, comprobar si la versión actual de oracledb lo sigue reproduciendo.
- 6.0.0: retirar `markdown.mkdocs_yml` (en desuso desde 5.6.0).
- Zensical en beta (0.1.x, tope `<0.2`): al subir, igualar el Mermaid local (`ZENSICAL.md` §6).
- Aparcados sin cambio: S-1 (`bulk` con procesos) y las dos limitaciones de driver del roadmap.

### Orden y versiones

| Paso | Fases | Resultado |
|---|---|---|
| 1 | F0 | commit `docs:` en `develop` |
| 2 | F1 | `chore(ci):` en `develop`, CI en verde |
| 3 | F4 (si D4 = sí) | `chore(deps):` en `develop` |
| 4 | F2 + F3 | `feat(doc)` + `feat(connection)` → VERSION **5.7.0** (MINOR) |
| — | F5 | seguimiento; sin commit |

F1 va antes de F2/F3 para que la release 5.7.0 se publique ya con las acciones nuevas.

---

## AUDIT_PLAN

| # | Riesgo | Fase | Mitigación | Severidad |
|---|---|---|---|---|
| R1 | Saltos mayores de acciones: `codecov-action@v7` puede exigir token o cambiar inputs; `upload-artifact@v7` y `softprops@v3` pueden cambiar comportamiento en los workflows de release, que solo corren con tag | F1 | Leer notas de versión antes; `workflow_dispatch` de `docs-zip-release.yml`; el de tag (`docs-release.yml`) se valida en la próxima release y, si falla, se completa a mano (`release_guide` §8) | Media |
| R2 | Conflictos de la PR con los workflows tocados en 5.6.0 | F1 | Rebase de Dependabot o aplicar a mano (opción B) | Baja |
| R3 | `validate_trace_map` crea superficie pública nueva en `util_bbdd.doc` (SemVer: queda congelada) | F2 | Firma mínima, `None` + excepción (como la validación al construir); decisión D1 | Media |
| R4 | Quitar rutas de los mensajes empeora el diagnóstico en local (dos mapas con el mismo nombre en carpetas distintas) | F2 | El nombre basta para quien pasó la ruta; decisión D3 si se prefiere ruta relativa al cwd | Baja |
| R5 | Detección del driver: cambia el comportamiento con ambos drivers instalados (17 → 18) | F3 | `Encrypt`/`TrustServerCertificate` explícitos en la cadena (verificado); integración del banco con ODBC 18; CHANGELOG lo explica; `driver_name` explícito para fijar | Media |
| R6 | `pyodbc.drivers()` en Linux depende de unixODBC (`odbcinst.ini`); en contenedores puede devolver lista vacía | F3 | Fallback a «ODBC Driver 17» (hoy) y test de lista vacía | Baja |
| R7 | `JPype1` sin wheel para 3.14 en algún SO rompe `pip install .[dev-full]` en el CI | F4 | Comprobar PyPI antes; si falta, no añadir y documentar | Media |
| R8 | El venv local oculta dependencias no declaradas (lección de 5.6.0: `certifi`) | F2–F4 | Gate final en venv limpio `.[dev-full]` antes de publicar 5.7.0 | Media |
| R9 | util_bbdd_web en otra sesión a 5.6.0 mientras se prepara 5.7.0 | F2 | 5.7.0 solo añade; G49 se marca en la web cuando adopte 5.7.0 | Baja |

**Criterio de salida por fase**: ruff, `ruff format --check`, mypy (`src` + protocolo), pytest completo sin URLs del
banco, `zensical build --strict`; F3 además con el banco de SQL Server; 5.7.0 además venv limpio `.[dev-full]`,
`python -m build` y wheel probado.

**Rollback**: F0/F1/F4 son commits independientes (`git revert`); F2/F3 sin publicar se revierten por commit; tras
publicar 5.7.0, corrección en 5.7.1 (no se reutiliza una versión publicada).

### Decisiones pendientes del usuario

- **D1 (F2)**: `validate_trace_map(path) -> None` que lanza `DocumentationConfigError` con todos los errores
  (recomendado, coherente con la validación al construir) **o** que devuelva la lista de errores.
- **D2 (F2)**: exponer también `validate_previous(path)` (no lo pide G49) — recomendado: no, de momento.
- **D3 (F2)**: mensajes con el nombre del fichero (recomendado, lo que pide G49) o ruta relativa.
- **D4 (F4)**: añadir `hsqldb` a `dev-full` (recomendado si hay wheels de JPype1 para 3.12–3.14).
- **D5 (F1)**: rebase de Dependabot (A, recomendado) o saltos a mano (B).
- **D6 (F3)**: detección automática del driver ODBC (recomendado) o dejar el 17 y solo documentarlo.

Veredicto AUDIT_PLAN: **GO_CONDICIONAL** — sujeto a D1–D6; F0 se puede ejecutar ya.
