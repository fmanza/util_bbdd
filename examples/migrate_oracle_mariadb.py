"""Ejemplo: Migración DDL de un schema Oracle a MariaDB con MigrationPlanner.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``oracle+oracledb://reader:secret@oracle-host:1521/?service_name=ORCL``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA
(``HR`` por defecto). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python migrate_oracle_mariadb.py
"""

import os

from sqlalchemy.engine import make_url

from util_bbdd import MigrationPlanner, SyncDatabaseManager
from util_bbdd.migrate import format_plan_text


def conn_params_from_url(url: str) -> dict[str, object]:
    """``conn_params`` de ``SyncDatabaseManager`` a partir de una URL de SQLAlchemy (la query añade parámetros)."""
    parts = make_url(url)
    params: dict[str, object] = {
        "host": parts.host,
        "port": parts.port,
        "user": parts.username,
        "password": parts.password,
        "database": parts.database,
        **parts.query,  # service_name en Oracle
    }
    return {key: value for key, value in params.items() if value is not None}


def main() -> None:
    url = os.environ.get("UTIL_BBDD_EXAMPLE_URL")
    if not url:
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy del Oracle de origen, p. ej.")
        print("oracle+oracledb://reader:secret@oracle-host:1521/?service_name=ORCL")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "HR")

    # 1. Conexión Oracle
    oracle_manager = SyncDatabaseManager(db_type="oracle", conn_params=conn_params_from_url(url))
    try:
        # 2. Configurar el planificador Oracle → MariaDB
        planner = MigrationPlanner(
            source_engine="oracle",
            target_engine="mariadb",
            charset="utf8mb4",
            collation="utf8mb4_spanish2_ci",
            number_fallback="DOUBLE",
        )

        # 3. Planificar (extrae metadatos y transforma tipos)
        plan = planner.plan(connection=oracle_manager, schema=schema)

        # 4. Revisar resumen de avisos
        print(format_plan_text(plan))
        print(f"Avisos ERROR: {plan.error_count}")
        print(f"Avisos WARNING: {plan.warning_count}")

        # 5. Guardar script DDL en disco
        with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {plan.suggested_filename()}")
    finally:
        oracle_manager.close()


if __name__ == "__main__":
    main()
