"""Ejemplo: Migración DDL de un schema MariaDB a PostgreSQL con MigrationPlanner."""

from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

# 1. Conexión MariaDB (replace with real credentials)
mariadb_manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "mariadb-host",  # replace with real host
        "port": 3306,
        "user": "reader",
        "password": "secret",
        "database": "ventas",
    },
)

# 2. Configurar el planificador MariaDB → PostgreSQL
planner = MigrationPlanner(
    source_engine="mariadb",
    target_engine="postgresql",
    pg_schema="ventas",  # opcional: emite SET search_path = ventas;
)

# 3. Planificar (extrae metadatos y transforma tipos)
plan = planner.plan(connection=mariadb_manager, schema="ventas")

# 4. Revisar resumen de avisos
print(format_plan_text(plan))
print(f"Avisos ERROR: {plan.error_count}")

# 5. Guardar script DDL en disco
with open("ventas_schema_postgresql.sql", "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())

print("Script guardado en: ventas_schema_postgresql.sql")

mariadb_manager.close()
