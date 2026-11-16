# TRACEABILITY

## Session metadata
- id: 2026-11-16-filtro-tablas-migrate-dump
- fecha: 2026-11-16
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (util_bbdd); IMPLEMENT de util_bbdd_web 1.19.0 en
  local, pendiente de W-0 (subir a 5.9.0 tras publicarla)

## Prompt issued
«Lanzar Ejecución: Documentación de la base de datos dispone del Filtro de tablas; lo queremos en Volcado de datos:
Plan de Migración DDL y en Volcado de datos: vista previa. PLAN y AUDIT_PLAN por fases para util_bbdd y
util_bbdd_web» → «D1 igual que en la documentación. D2 se mantiene la lista exacta, incompatible con los patrones.
implement».

## Context supplied
- util_bbdd: `doc/domain/table_filter.py`, `migrate/planner.py`, `migrate/ir/{models,_serialization}.py`, emitters,
  `transformers/_base_transformer.py`, `dump/{_models,orchestrator}.py`, `scripts/gen_arquitectura_capas.py`.
- util_bbdd_web: `domain/runs/operations.py`, `integrations/util_bbdd/{migrate,dump,documentation}.py`, jobs,
  `LaunchRunModal.tsx`, `PatternPreview.tsx`, `tablePatterns.ts`, visores del plan y de la vista previa.

## AI output summary
- PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`): GO_CONDICIONAL con D1 (rutinas sin filtrar) y D2 (lista exacta del
  volcado incompatible con patrones), resueltas por el usuario.
- `aa1bfa13` (feat): `TableFilter` público en `util_bbdd.metadata` (+ `from_patterns`); `MigrationPlanner.plan(...,
  *, table_filter=None)` con `FK_OUTSIDE_FILTER`, `CanonicalFK.outside_filter`, `MigrationPlan.table_filter`/
  `frontier` (claves opcionales de `to_dict`); `DumpConfig.table_filter`. Guías y API.
- Web (sin commit hasta W-0, probada con `PYTHONPATH` al `src` local): parámetros `table_include`/`table_exclude` en
  `migrate_plan` y `dump_preview`, `PatternPreview` por operación (contexto i18next), `TableFilterSummary` en los
  visores, OpenAPI y tipos regenerados, guías, GAPS G56/G57 y CHANGELOG.
- VERSION 5.9.0: versión, pines `@v5.9.0`, CHANGELOG, estado e índices.

## Pruebas
- util_bbdd: pytest local 7193 passed, 619 skipped (shell sin URLs del banco); ruff, `ruff format`, mypy (376)
  limpios; `zensical build --strict` limpio; diagrama de capas sin cambios. Integración con motores reales **no
  ejecutada**: los contenedores del banco estaban parados.
- util_bbdd_web contra util_bbdd local: backend 814 passed, 2 skipped (`not integration`), ruff/mypy/OpenAPI limpios;
  frontend 215 tests, lint, typecheck, prettier y build limpios; `zensical build --strict` limpio. Un fallo
  intermitente ajeno (`test_previous_documentation_is_checked_on_launch`: `UnsafePathError` con dos jobs a la vez en
  Windows) pasó al repetirlo.

## Directrices para Futuras IAs
- **[metadata]**: `TableFilter` vive en `metadata/table_filter.py` (capa 5) para que lo usen `doc`, `migrate` y
  `dump`; `doc/domain/table_filter.py` solo reexporta. Construir con `from_patterns`/`from_config` (el constructor no
  valida).
- **[migrate]**: el filtro se aplica en `_build_plan` **después** de transformar todas las tablas y vistas
  (`_FilterSelection`): la reescritura de vistas necesita los nombres de todo el schema. Las FK hacia tablas de fuera
  se marcan `outside_filter` en las tablas crudas y el transformer las convierte en `is_external` (ALTER al final).
- **[migrate]**: `CanonicalView` no conoce sus dependencias; una vista que lea una tabla filtrada solo se detecta con
  `validate_views` (modo seco).
- **[dump]**: `table_filter` se resuelve en `_get_source_tables` (único punto de selección de `plan()` y `run()`).
- **[web]**: el volcado vuelve a resolver los patrones al ejecutar; `structure_hash` (que incluye las tablas)
  bloquea si cambió el conjunto. La web comprueba antes de `plan()` que algún patrón casa (`NoMatchingTablesError`).
- **[herramientas]**: en Windows, `Path.write_text` escribe CRLF; en util_bbdd_web (`eol=lf`) prettier lo marca.
  Escribir con `write_bytes` o pasar el formateador. `grep -c $'\r'` en Git Bash no cuenta CR: usar
  `git ls-files --eol`.

## Veredicto final
Veredicto: CLOSED (util_bbdd) — v5.9.0 (commit y tag anotado `v5.9.0` en local).
Pendientes al cierre:
- Publicar util_bbdd 5.9.0 (push de `develop` y del tag, ff de `main`, release con wheel y `.sha256`).
- util_bbdd_web W-0: wheel 5.9.0 en `backend/pyproject.toml` + `uvx uv@0.12.22 lock`, tests sin `PYTHONPATH`,
  commit y release 1.19.0.
- Integración con el banco (migración filtrada aplicada en motores reales) cuando esté levantado.
