# TRACEABILITY

## Session metadata
- id: 2026-09-21-regla6-ciclo-connection-factory
- fecha: 2026-09-21 (continúa el 2026-09-22)
- rama: develop
- skill: audit_code + refactor + new_feature
- fase: AUDIT_CODE → IMPLEMENT (condición 1) → IMPLEMENT (condiciones 2 y 3) → PLAN + AUDIT_PLAN (capas estrictas) → PLAN + AUDIT_PLAN (`UpdateAutoIncrement`) → IMPLEMENT + AUDIT_CODE + VERSION (commit `92e6c7c`) → actualización de `.ai/sessions`

## Prompt issued
> `/audit-code`: connection/ y factory/ se importan mutuamente. factory/ importa de connection/ en 12 puntos (2 de módulo, 10 perezosos). En sentido contrario, un único import, `connection/mariadb/update_auto_increment.py:11`, cierra el ciclo. Hoy `import util_bbdd`, `util_bbdd.factory` y `util_bbdd.connection` resuelven sin error, así que el ciclo está latente. La Regla #6 prohíbe ciclos dentro de un nivel.

Las instrucciones posteriores del usuario están numeradas en `00_REQUEST.md`.

## Context supplied
- `CLAUDE.md` (instrucciones del proyecto) y el índice de memoria del usuario (nota sobre `doc_ia`).
- Estado de git de arranque: `docs/architecture.md`, `mkdocs.yml`, `docs/assets/…` y `scripts/gen_arquitectura_capas.py` sin commitear.
- Lo demás se leyó durante la sesión; ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- **AUDIT_CODE.** Confirmó las cifras: 12 aristas `factory→connection` (2 de módulo en `factory/__init__.py:4` y `pool_factory.py:15`, 10 perezosas) y 1 `connection→factory` (`update_auto_increment.py:11`). Grafo AST de 338 ficheros: SCC de paquetes {connection, factory} y ninguna SCC de módulos. Imports OK en 4 órdenes reales y en 7 primeros imports con la raíz `util_bbdd` sin inicializar ⇒ ciclo latente, no solo enmascarado por el orden del `__init__`. Veredicto APROBADO CON CONDICIONES.
- **Hallazgos del fichero.** `sys.exit(1)` en el constructor, SQL con f-strings y sin entrecomillar, un `ALTER` por cada columna de PK compuesta, `ValueError` con PK no numérica, SQL de introspección fuera de `metadata/` (Reglas #1/#3) y ninguna referencia en el repo.
- **Condición 1 (opción A).** Retiró `update_auto_increment.py`; actualizó `gen_arquitectura_capas.py` (flecha, etiquetas, marcas renumeradas 1-2, CSS), figura, guía y CHANGELOG. Corrigió su propia afirmación de que `PKSequenceSyncer` «hacía lo mismo»: ese **ejecuta**, `salida_sql()` solo devolvía sentencias.
- **Condiciones 2 y 3.** Adoptó los niveles de `.ai/architecture.md` y la regla «imports acíclicos dentro de un nivel»; actualizó `architecture.instructions.md`, `.ai/architecture.md`, README, onboarding, `docs/architecture.md` y DECISIONS_LOG; creó `tests/unit/test_architecture_import_rules.py` (7 tests). Comprobó la guarda por mutación: falla al reintroducir `connection→factory` y `query→managers`.
- **Consulta de dirección.** Midió tres esquemas de capas (17, 11 y 0 imports horizontales) y recomendó capas estrictas por función. Corrigió su frase «sin ganar nada» sobre prohibir lo horizontal.
- **PLAN + AUDIT_PLAN pasos 1-3.** Persistido en `01_PLAN_capas_estrictas.md`. GO_CONDICIONAL.
- **Commit base interrumpido** por el usuario. Nuevo PLAN + AUDIT_PLAN de `UpdateAutoIncrement` (A: `Engine` + Inspector en `connection/mariadb/`; B: proveedor; C: modo «solo emitir» en `PKSequenceSyncer`). Recomendada A. Decisiones del usuario: firma `Engine`, Inspector, MariaDB de pruebas disponible, reescribir antes del commit base.
- **IMPLEMENT.** Reescribió `update_auto_increment.py` en su ruta (`Engine` por parámetro, Inspector de SQLAlchemy, `SELECT MAX` con Core, identificadores con backticks, `DatabaseOperationError`/`InvalidDatabaseType`, sin `sys.exit`, sin pandas); export perezoso en `connection/mariadb/__init__.py`; 23 tests unitarios; test de integración `tests/integration/test_update_auto_increment_mariadb.py` (3 pruebas, base temporal `zz_util_bbdd_autoinc_<id>`, se saltan sin `UTIL_BBDD_TEST_MARIADB_URL`); página de API, ejemplo ejecutable, `mkdocs.yml`, CHANGELOG y DECISIONS_LOG.
- **Verificación real.** El usuario ejecutó el test de integración contra su MariaDB: 3 passed (`BIGINT UNSIGNED` > 2⁶³, vistas, nombres con palabra reservada y con backtick, PK compuesta, parámetro `schema`, y contador 101 → 42 tras ejecutar el script).
- **Aviso añadido.** Documentó que el reajuste a `MAX+1` puede bajar contadores y reasignar ids de filas borradas.
- **Validación previa al commit.** `pytest` 3856 passed / 4 skipped; `ruff check` limpio; `mypy src` solo con los 2 errores previos; `mkdocs build --strict` con los mismos 13 warnings previos; script del diagrama coherente (338 ficheros).
- **Commit** `92e6c7c` `refactor(connection)!: reescribir UpdateAutoIncrement sin importar factory`: 20 ficheros, +1055/−177. Local, sin push.
- **Esta actualización** de `.ai/sessions`: carpeta de sesión, fila en `INDEX.md` y en `SESSIONS_DIGEST.md`. Sin commit.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE | conversación (sin fichero propio) | emitido |
| IMPLEMENT (módulo) | `src/util_bbdd/connection/mariadb/update_auto_increment.py`, `__init__.py` | commiteado (`92e6c7c`) |
| Guarda de arquitectura | `tests/unit/test_architecture_import_rules.py` | commiteado (`92e6c7c`) |
| Tests `UpdateAutoIncrement` | `tests/unit/connection/mariadb/test_update_auto_increment.py`, `tests/integration/test_update_auto_increment_mariadb.py` | commiteado (`92e6c7c`) |
| Regla #6 reconciliada | `.github/instructions/architecture.instructions.md`, `.ai/architecture.md`, `README.md`, `docs/guides/onboarding_dev.md`, `docs/architecture.md`, `.ai/DECISIONS_LOG.md` | commiteado (`92e6c7c`) |
| Diagrama | `scripts/gen_arquitectura_capas.py`, `docs/assets/…`, `docs/guides/architecture_diagram_guide.md` | commiteado (`92e6c7c`) |
| Documentación de la utilidad | `docs/api/update-auto-increment.md`, `docs/examples/update-auto-increment-example.{md,py}`, `mkdocs.yml`, `CHANGELOG.md` | commiteado (`92e6c7c`) |
| PLAN + AUDIT_PLAN capas estrictas | `.ai/sessions/2026-09-21-regla6-ciclo-connection-factory/01_PLAN_capas_estrictas.md` | emitido, sin IMPLEMENT |
| REQUEST / CONTEXT / TRACEABILITY | `.ai/sessions/2026-09-21-regla6-ciclo-connection-factory/` | emitido, sin commitear |

## Directrices para Futuras IAs
- **[arquitectura/niveles]**: los niveles canónicos son los de `.ai/architecture.md` (`connection`, `factory`, `query`, `executors`, `metadata`, `results`, `validators` = N2; `managers`, `bulk`, `dump`, `comparar`, `migrate`, `analysis`, `doc` = N3; `_core`, `_drivers`, `core`, `models.py`, `async_utils.py` = N1). La tabla ejecutable es `LEVEL` en `scripts/gen_arquitectura_capas.py`. `models.py` y `async_utils.py` no importan nada de la librería.
- **[Regla #6]**: un paquete importa de su nivel o inferiores; dentro de un nivel, solo en un sentido (sin ciclos); un import perezoso cuenta igual que uno de módulo. Hay 11 pares horizontales acíclicos en el código (p. ej. `factory→connection`, `metadata→results`, `executors→query`). La guarda es `tests/unit/test_architecture_import_rules.py` y reutiliza `measure()`, `LEVEL`, `EXCLUDED` y `top_level_names()` del script: no renombrarlos.
- **[connection/factory]**: `factory/` importa de `connection/` en 12 puntos (2 de módulo, 10 perezosos por los drivers opcionales); `connection/` no debe importar de `factory/`. El nombre «factory» designa dos cosas: el paquete `util_bbdd/factory/` y el módulo `connection/factory.py` (`ConnectionFactory`).
- **[UpdateAutoIncrement]**: recibe un `Engine` (mysql/mariadb); pasar un `dict` lanza `TypeError`. No restaurar la versión anterior (`conf` + `SQLAlchemyEngineFactory`). Solo **genera** sentencias; quien las ejecuta es `BulkCrud.sync_pk_sequences()` (`PKSequenceSyncer`). Descubre columnas `AUTO_INCREMENT` con el Inspector de SQLAlchemy (su reflexión marca `autoincrement`: `sqlalchemy/dialects/mysql/reflection.py:325-328`), una excepción a la Regla #2 documentada en el módulo, como `comparar/`.
- **[UpdateAutoIncrement/semántica]**: `MAX+1` puede **bajar** contadores (verificado en un MariaDB real: 101 → 42); los ids de filas borradas pueden reasignarse. La decisión de retirar el módulo (opción A) se implementó y luego se descartó por decisión del usuario: la utilidad debe existir como utilidad MariaDB propia; no volver a proponer eliminarla.
- **[tests/integración MariaDB]**: `tests/integration/test_update_auto_increment_mariadb.py` necesita `UTIL_BBDD_TEST_MARIADB_URL` (URL de SQLAlchemy con permiso `CREATE`/`DROP`; crea y borra `zz_util_bbdd_autoinc_<id>`). El `docker-compose.yml` solo trae Postgres. Los escenarios `float_auto`, `sequence` y `versioned` son condicionales a lo que admita el servidor y la salida no dice cuáles se ejercitaron; la versión de MariaDB del usuario no se registró.
- **[metadata]**: `NormalizedColumnRow` (`metadata/normalizer.py:17`) solo tiene `name`, `data_type` y `raw`; el dato `EXTRA` (auto_increment) viaja en la fila cruda. `SyncMetadataProvider` cubre 9 lecturas y sus parámetros se llaman `tabla`, incompatibles con los posicionales del adaptador de `doc`.
- **[analysis/doc → managers]**: `analysis/` (3 ficheros) y `doc/` (2) importan `SyncDatabaseManager` solo para anotar. `doc` ya pasa a `analysis` su adaptador (`DocumentationManagerPort`) con un `cast` en `documentation_orchestrator.py:558`, y ese puerto no declara `relationship_cache`. `DbManagerProtocol` aparece solo en docstrings de `metadata/`; no está definido. `SyncMetadataProvider` no basta para sustituir el manager.
- **[dump/bulk]**: la decisión del 2026-05-25 (DECISIONS_LOG) afirma que `dump/` no depende de `BulkCrud`, pero `dump/orchestrator.py` lo importa (l. 38) y lo instancia (l. 154 y 672). La decisión del 2026-09-21 sustituye su parte «Nivel 3 → Nivel 3 prohibido».
- **[.ai/architecture.md]**: indica `from util_bbdd.bulk import … PKSequenceSyncer`, pero `bulk/__init__.py` no lo exporta (ruta real `bulk/_support/pk_sync.py`; API pública `BulkCrud.sync_pk_sequences()`).
- **[calidad/baseline]**: `mypy src` da 2 errores previos en `docs_build_plugin.py:25,27` (el paso de CI ya está en rojo); `mkdocs build --strict` aborta con 13 warnings previos (faltan `installation.md` y `roadmap.md`). Comparar contra ese baseline, no contra cero. `ruff format --check` señala 5 ficheros previos de `bulk/` y sus tests.
- **[docs .ai/CURRENT_STATE]**: `.ai/CURRENT_STATE.md` está generado a 2026-06-05 (3826 tests, PR #18, `mypy` 336 ficheros) y no refleja esta sesión; no se actualizó porque la petición se limitó a `.ai/sessions`.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- IMPLEMENT de los pasos 1, 2 y 3 de capas estrictas (`01_PLAN_capas_estrictas.md`). Antes hay que cerrar tres decisiones: confirmar la tabla de capas (capa 6), si `DocumentationManagerPort` gana `relationship_cache`, y si mypy verifica el fichero de conformidad en CI.
- El commit `92e6c7c` es local: pendiente de push o PR.
- Esta actualización de `.ai/sessions` está sin commitear.
- Opcional: convertir los escenarios opcionales del test de integración en tests con `skip` explícito, y registrar la versión de MariaDB del servidor de pruebas.
- Opcional: actualizar `.ai/CURRENT_STATE.md`.
