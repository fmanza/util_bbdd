# Ejemplo: Migración DDL SQL Server → Oracle / MariaDB / PostgreSQL

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema SQL Server para ejecutarlo en Oracle, MariaDB o PostgreSQL, adaptando tipos de datos, columnas `IDENTITY` y vistas T-SQL al dialecto destino.

Resuelve el caso de migrar una aplicación SQL Server a un motor de BD open-source, preservando índices, FKs y autoincremento sin reescribir el DDL manualmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_sqlserver_source.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`schema`**: corresponde al `TABLE_SCHEMA` en `INFORMATION_SCHEMA` de SQL Server (habitualmente `'dbo'`).
- **Columnas `IDENTITY`**: detectadas via `COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')`. El planificador activa `auto_increment=True` y genera el equivalente en el motor destino.
- **Tipos `MAX` (`VARCHAR(MAX)`, `NVARCHAR(MAX)`)**: SQL Server usa `-1` como sentinel en `CHARACTER_MAXIMUM_LENGTH`. El extractor lo detecta y emite el tipo LOB apropiado en destino.
- **Vistas reescritas**: el SQL de las vistas (`GETDATE()`, `ISNULL()`, `TOP`, etc.) se reescribe al dialecto destino con sqlglot (extra `util_bbdd[migrate]`; ver [reescritura de vistas](../functional/migrate_views.md)). El plan emite un aviso de revisión por cada vista.
- **`VIEW_DEFINITION` truncada**: en SQL Server < 2019, las vistas con definición > 4000 chars pueden quedar truncadas. Verificar manualmente si el script incluye vistas largas.

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

# Ejecución (requiere servidor SQL Server accesible; driver pymssql instalado)
# Sustituir credenciales antes de ejecutar
python docs/examples/migrate_sqlserver_source.py
```

El script DDL se guarda como `dbo_schema_postgresql.sql` (o el nombre configurado).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración SQL Server como Origen](../functional/migrate_sqlserver_source.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración SQL Server](../api/migrate_sqlserver_source.md) — API de `MigrationPlanner` con origen SQL Server
- **Ejemplos relacionados**: [Migración PostgreSQL](migrate_postgresql_source.md) — patrón equivalente con origen PostgreSQL
