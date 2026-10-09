# TRACEABILITY

## Session metadata
- id: 2026-10-09i-hotfix-init-command
- fecha: 2026-10-09
- rama: develop
- skill: audit-code → hotfix
- fase: AUDIT_CODE (traceback de `pruebas_util`) + PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION

## Prompt issued
```text
/audit-code
mariadb.ProgrammingError: You have an error in your SQL syntax; ... near 'SET NAMES utf8mb4' at line 1
→ DatabaseConfigurationError: Error al inicializar SyncDatabaseManager: ... (Operación: mariadb) (BD: You have an error ...)
(pruebas_util/src/doc_bbdd/pruebas.py → SyncDatabaseManager(db_type="mariadb", use_pool=True))

/hotfix
F1 DatabaseConfigurationError con argumentos posicionales; F2 init_command con varias sentencias sin validar;
F3 guía de conexión § 6; corregir el TOML de pruebas_util.
```
Usuario: «continua» tras el veredicto APROBADO CON CONDICIONES.

## Context supplied
- `C:\Desarrollo\Proyectos\pruebas_util\param\doc_bbdd\doc_bbdd_param.toml` (modificado por el usuario el 2026-10-09):
  `init_command = "SET SESSION character_set_server = utf8mb4; SET NAMES utf8mb4;"`.
- Banco Docker MariaDB 11.4, Connector/Python 1.1.14.

## AI output summary
- **RCA (configuración, no regresión)**: MariaDB ejecuta `init_command` como una sola sentencia; con dos separadas por
  `;` el servidor da error de sintaxis «near 'SET NAMES utf8mb4'». Comprobado en el banco: también falla por
  `cursor.execute` (la vía manual antigua), así que nunca funcionó. Válidos: `SET NAMES utf8mb4;`, `;` finales
  repetidos, `;` dentro de comillas simples/dobles/acento grave y comilla escapada con `\`;
  `SET SESSION character_set_server = utf8mb4, NAMES utf8mb4` aplica las dos variables.
- **F1**: `sync_mgr.py` pasaba `(msg, self.db_type, str(e))` a `DatabaseException(message, operation, db_type,
  details)`; único caso en `src/` (análisis AST de llamadas a la jerarquía de excepciones).
- **Fix**: `connection/config.py::_single_statement` (recorre el SQL fuera de comillas) en
  `MariaDBConnectionConfig.from_params` → `ValueError` → `ValidationError` en el manager; `db_type=` por nombre en
  `SyncDatabaseManager.__init__`.
- **Test-first**: `tests/unit/connection/test_init_command_single_statement.py` (13; 6 fallaban antes del fix).
- **Docs**: `connection_guide.md` § 6 y «Problemas frecuentes».
- **Validación**: `ruff` OK; `mypy` sin errores (332 ficheros); `pytest` 5446 passed, 507 skipped (`build/logs/hotfix_v0.40.2_pytest.txt`); `zensical build --strict` OK; `test_docs_version` OK.
- **App** (fuera del repo, sin git; copia previa en el scratchpad): `doc_bbdd_param.toml` con
  `SET SESSION character_set_server = utf8mb4, NAMES utf8mb4`; pasa la nueva validación.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/config.py`, `src/util_bbdd/managers/sync_mgr.py` | modificados |
| Tests | `tests/unit/connection/test_init_command_single_statement.py` | nuevo |
| Docs | `docs/guides/connection_guide.md` | |
| VERSION | `CHANGELOG.md`, `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `.ai/sessions/SESSIONS_DIGEST.md` | 0.40.2 |

## Directrices para Futuras IAs
- **[MariaDB/init_command]**: una sola sentencia (límite del servidor, sync y async); varias variables con un solo `SET a = …, b = …`. La validación está en `connection/config.py::_single_statement`; la configuración es la frontera de confianza del SQL de `init_command` (no se escapa).
- **[excepciones]**: `DatabaseException(message, operation, db_type, details)`: pasar `db_type`/`details` siempre por nombre; el segundo posicional es `operation`.
- **[Bash en Windows]**: para probar SQL con `\` contra el banco, escribir el script con Write; los heredocs pierden la barra.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- `param_pruebas_util.toml` conserva comentadas líneas `#init_command = "...; ..."` (inactivas; no se tocaron).
- Push y tag `v0.40.2` hechos (2026-10-09).
