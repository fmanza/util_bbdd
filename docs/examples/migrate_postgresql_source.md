# Ejemplo: Migración DDL PostgreSQL → Oracle / MariaDB / SQL Server

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema PostgreSQL para ejecutarlo en Oracle, MariaDB, MySQL o SQL Server, adaptando tipos de datos (incluyendo `SERIAL`, tipos sin equivalente directo y `pg_catalog`) al dialecto destino.

Resuelve el caso de migrar un esquema PostgreSQL a un motor de BD corporativo preservando las relaciones, índices y autoincremento, sin reescribir el DDL manualmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_postgresql_source.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`schema`**: el schema de PostgreSQL (habitualmente `'public'`).
- **Autoincremento**: las columnas `SERIAL`/`BIGSERIAL`/`SMALLSERIAL` (default `nextval(...)`) y las `GENERATED … AS IDENTITY` se marcan como `auto_increment=True` y se emite el equivalente en el motor destino.
- **`CHARACTER VARYING` sin límite**: `character varying` sin longitud (sin límite en PostgreSQL) se mapea a `CLOB` (Oracle), `LONGTEXT` (MariaDB) o `NVARCHAR(MAX)` (SQL Server).
- **Metadatos desde `pg_catalog`**: tablas, columnas, claves, índices y vistas se leen de `pg_catalog`, una consulta por tipo de objeto (ADR-003). Las vistas materializadas no se migran.
- **Tipos sin equivalente**: `ARRAY`, `TSVECTOR`, `USER-DEFINED` se mapean a texto largo (`LONGTEXT`, `NVARCHAR(MAX)`, `CLOB`) con severidad `ERROR` en los avisos; el script DDL sigue generándose.

Para PostgreSQL → Oracle:

```python
planner = MigrationPlanner(
    source_engine="postgresql", target_engine="oracle",
    oracle_identity_mode="identity_by_default_on_null",  # Oracle 12c+
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/migrate_postgresql_source.py

# Ejecución contra un PostgreSQL accesible (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla)
export UTIL_BBDD_EXAMPLE_URL="postgresql+psycopg://reader:secret@postgres-host:5432/mydb"
export UTIL_BBDD_EXAMPLE_SCHEMA="public"  # opcional; por defecto public
python docs/examples/migrate_postgresql_source.py
```

El script DDL se guarda como `<schema>_schema_mariadb.sql` (`public_schema_mariadb.sql` con el schema por defecto). `tests/integration/test_docs_examples_engines.py` lo ejecuta contra el banco del proyecto.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración PostgreSQL como Origen](../functional/migrate_postgresql_source.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración PostgreSQL](../api/migrate_postgresql_source.md) — API de `MigrationPlanner` con origen PostgreSQL
- **Ejemplos relacionados**: [Migración SQL Server](migrate_sqlserver_source.md) — patrón equivalente con origen SQL Server
