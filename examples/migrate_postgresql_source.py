"""Ejemplo: Migración DDL de un schema PostgreSQL a MariaDB con MigrationPlanner.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``postgresql+psycopg://reader:secret@postgres-host:5432/mydb``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA (``public``
por defecto). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python migrate_postgresql_source.py
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
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy del PostgreSQL de origen, p. ej.")
        print("postgresql+psycopg://reader:secret@postgres-host:5432/mydb")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "public")

    # 1. Conexión PostgreSQL
    pg_manager = SyncDatabaseManager(db_type="postgresql", conn_params=conn_params_from_url(url))
    try:
        # 2. Configurar el planificador PostgreSQL → MariaDB
        planner = MigrationPlanner(
            source_engine="postgresql",
            target_engine="mariadb",
            charset="utf8mb4",
            collation="utf8mb4_uca1400_ai_ci",  # por defecto; requiere MariaDB >= 10.10
        )

        # 3. Planificar (extrae metadatos y transforma tipos)
        plan = planner.plan(connection=pg_manager, schema=schema)

        # 4. Revisar resumen de avisos
        print(format_plan_text(plan))
        print(f"Avisos ERROR: {plan.error_count}")

        # 5. Guardar script DDL en disco
        filename = f"{schema}_schema_mariadb.sql"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {filename}")
    finally:
        pg_manager.close()


if __name__ == "__main__":
    main()
