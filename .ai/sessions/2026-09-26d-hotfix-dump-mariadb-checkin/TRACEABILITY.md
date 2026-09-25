# TRACEABILITY

## Session metadata
- id: 2026-09-26d-hotfix-dump-mariadb-checkin
- fecha: 2026-09-26
- rama: develop (base `e759a4f`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-09 (MEDIA) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.8

## Prompt issued
```
/hotfix PD-09: en MySQL/MariaDB, el listener checkin de ConstraintManager (_fk_on) hace dbapi_conn.cursor(); con una
conexión invalidada dbapi_conn es None y el AttributeError sustituye a la excepción real. Criterio: un error durante la
carga en MySQL/MariaDB llega intacto a quien llama; test.
```

## RCA
- En MySQL/MariaDB, `ConstraintManager._disable_mariadb` registra en el pool del engine destino un listener `checkout` (`FOREIGN_KEY_CHECKS = 0`) y otro `checkin` (`= 1`), que ejecutan el `SET` con `_exec_session_var(dbapi_conn, …)`.
- Cuando SQLAlchemy invalida una conexión (queda inservible tras un error), cierra la conexión DBAPI y dispara `checkin` con `dbapi_conn=None`. `None.cursor()` lanza `AttributeError` y ese error sale del `with` en lugar del original.
- **Reproducido en MariaDB 11.4 y MySQL 8.4** (script de la sesión: `ConstraintManager` real, conexión invalidada y excepción propia dentro del `with`): se recibía `AttributeError: 'NoneType' object has no attribute 'cursor'` en vez de la excepción de la carga.

## FIX (mínimo)
- `dump/_constraints.py::_exec_session_var`: si `dbapi_conn is None`, no hace nada. Cubre los dos listeners. No hay nada que restaurar: el pool descarta la conexión invalidada y no se reutiliza con `FOREIGN_KEY_CHECKS = 0`.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Test**: `TestConstraintManagerMariaDB::test_listeners_ignore_invalidated_connection` (los dos listeners con `None` no lanzan). Falla sin el arreglo.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4529 passed**.
- **Servidores reales**:

| Motor | Sin el arreglo | Con el arreglo | `FOREIGN_KEY_CHECKS` en el pool después |
|---|---|---|---|
| MariaDB 11.4 | `AttributeError` | **excepción original** | 1 |
| MySQL 8.4 | `AttributeError` | **excepción original** | 1 |

## AUDIT_CODE
- **Conexiones válidas**: sin cambio (mismo `SET` en `checkout`/`checkin`).
- **Conexión invalidada**: no se ejecuta el `SET`; el pool la descarta. Comprobado: la siguiente conexión del pool tiene `FOREIGN_KEY_CHECKS = 1`.
- **Fuera del alcance**: si el `SET` del `checkin` falla sobre una conexión aún válida (p. ej. servidor caído), ese error sigue propagándose como antes; no se ha observado.
- **Compatibilidad**: sin cambios de API.

## VERSION
- Commit: `fix(dump): no tapar el error de la carga en MySQL/MariaDB con una conexión invalidada (PD-09)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/mysql]**: los listeners de pool reciben `dbapi_conn=None` en el `checkin` de una conexión invalidada; cualquier listener nuevo debe tolerarlo.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-06 (SQLite con `parallel_pk_ranges`), PD-07 (origen SQLite).
