# Ejemplo: Migración DDL MariaDB → Oracle / SQL Server / PostgreSQL

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema MariaDB para ejecutarlo en MySQL, Oracle, SQL Server o PostgreSQL, adaptando tipos de datos, `AUTO_INCREMENT` y vistas al dialecto destino.

Resuelve el caso de migrar una aplicación MariaDB a un motor de BD corporativo sin reescribir el DDL manualmente: el plan registra cada decisión de conversión con nivel de severidad.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_mariadb_source.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`schema`**: en MariaDB es el nombre de la base de datos. Para una BD llamada `ventas`, usar `schema="ventas"`.
- **`AUTO_INCREMENT` → equivalentes**: el planificador convierte automáticamente: MariaDB `AUTO_INCREMENT` → Oracle `SEQUENCE+TRIGGER` (por defecto; `oracle_identity_mode="identity_by_default_on_null"` en 12c+), SQL Server `IDENTITY(1,1)`, PostgreSQL `SERIAL/BIGSERIAL`.
- **Vistas reescritas**: el SQL de las vistas se reescribe al dialecto destino con sqlglot (extra `util_bbdd[migrate]`; ver [reescritura de vistas](../functional/migrate_views.md)). El plan emite un aviso de revisión por cada vista.
- **`plan.error_count`**: verificar antes de ejecutar contra el destino. Errores indican tipos sin equivalente directo que requieren intervención manual.

Para MariaDB → Oracle:

```python
planner = MigrationPlanner(source_engine="mariadb", target_engine="oracle")
```

Para MariaDB → SQL Server:

```python
planner = MigrationPlanner(
    source_engine="mariadb", target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/migrate_mariadb_source.py

# Ejecución contra un MariaDB accesible (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla)
export UTIL_BBDD_EXAMPLE_URL="mariadb+pymysql://reader:secret@mariadb-host:3306/ventas"
export UTIL_BBDD_EXAMPLE_SCHEMA="ventas"  # opcional; por defecto ventas
python docs/examples/migrate_mariadb_source.py
```

El script DDL se guarda como `<schema>_schema_postgresql.sql` (`ventas_schema_postgresql.sql` con el schema por defecto). `tests/integration/test_docs_examples_engines.py` lo ejecuta contra el banco del proyecto.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración MariaDB como Origen](../functional/migrate_mariadb_source.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración MariaDB](../api/migrate_mariadb_source.md) — API de `MigrationPlanner` con origen MariaDB
- **Ejemplos relacionados**: [Migración Oracle](migrate_oracle_mariadb.md) — patrón equivalente con origen Oracle
