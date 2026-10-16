# Ejemplo: Migración DDL SQL Server → Oracle / MariaDB / PostgreSQL

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema SQL Server para ejecutarlo en Oracle, MariaDB, MySQL o PostgreSQL, adaptando tipos de datos, columnas `IDENTITY` y vistas T-SQL al dialecto destino.

Resuelve el caso de migrar una aplicación SQL Server a un motor de BD open-source, preservando índices, FKs y autoincremento sin reescribir el DDL manualmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_sqlserver_source.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`schema`**: el schema de SQL Server (habitualmente `'dbo'`).
- **Columnas `IDENTITY`**: se leen del catálogo `sys.*` (`is_identity`), una consulta por tipo de objeto (ADR-003). El planificador activa `auto_increment=True` y genera el equivalente en el motor destino.
- **Tipos `MAX` (`VARCHAR(MAX)`, `NVARCHAR(MAX)`)**: SQL Server los marca con longitud `-1`. El extractor lo detecta y emite el tipo LOB apropiado en destino.
- **Vistas reescritas**: el SQL de las vistas (`GETDATE()`, `ISNULL()`, `TOP`, etc.) se reescribe al dialecto destino con sqlglot (extra `util_bbdd[migrate]`; ver [reescritura de vistas](../functional/migrate_views.md)). El plan emite un aviso de revisión por cada vista.
- **Definición completa de las vistas**: se lee con `OBJECT_DEFINITION` (sin el límite de 4000 caracteres de `INFORMATION_SCHEMA.VIEW_DEFINITION`); una vista cifrada (`WITH ENCRYPTION`) no tiene definición legible.

Para SQL Server → Oracle:

```python
planner = MigrationPlanner(
    source_engine="sqlserver", target_engine="oracle",
    oracle_identity_mode="sequence_trigger",  # compatible con Oracle 11g+
)
```

Para SQL Server → MariaDB:

```python
planner = MigrationPlanner(
    source_engine="sqlserver", target_engine="mariadb",
    charset="utf8mb4", collation="utf8mb4_uca1400_ai_ci",  # por defecto; requiere MariaDB >= 10.10
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/migrate_sqlserver_source.py

# Ejecución contra un SQL Server accesible con pymssql (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla)
export UTIL_BBDD_EXAMPLE_URL="mssql+pymssql://reader:secret@sqlserver-host:1433/mydb"
export UTIL_BBDD_EXAMPLE_SCHEMA="dbo"  # opcional; por defecto dbo
python docs/examples/migrate_sqlserver_source.py
```

El script DDL se guarda como `<schema>_schema_postgresql.sql` (`dbo_schema_postgresql.sql` con el schema por defecto). `tests/integration/test_docs_examples_engines.py` lo ejecuta contra el banco del proyecto.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración SQL Server como Origen](../functional/migrate_sqlserver_source.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración SQL Server](../api/migrate_sqlserver_source.md) — API de `MigrationPlanner` con origen SQL Server
- **Ejemplos relacionados**: [Migración PostgreSQL](migrate_postgresql_source.md) — patrón equivalente con origen PostgreSQL
