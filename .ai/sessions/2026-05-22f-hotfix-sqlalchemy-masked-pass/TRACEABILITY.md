# TRACEABILITY

## Session metadata
- id: 2026-05-22f-hotfix-sqlalchemy-masked-pass
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: RCA + FIX + AUDIT_CODE

## Prompt issued
`ConnectionError` al conectar a SQL Server con `SQLAlchemyEngineFactory`:
error 18456 "Login failed for user 'DA_DPSS'" / "Adaptive Server connection failed".
Config correcta (host/port/user/password/pool_size/max_overflow/pool_timeout).

## Context supplied
- `src/util_bbdd/factory/sqlalchemy_engine_factory.py` — fichero afectado
- `src/util_bbdd/factory/async_sqlalchemy_engine_factory.py` — referencia de patrón correcto
- Stack trace completo con error pymssql 18456

## AI output summary
- **RCA**: `_build_sqlserver_connection_string` y `_build_postgresql_connection_string` construían
  `masked_pass = "*" * len(password)` con intención de display, pero usaban `masked_pass` —
  no `password` — en la URL de conexión. SQLAlchemy enviaba asteriscos literales al servidor;
  SQL Server los rechazaba con login failed (18456). La async factory no tenía el bug
  (usaba `password` directo + `_sanitize_conn_str()` separado para logging).
- **FIX**: Eliminada variable `masked_pass` en ambos métodos; sustituida por `password` en las
  dos f-strings de retorno (`mssql+pymssql://`, `mssql+pyodbc://`, `postgresql+psycopg://`).
- **AUDIT_CODE**: 2887 tests pasan; 0 regresiones. Edge case pendiente (contraseñas con `@`/`:`
  requieren URL-encoding) no es regresión de este fix.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix `_build_postgresql_connection_string` | `src/util_bbdd/factory/sqlalchemy_engine_factory.py` L196 | completado |
| Fix `_build_sqlserver_connection_string` | `src/util_bbdd/factory/sqlalchemy_engine_factory.py` L245–249 | completado |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Reinstalar el paquete en el entorno afectado: `pip install -e c:\Desarrollo\python\libs\util_bbdd`
- Edge case mejora futura (no hotfix): URL-encoding de contraseñas con caracteres especiales.
