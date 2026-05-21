# REQUEST

## Session metadata
- id: 2026-05-21-hotfix-postgresql-schema
- fecha: 2026-05-21
- rama: develop
- skill: hotfix
- fase solicitada: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Solicitud original saneada
Al conectar con PostgreSQL en `src/util_bbdd/migrate`, no se recoge el `database` y `schema`
definidos en el bloque `[conexion.postgresql]` del TOML de configuración. No se muestra error.

Configuración de referencia:
```toml
[conexion.postgresql]
host = "localhost"
port = 5432
user = "admin"
password = "admin123"
database = "testdb"
schema = "ventas_test"
pool_size = 5
pool_timeout = 30
max_idle = 300
```

## Objetivo operativo de esta sesión
- Identificar por qué `schema` es ignorado silenciosamente al construir la conexión PostgreSQL.
- Aplicar fix mínimo sin refactorizar código no relacionado.
- Verificar ausencia de regresiones en tests existentes.

## Restricciones explícitas
- Solo fix mínimo; no refactorizar ni optimizar.
- No tocar módulos fuera de la capa de conexión PostgreSQL.

## Resultado esperado
- `PostgreSQLConnectionConfig` almacena `schema` y lo propaga en `to_driver_kwargs()`.
- `pool_connection_postgresql.py` aplica `schema` como `search_path` en el conninfo psycopg3.
- 3083 tests pasan sin regresiones.
- Sesión documentada en `.ai/sessions/2026-05-21-hotfix-postgresql-schema/`.
