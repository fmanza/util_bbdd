"""Ejemplo: migración DDL de un schema MySQL a PostgreSQL con MigrationPlanner.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``mysql+pymysql://reader:secret@mysql-host:3306/ventas``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA (``ventas`` por
defecto). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python migrate_mysql.py
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
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy del MySQL de origen, p. ej.")
        print("mysql+pymysql://reader:secret@mysql-host:3306/ventas")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "ventas")

    # 1. Conexión MySQL (MySQL como origen reutiliza las capas de MariaDB)
    origen = SyncDatabaseManager(db_type="mysql", conn_params=conn_params_from_url(url))
    try:
        # 2. Planificar MySQL → PostgreSQL (extrae metadatos y transforma tipos)
        plan = MigrationPlanner(source_engine="mysql", target_engine="postgresql").plan(
            connection=origen, schema=schema
        )

        # 3. Resumen y avisos de tipos (los ERROR impiden ejecutar el plan)
        print(format_plan_text(plan))
        print(f"Avisos ERROR: {plan.error_count}")

        # 4. Guardar el script DDL
        filename = f"{schema}_schema_postgresql.sql"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {filename}")
    finally:
        origen.close()


if __name__ == "__main__":
    main()
