"""Ejemplo: Migración DDL de un schema MariaDB a PostgreSQL con MigrationPlanner.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``mariadb+pymysql://reader:secret@mariadb-host:3306/ventas``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA (``ventas`` por
defecto). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python migrate_mariadb_source.py
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
        **parts.query,
    }
    return {key: value for key, value in params.items() if value is not None}


def main() -> None:
    url = os.environ.get("UTIL_BBDD_EXAMPLE_URL")
    if not url:
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy del MariaDB de origen, p. ej.")
        print("mariadb+pymysql://reader:secret@mariadb-host:3306/ventas")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "ventas")

    # 1. Conexión MariaDB
    mariadb_manager = SyncDatabaseManager(db_type="mariadb", conn_params=conn_params_from_url(url))
    try:
        # 2. Configurar el planificador MariaDB → PostgreSQL
        planner = MigrationPlanner(
            source_engine="mariadb",
            target_engine="postgresql",
            pg_schema=schema,  # opcional: emite SET search_path = <schema>;
        )

        # 3. Planificar (extrae metadatos y transforma tipos)
        plan = planner.plan(connection=mariadb_manager, schema=schema)

        # 4. Revisar resumen de avisos
        print(format_plan_text(plan))
        print(f"Avisos ERROR: {plan.error_count}")

        # 5. Guardar script DDL en disco
        filename = f"{schema}_schema_postgresql.sql"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {filename}")
    finally:
        mariadb_manager.close()


if __name__ == "__main__":
    main()
