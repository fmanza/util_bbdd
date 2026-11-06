"""Ejemplo: Migración DDL de un schema SQL Server a PostgreSQL con MigrationPlanner.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``mssql+pymssql://reader:secret@sqlserver-host:1433/mydb``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA (``dbo`` por
defecto). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python migrate_sqlserver_source.py
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
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy del SQL Server de origen, p. ej.")
        print("mssql+pymssql://reader:secret@sqlserver-host:1433/mydb")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "dbo")

    # 1. Conexión SQL Server
    ss_manager = SyncDatabaseManager(db_type="sqlserver", conn_params=conn_params_from_url(url))
    try:
        # 2. Configurar el planificador SQL Server → PostgreSQL
        planner = MigrationPlanner(
            source_engine="sqlserver",
            target_engine="postgresql",
            pg_schema="mi_schema",  # opcional: emite SET search_path
        )

        # 3. Planificar (extrae metadatos y transforma tipos)
        plan = planner.plan(connection=ss_manager, schema=schema)

        # 4. Revisar resumen de avisos
        print(format_plan_text(plan))
        print(f"Avisos ERROR: {plan.error_count}")

        # 5. Guardar script DDL en disco
        filename = f"{schema}_schema_postgresql.sql"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {filename}")
    finally:
        ss_manager.close()


if __name__ == "__main__":
    main()
