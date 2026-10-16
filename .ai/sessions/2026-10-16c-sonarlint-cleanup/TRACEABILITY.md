# TRACEABILITY

## Session metadata
- id: 2026-10-16c-sonarlint-cleanup
- fecha: 2026-10-16
- rama: develop (base `18962584`, tras v2.2.1)
- skill: correcciones aviso a aviso (Pylance + SonarLint) + version_closure v2.2.2
- fase: IMPLEMENT por aviso + VERSION

## Prompt issued
Avisos de Pylance y SonarLint pegados uno a uno desde el IDE (sin texto propio salvo la selección del editor), y al
final «/version-closure con el contenido de esta sesión».

## Context supplied
- Los diagnósticos del IDE (regla, fichero, línea) y la línea seleccionada en el editor.
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md` y la memoria del proyecto (español, no `git add -A`, puerta sin URLs
  del banco, heredocs que pierden barras invertidas).

## AI output summary
- **analysis**: `_render_batch` comprueba `graphviz is None` (Pylance `reportOptionalMemberAccess`).
- **bulk**: `_fits`/`_column_fits` divididos por tipo (S3776); `TableMaintenance.scope` restaura en `finally` con
  `failed` (S9152); `_readiness_blocks` devuelve `list` (S8495); `bulk_session()` marcado `# NOSONAR` con el motivo
  (S9152 falso positivo: tras el `yield` está el commit, no limpieza).
- **comparar**: `_DIALECT_FACTORY: dict[str, type[DefaultDialect]]` (Pylance); vistas modificadas sin `append`
  consecutivos (S9409).
- **connection**: `_ = conn_params` en el `check_dynamic` de MariaDB (S1172; lo exige el Protocol); `connect` y
  `__create_pool` de MariaDB divididos (S3776) y `_MARIADB_MISSING_MSG` (S1192); `logger.exception` en los 14
  `except Exception` de conexión (S8572); `if x is None: pass` invertido en 4 validadores (S108); `check_dynamic` de
  Oracle con `_threshold_finding` (S3776); `\w` + `re.ASCII` en `config.py` (S6353); `if/elif` de `ssl_verify_cert`
  (S3358).
- **factory**: `_build_connection_string` en los dos `create_engine` y `_builtin_async_builder` en
  `create_async_pool` (S3776).
- **metadata**: constantes `_TC_TABLE_NAME`, `_CON_TABLE_NAME`, `_T_NAME`, `_NO_ACTION` (S1192); `_parse_columns` de
  HSQLDB/MariaDB, `_data_type` de Oracle, `_determine_state`, `to_driver`, `_mssql_build_indexes`,
  `_mssql_column_type`, `_mssql_build_columns` divididos (S3776).
- **migrate**: `_MYSQL_TIMESTAMP_FUNCTIONS` y `_MYSQL_PATH_TEXT` (S1192); `_PG_CAST_TYPE_RE` + `_strip_pg_cast`
  (S5843 y S8786); `_emitted_warnings`, `oracle_rownum_limit`, `_connect_by_hierarchy`, `_apply_names` y
  `_transpile_view` divididos (S3776); `_nodes()` en lugar de 20 `list(tree.find_all(...))` (S7504); `\w` +
  `re.ASCII` en `charset.py` y `transpiler.py` (S6353); `if/elif` del estado de `view_validation` (S3358).
- Errores propios detectados antes del cierre y corregidos: un script convirtió un `elif pool_size > 20` en `if`
  (PostgreSQL daba WARNING y OK) → test nuevo; `importlib` en `PoolFactory` ocultaba 6 imports al diagrama de capas
  (×17 → ×11) → imports estáticos; `_transpile_view` capturaba el `KeyError` de un destino sin dialecto (181
  diferencias en la comparación) → búsqueda al principio otra vez.
- `/version-closure` v2.2.2: CHANGELOG, `pyproject.toml`, `README.md` (2), `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md` (337 ficheros), `CURRENT_STATE`, `SESSIONS_DIGEST`, `INDEX`.

## Tests and evidence
- Puerta final (`build/logs/v2.2.2_gate.txt`, `build/logs/v2.2.2_final.txt`): `ruff check` y `ruff format --check`
  sobre `src tests` (709 ficheros), `mypy src tests/unit/test_protocol_conformance.py` sin errores (337),
  `pytest` sin URLs del banco **6085 passed, 532 skipped**, `zensical build --strict` sin avisos, `python -m build`
  (sdist y wheel 2.2.2).
- Comparación antes/después de `migrate/views` (scripts en el scratchpad de la sesión, no versionados): 66 vistas
  `CONNECT BY` × 6 destinos (396 casos) y 181 vistas × 6 destinos (1086 casos), mismo SQL y mismos avisos.
- Fuzz de `_strip_pg_cast` frente a la regex anterior: 200 000 entradas, 0 diferencias.
- `scripts/gen_arquitectura_capas.py`: el dibujo coincide con el código (337 ficheros, `factory → connection` ×17).
- Suite con el banco y los 6 motores (SQL Server en 51833, `JAVA_HOME` para HSQLDB; `build/logs/v2.2.2_bench.txt`):
  **6609 passed, 8 skipped** (v2.2.1: 6602), incluidos los e2e de `tests/integration/test_migrate_views_e2e.py`.
- `/audit-code` de los cambios de la sesión: APROBADO (sin hallazgos bloqueantes; ver el resumen de la sesión).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Código | 43 ficheros de `src/util_bbdd/` (ver `git status`) | sin commit |
| Test | `tests/unit/connection/test_advisor_characterization.py::test_pool_size_gives_exactly_one_finding` | sin commit |
| Logs | `build/logs/sonar_fixes_pytest.txt`, `build/logs/v2.2.2_gate.txt`, `build/logs/v2.2.2_final.txt` | generados |

## Known limitations
- Solo se corrigieron los avisos que se pegaron; SonarLint puede marcar otros en los mismos ficheros (p. ej.
  `"CURRENT_TIMESTAMP"` 5 veces en `default_normalizer.py`; `_rejected_optional_param` casi duplicado en
  `connection_mariadb.py` y `pool_connection_mariadb.py`).
- Ningún test fija el `KeyError` de `transpile_view` con un destino sin dialecto (se conservó, no se decidió si es
  deliberado).

## Rollback
- Sin tag todavía: `git revert` de los commits de la sesión (o `git checkout -- <ruta>` antes de confirmar). Riesgo
  bajo: sin cambios de API; revertir devuelve los logs de conexión sin traceback y la regex anterior del cast.

## Directrices para Futuras IAs
- **[sonarlint]**: S9152 («cleanup after yield») es falso positivo cuando tras el `yield` va el commit del camino feliz
  (`BulkCrud.bulk_session`): moverlo a `finally` confirmaría tras un error; se marca `# NOSONAR` con el motivo.
- **[sonarlint]**: S7504 sobre `list(tree.find_all(...))` en `migrate/views/_rewrites.py` es falso positivo: las
  reescrituras hacen `replace` durante el recorrido; usar `_nodes(tree, *tipos)` (genérica, conserva el tipo).
- **[sonarlint]**: S6353 (`\w` por `[A-Za-z0-9_]`) solo es equivalente con `re.ASCII`: sin él `\w` admite letras
  Unicode y relaja validaciones (charset de MariaDB, identificadores sin comillas).
- **[factory]**: los imports diferidos de `PoolFactory._builtin_async_builder` deben ser estáticos (`from … import`):
  con `importlib` desaparecen del diagrama de capas (`scripts/gen_arquitectura_capas.py`), de mypy y del IDE.
- **[migrate/views]**: para refactorizar `_rewrites.py`/`transpiler.py` sin cambiar la salida, comparar
  `transpile_view` antes/después con todas las cadenas `SELECT`/`WITH` de `tests/unit/migrate/test_view*.py`,
  `test_views_*.py` y `tests/integration/test_migrate_views_e2e.py` en los 6 destinos (incluido uno sin dialecto).
- **[migrate/views]**: `_transpile_view` resuelve `SQLGLOT_DIALECT[ctx.target_engine]` antes del primer `try`: dentro
  de un `except Exception` un destino sin dialecto pasaría a pass-through en lugar de `KeyError`.
- **[connection]**: `check_dynamic(connection, conn_params)` es contrato de `ReadinessValidator`
  (`connection/_advisory.py`); en los motores que no usan `conn_params` se escribe `_ = conn_params`.
- **[herramientas]**: los ficheros de `src/` mezclan LF y CRLF: los scripts de edición deben detectar `\r\n` y
  normalizar antes de buscar; `\w+` no casa con `Clase.logger` (el punto) al buscar llamadas a métodos.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno de la versión: commits, tag `v2.2.2` y push de `develop`/`main` hechos tras `/audit-code`.
