# PLAN + AUDIT_PLAN — filtro de tablas en la migración DDL y el volcado

- Fecha: 2026-11-16 · Rama: `develop` (= `v5.8.0` + `8ad00ee6`) · Flujo: `/new-feature` (MINOR) · Repos: util_bbdd y
  util_bbdd_web
- Petición: «Lanzar ejecución: Documentación de la base de datos» de la web tiene el «Filtro de tablas»; se quiere lo
  mismo en «Plan de migración DDL» y en «Volcado de datos: vista previa». PLAN y AUDIT_PLAN por fases, en los dos repos.
- Decisiones del usuario: **D1** las rutinas no se filtran (como en la documentación). **D2** en la vista previa del
  volcado se mantiene la lista exacta `tables` (avisa si una tabla no existe) y es incompatible con los patrones.

---

## Evidencia (verificada)

- `TableFilter` (5.5.0) vivía en `doc/domain/table_filter.py`: *glob* con `fnmatchcase` sobre `casefold`, `excluir`
  gana a `incluir`, frontera por FK. Lo usa solo `doc` (tablas y vistas; las rutinas no se filtran).
- Capas (`scripts/gen_arquitectura_capas.py`): `doc` y `dump` en la 7, `migrate` en la 6, `metadata` en la 5.
  `migrate`/`dump` no pueden importar de `doc` (Regla #6).
- `MigrationPlanner.plan(connection, schema)` no filtra; los cinco pipelines terminan en `_build_plan`.
- Las FK «externas» (`CanonicalFK.is_external`) ya se emiten con `ALTER TABLE` al final en los cinco emitters y
  `align_fk_types` las ignora: es el camino para las FK hacia tablas filtradas.
- `_transform_views` construye el contexto de reescritura con `zip(raw_tables, transformed)`: filtrar las tablas
  antes cambiaría la reescritura de las vistas que leen tablas de fuera. `transform`/`transform_views` son 1:1.
- `CanonicalView` no guarda sus dependencias: el aviso «vista que lee una tabla filtrada» no se puede calcular; lo
  cubre `validate_views` (modo seco).
- `MigrationPlan.from_dict` (`_serialization.load_plan`) construye el plan campo a campo: las claves nuevas son
  opcionales con `data.get`; `CanonicalFK` se carga con `_load`, que admite campos con valor por defecto ausentes.
- `DumpConfig.tables` es una lista exacta; `_get_source_tables` es el único punto de selección (lo usan `plan()` y
  `run()`); `OUTSIDE_REFERENCES` ya avisa de las FK hacia tablas que no se vuelcan.
- Web: `run_dump` recalcula la vista previa y exige el mismo `structure_hash` (incluye las tablas): volver a resolver
  los patrones al volcar es seguro.

---

## PLAN

### util_bbdd 5.9.0

| Fase | Contenido |
|---|---|
| U-1 | `TableFilter` a `metadata/table_filter.py` (público en `util_bbdd.metadata`), `from_patterns()` validado; `doc/domain/table_filter.py` reexporta |
| U-2 | `MigrationPlanner.plan(..., *, table_filter=None)`: filtro en `_build_plan` tras transformar todo; FK hacia fuera → `outside_filter` + `is_external` + aviso `FK_OUTSIDE_FILTER`; `MigrationPlan.table_filter`/`frontier` serializados como claves opcionales; sin coincidencias → `ValueError` |
| U-3 | `DumpConfig.table_filter` (incompatible con `tables`), resuelto en `_get_source_tables`; sin coincidencias → `DumpError` |
| U-4 | Tests, guías (`ddl_migration_guide`, `dump_guide`), API (`dump.md`, `metadata_autodoc.md`), CHANGELOG |

### util_bbdd_web 1.19.0 (tras publicar 5.9.0)

| Fase | Contenido |
|---|---|
| W-0 | Wheel 5.9.0 + `uvx uv@0.12.22 lock`; G56/G57 en `UTIL_BBDD_GAPS.md` |
| W-1 | `table_include`/`table_exclude` (grupo `filter`) en `MigratePlanParams` y `DumpPreviewParams`, validador común con `DocumentationParams`; `tables` + patrones → error |
| W-2 | `PlannerOptions`/`DumpOptions` con el filtro; `plan_to_dict` con `filter` y `frontier`; error claro sin coincidencias |
| W-3 | `PatternPreview` en las tres operaciones (solo tablas en `dump_preview`); filtro y frontera en `PlanViewer`/`DumpPreviewViewer` |
| W-4 | Tests backend y frontend |
| W-5 | `features.json`, guía, CHANGELOG, ROADMAP, release 1.19.0 |

---

## AUDIT_PLAN

- Funcionales: FK hacia fuera diferida (no omitida); vistas que leen tablas de fuera → modo seco; rutinas sin filtrar
  (D1); `structure_hash` protege el volcado.
- Técnicos: sin imports nuevos entre paquetes (el diagrama no cambia); `plan()` con argumento keyword-only; claves
  opcionales sin subir `format_version`; sin filtro, mismas sentencias y hash.
- Seguridad: los patrones no llegan al SQL (`fnmatchcase` en memoria); límites 100 × 128 sin caracteres de control.
- Veredicto: **GO_CONDICIONAL** → condiciones D1 y D2 resueltas por el usuario; aprobado IMPLEMENT.
