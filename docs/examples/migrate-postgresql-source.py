"""Ejemplo: Migración DDL de un schema PostgreSQL a MariaDB con MigrationPlanner."""

from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

# 1. Conexión PostgreSQL (replace with real credentials)
pg_manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "postgres-host",  # replace with real host
        "port": 5432,
        "user": "reader",
        "password": "secret",
        "database": "mydb",
    },
)

# 2. Configurar el planificador PostgreSQL → MariaDB
planner = MigrationPlanner(
    source_engine="postgresql",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
)

# 3. Planificar (extrae metadatos y transforma tipos)
plan = planner.plan(connection=pg_manager, schema="public")

# 4. Revisar resumen de avisos
print(format_plan_text(plan))
print(f"Avisos ERROR: {plan.error_count}")

# 5. Guardar script DDL en disco
with open("public_schema_mariadb.sql", "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())

print("Script guardado en: public_schema_mariadb.sql")

pg_manager.close()
