# Ejemplo: Migración DDL PostgreSQL → Oracle / MariaDB / SQL Server

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema PostgreSQL para ejecutarlo en Oracle, MariaDB o SQL Server, adaptando tipos de datos (incluyendo `SERIAL`, tipos sin equivalente directo y `pg_catalog`) al dialecto destino.

Resuelve el caso de migrar un esquema PostgreSQL a un motor de BD corporativo preservando las relaciones, índices y autoincremento, sin reescribir el DDL manualmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_postgresql_source.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`schema`**: corresponde al `TABLE_SCHEMA` en `INFORMATION_SCHEMA` de PostgreSQL (habitualmente `'public'`).
- **Detección de `SERIAL`**: las columnas `SERIAL`, `BIGSERIAL` y `SMALLSERIAL` se detectan por su `COLUMN_DEFAULT = nextval(...)`. El planificador activa `auto_increment=True` y genera el equivalente en el motor destino.
- **`CHARACTER VARYING` sin límite**: `character varying` sin longitud (sin límite en PostgreSQL) se mapea a `CLOB` (Oracle), `LONGTEXT` (MariaDB) o `NVARCHAR(MAX)` (SQL Server).
- **Índices desde `pg_catalog`**: `INFORMATION_SCHEMA` no expone índices en PostgreSQL; el extractor usa `pg_catalog.pg_index` para obtenerlos correctamente.
- **Tipos sin equivalente**: `ARRAY`, `TSVECTOR`, `USER-DEFINED` se mapean a tipos LOB con severidad `ERROR` en los warnings; el script DDL sigue generándose.

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

# Ejecución (requiere servidor PostgreSQL accesible)
# Sustituir credenciales antes de ejecutar
python docs/examples/migrate_postgresql_source.py
```

El script DDL se guarda como `public_schema_mariadb.sql` (o el nombre configurado).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración PostgreSQL como Origen](../functional/migrate_postgresql_source.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración PostgreSQL](../api/migrate_postgresql_source.md) — API de `MigrationPlanner` con origen PostgreSQL
- **Ejemplos relacionados**: [Migración SQL Server](migrate_sqlserver_source.md) — patrón equivalente con origen SQL Server
