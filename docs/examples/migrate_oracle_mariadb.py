"""Ejemplo: Migración DDL de un schema Oracle a MariaDB con MigrationPlanner."""

from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

# 1. Conexión Oracle (replace with real credentials)
oracle_manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "host": "oracle-host",  # replace with real host
        "port": 1521,
        "service_name": "ORCL",
        "user": "reader",
        "password": "secret",
        "database": "ORCL",
    },
)

# 2. Configurar el planificador Oracle → MariaDB
planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_spanish2_ci",
    number_fallback="DOUBLE",
)

# 3. Planificar (extrae metadatos y transforma tipos)
plan = planner.plan(connection=oracle_manager, schema="HR")

# 4. Revisar resumen de avisos
print(format_plan_text(plan))
print(f"Avisos ERROR: {plan.error_count}")
print(f"Avisos WARNING: {plan.warning_count}")

# 5. Guardar script DDL en disco
with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())

print(f"Script guardado en: {plan.suggested_filename()}")

oracle_manager.close()
