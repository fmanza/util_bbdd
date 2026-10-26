# TRACEABILITY

## Session metadata
- id: 2026-10-25-web-gaps-plan
- fecha: 2026-10-25
- rama: claude/practical-ride-44fot0
- skill: new_feature
- fase: PLAN + AUDIT_PLAN; IMPLEMENT + AUDIT_CODE + VERSION de la ola 1 (v4.1.0)

## Prompt issued
Plan por tipo de ejecución (incluida la carga) para resolver en util_bbdd los huecos de
`docs/plan/UTIL_BBDD_GAPS.md` de util_bbdd_web, con orden de ejecución simultáneo de los dos repositorios, un commit
por fase, AUDIT_PLAN e instrucciones de ejecución.

## Context supplied
- `util_bbdd_web/docs/plan/UTIL_BBDD_GAPS.md` (G1-G41), analizado sobre util_bbdd 4.0.0.
- Este repositorio en 4.0.1: rutas de cada hueco verificadas con `grep` en `src/util_bbdd/`.

## AI output summary
- Plan: resumen de las fases `U-` en `PLAN.md`; plan completo en util_bbdd_web. Decisiones D1-D5 aprobadas.
- Entorno: venv Python 3.12 con `.[dev-full]` + Graphviz 2.43, `libmariadb-dev` y unixODBC. Línea base: 1 fallo
  previo (`test_edge_shapes_match[sin_columnas]`, pandas 3.1.0), registrado en `build/logs/baseline_failures.txt` y
  comparado después de cada fase.
- Ola 1, un commit por fase (ruff, ruff format, mypy, pytest completo sin fallos nuevos y `zensical build --strict`):
  - U-0.1 `fb23060` paquete `progress/` (capa 2) + `OperationCancelledError`; diagrama de capas regenerado.
  - U-0.2 `22aaba0` extras `sqlserver`, `sqlserver-odbc`, `hsqldb`, `sqlite-async`.
  - U-D1 `d8aeaf9` G2: la clave del caché de nombres lleva motor, host, puerto y BD. **Cambio de alcance**: la
    agrupación entre instancias es una función documentada; no se pasó a estado por instancia.
  - U-D2 `6c68c69` G39: `graphviz.CalledProcessError` → `RuntimeError` en `_pipe_graph_bytes`.
  - U-D3 `0b09bee` G39: `grafo.orthogonal_edges` (el parámetro ya existía en `GraphvizRelationshipGraphExt`).
  - U-D4 `532521c` G41: `WordTemplateValidator` en `settings()`.
  - U-D5 `776c749` G38: clave `"isolated"` en `pipe_level_graphs_ext` y grupo «Sin relaciones» en el HTML.
  - U-D6 `6a543fa` G21: `schema` opcional en `conn_params` de Oracle (owner de metadatos, no va al driver).
  - U-D7 `c81d291` G22: `schema` explícito en documentación y grafos; `get_ddl`/`get_columns_charset_collation`
    con `schema=None`.
  - U-D8 `1e0588f` G40: `plantilla_excel` (`ExcelTemplate`) y `table_style_excel`.
  - U-D9 `6ae2637` G1: progreso y cancelación en la documentación (`TableProgress` en los tres renderers).
  - U-G1 `eb14fb1` G1: progreso y cancelación en `generate_all_tables_graphs_ext`.
- VERSION: `release: v4.1.0` (este commit). Sin tag ni wheel: los publica el propietario tras el merge.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Resumen de fases `U-` | `.ai/sessions/2026-10-25-web-gaps-plan/PLAN.md` | emitido |
| Ola 1 | `src/util_bbdd/progress/`, `doc/`, `analysis/`, `connection/config.py`, `managers/` | completado (v4.1.0) |

## Directrices para Futuras IAs
- **[web]**: util_bbdd_web consume este paquete por el wheel adjunto a la release de GitHub (URL + hash en su
  `uv.lock`); una release sin wheel bloquea a la web.
- **[semver]**: G30 (`DumpConfig.truncate_target`, `dump/_models.py`) y G35 (`generar_sql`, `bulk/crud.py`) son
  cambios de valor por defecto: en 4.x solo `FutureWarning`.
- **[progreso]**: el contrato de progreso y cancelación (G1) es un paquete público nuevo `progress/` en la capa 2
  (`LAYER` de `scripts/gen_arquitectura_capas.py`): solo importa `_core` y lo usan las capas 6 y 7 (D1 aprobada).
- **[seguridad]**: G11 (`get_database_info` con contraseña) se publica en MINOR como `security:` (D2).
- **[progreso]**: `OperationCancelledError` hereda de `DatabaseException`; en bucles con `except DatabaseException`
  (p. ej. `_generate_all_tables_batch`) la cancelación se comprueba fuera del `try` o se guardaría como error.
- **[doc]**: el `ProgressReporter` viaja en `DocumentationSession.progress`; los renderers lo leen con
  `TableProgress.of(data_provider, ...)`, que no hace nada si el `data_provider` no lo trae (dobles de test).
- **[doc]**: los checks de plantilla (`WordTemplateValidator.check`, `ExcelTemplate.check`) se inyectan en
  `DocumentationBootstrap` (capa de aplicación sin python-docx ni openpyxl).
- **[doc]**: `DocumentationSourcePort` (interno) amplía `get_ddl`/`get_columns_charset_collation` con `schema`; no
  se amplía `DocumentationCatalogPort`/`MetadataReaderPort`, que también cumple `DocumentationSession`.
- **[analysis]**: `graphviz.CalledProcessError` no es `OSError` ni `RuntimeError`; la conversión vive en
  `GraphvizRelationshipGraphExt._pipe_graph_bytes`, punto común de Word, HTML y los `generate_*`.
- **[metadata]**: `get_schema_metadata(schema, kinds=frozenset())` normaliza el nombre con el dialecto sin consultar.

## Veredicto final
Veredicto: GO (ola 1, v4.1.0)
Pendientes al cierre:
- Merge a `develop`/`main`, tag `v4.1.0` y wheel + `.sha256` en GitHub Releases (los hace el propietario).
- G21 sin verificar contra un Oracle real (no hay bench en esta sesión): ejecutar `pytest -m integration` con Oracle.
- Fallo previo de pandas 3.1.0 (`test_edge_shapes_match[sin_columnas]`): fuera del alcance, tarea aparte.
- Olas 2-6 en sesiones aparte (plan canónico en util_bbdd_web).
