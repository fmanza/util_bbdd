# TRACEABILITY

## Session metadata
- id: 2026-10-26-web-gaps-ola3
- fecha: 2026-10-26
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 3 (v4.3.0)

## Prompt issued
Ola 3 del plan de huecos de util_bbdd_web (migración DDL, util_bbdd 4.3.0): fases U-M1 … U-M5, un commit por fase en
`develop`; solo parámetros opcionales nuevos, sin cambios de valor por defecto; progreso con `util_bbdd.progress` como
`compare()` en 4.2.0. Plan canónico: `docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (solo lectura); PLAN y
AUDIT_PLAN aprobados allí (2026-10-25).

## Context sources
- `src/util_bbdd/migrate/` (planner, `ir/models.py`, transformers, emitters, `_audit_events.py`) en 4.2.0.
- `backend/app/integrations/util_bbdd/migrate.py` de util_bbdd_web (rodeos de G4, G26, G27 y G28) para ajustar la API.
- Patrón de `SchemaDiff.to_dict`/`from_dict` (4.2.0, `8edbf8e`) y de progreso de `compare()` (`60e3c5f`).

## AI output summary
- Un commit por fase (ruff, ruff format, mypy y pytest completo en cada una; AUDIT_CODE tras cada fase):
  - U-M1 `3b06e7dc` G4: `MigrationPlanner.supported_sources()`/`supported_targets()` (tuplas en orden alfabético).
  - U-M2 `c2a5bd31` G28: `transformers/_fk_types.py::align_fk_types` tras `transform()` en `_build_plan`: la FK toma
    el `target_type` de la columna referenciada (cadenas resueltas, ciclos cortados); `FK_TYPE_ALIGNED` (INFO) o
    `FK_TYPE_UNRESOLVED` (ERROR).
  - U-M3 `de9127ba` G26: `MigrationPlan.to_dict()`/`from_dict()`/`statements_sha256()` en `ir/_serialization.py`;
    `MigrationPlanValidationError`.
  - U-M4 `ee5ef17f` G27: `check_target()` → `TargetCheck`; `execute(dry_run=, stop_on_error=)` → `ExecutionResult`;
    `MigrationStatementError` (subclase de `DatabaseOperationError`); `run` de auditoría con `DRY_RUN` y
    `statements_failed`.
  - U-M5 `e8c564e5` G1: `execute(on_progress=, cancel_token=)`, operación `"migrate"`, fase `"statements"`.
- Evidencias: pytest 6559 passed, 595 skipped (`build/logs/U-M5_pytest.txt`); mypy limpio (352 ficheros);
  `zensical build --strict` limpio; `-m integration` con el banco: 637 passed, 8 failed y 6 errores de entorno
  (`asyncpg`/`aioodbc` no instalados en el venv local, HSQLDB sin `JAVA_HOME`), ninguno en `migrate`
  (`build/logs/ola3_integration.txt`). Script de verificación de G28 contra el banco (Oracle `INT` PK + FK → MariaDB,
  MySQL, SQL Server, PostgreSQL: tipo alineado, FK creada, `to_dict`/`from_dict` por JSON, `check_target`, `dry_run`,
  progreso y `MigrationStatementError` al repetir): los 4 OK (`build/logs/ola3_bench_check.txt`).
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (`progress` ya es Foundation); pie de figura a 352 ficheros.
- VERSION: `release: v4.3.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 3 | `src/util_bbdd/migrate/` | completado (v4.3.0) |
| Tests | `tests/unit/migrate/test_fk_type_alignment.py`, `test_plan_serialization.py`, `test_plan_target_check.py`, `test_plan_progress.py` | completado |

## Notas para las fases W-M de util_bbdd_web
- W-M1: `supported_*()` devuelve orden alfabético, no el de la UI actual.
- W-M2: `fk_mismatches` debería quedar vacío con planes nuevos; `FK_TYPE_UNRESOLVED` bloquea ya en util_bbdd.
- W-M3: `from_dict` ya exige el mismo `statements_sha256`; la web debe seguir comparándolo con su hash guardado aparte
  (el hash del diccionario no protege de una manipulación del fichero). `check_target(manager, schema=...)` sustituye a
  `_target_tables` (por defecto usa `pg_schema` con destino PostgreSQL).
- W-M4: `MigrationStatementError.position`/`.statement` sustituyen la lectura de la auditoría en `_record_failure`; el
  `error_type` del `run` de auditoría pasa a `MigrationStatementError`.

## Directrices para Futuras IAs
- **[migrate]**: la alineación de tipos de FK (G28) es un paso común en `migrate/transformers/_fk_types.py`, llamado
  desde `MigrationPlanner._build_plan` justo tras `transformer.transform()`; los transformers no ven la tabla
  referenciada. Las FK externas (`is_external`) o a tablas fuera del plan no se tocan.
- **[migrate]**: `FK_TYPE_ALIGNED` borra `ddl_comment` y los avisos `TYPE` de nivel `WARNING` de la columna (precedente:
  PK `NUMBER` sin precisión → `INTEGER` en `oracle_to_postgresql`); la comparación de tipos ignora el ancho de los
  enteros de MySQL (`INT(11)` == `INT`).
- **[migrate]**: `MigrationPlan.to_dict` guarda las opciones del emitter leyendo sus atributos privados
  (`_EMITTER_OPTIONS` en `ir/_serialization.py`); un parámetro nuevo en un emitter exige añadirlo ahí o `from_dict`
  rechazará los planes (el test de round-trip de los 20 pares lo detecta).
- **[migrate]**: `from_dict` vuelve a emitir y exige el mismo `statements_sha256`: un cambio en un emitter invalida los
  planes guardados con versiones anteriores (es intencionado: se ejecuta lo revisado o se replanifica).
- **[migrate]**: emitir dos veces no duplica avisos (verificado en los 4 destinos de la familia): `to_dict` emite antes
  de leer `warnings` para incluir los que descubre la emisión.
- **[migrate]**: `execute()` con un objeto de solo `execute_custom_one` relanza el error original con `add_note` en vez
  de `MigrationStatementError`, para no cambiar el tipo de excepción de esos consumidores.
- **[migrate]**: `check_target` lee con `metadata_source()` de `extractors/_snapshot.py` (manager o `MetadataSource`) y,
  con un `Engine`, `CatalogSource.from_engine`; invalida antes la caché de `TABLES`/`VIEWS` del schema.
- **[tests]**: `tests/unit/test_exceptions_public_module.py` fija el número de excepciones públicas (43 en 4.3.0);
  `test_planner.py::test_execute_has_no_override_flag` fija la firma de `execute()`.
- **[banco]**: el usuario `bench` de MySQL/MariaDB solo crea bases con prefijo `zz_util_bbdd_` (`zz_um_dst` da 1044);
  los helpers de `tests/integration/test_migrate_views_e2e.py` (`_manager`, `_create_namespace`, `_drop_namespace`,
  `_run`) sirven para verificaciones puntuales.
- **[herramientas]**: los scripts de edición con heredoc de Bash y comillas triples mezcladas fallan
  (`unexpected EOF`); escribirlos con Write en el scratchpad y ejecutarlos con `python <ruta>`.

## Veredicto final
Veredicto: CLOSED (ola 3, v4.3.0)
Pendientes al cierre:
- Push de `develop` y del tag `v4.3.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (propietario).
- Registrar la ola 3 en §6 del plan de util_bbdd_web (desde esa sesión; aquí es solo lectura).
- HSQLDB y async del banco sin verificar en este venv (falta `JAVA_HOME`, `asyncpg`, `aioodbc`): no afectan a `migrate`.
- Olas 4-6 (U-V, U-B, U-T) en sesiones aparte.
