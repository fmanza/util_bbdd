"""Ejemplo: Migración DDL de un schema SQL Server a PostgreSQL con MigrationPlanner."""

from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

# 1. Conexión SQL Server (replace with real credentials)
ss_manager = SyncDatabaseManager(
    db_type="sqlserver",
    conn_params={
        "host": "sqlserver-host",  # replace with real host
        "port": 1433,
        "user": "reader",
        "password": "secret",
        "database": "mydb",
    },
)

# 2. Configurar el planificador SQL Server → PostgreSQL
planner = MigrationPlanner(
    source_engine="sqlserver",
    target_engine="postgresql",
    pg_schema="mi_schema",  # opcional: emite SET search_path
)

# 3. Planificar (extrae metadatos y transforma tipos)
plan = planner.plan(connection=ss_manager, schema="dbo")

# 4. Revisar resumen de avisos
print(format_plan_text(plan))
print(f"Avisos ERROR: {plan.error_count}")

# 5. Guardar script DDL en disco
with open("dbo_schema_postgresql.sql", "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())

print("Script guardado en: dbo_schema_postgresql.sql")

ss_manager.close()
