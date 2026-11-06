"""Ejemplo: migrar las vistas de un schema PostgreSQL a MySQL, reescribiendo su SQL con sqlglot, y validarlas.

El origen se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``postgresql+psycopg://reader:secret@pg-host:5432/ventas``, y el schema de UTIL_BBDD_EXAMPLE_SCHEMA (``public`` por
defecto). Sin la URL, el ejemplo termina explicando cómo configurarla. Necesita el extra ``util_bbdd[migrate]``
(sqlglot). Con destino MySQL la validación es sintáctica: no necesita conexión al destino.

Uso:
    python migrate_views.py
"""

import os

from sqlalchemy.engine import make_url

from util_bbdd import MigrationPlanner, SyncDatabaseManager


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
        print("postgresql+psycopg://reader:secret@pg-host:5432/ventas")
        return
    schema = os.environ.get("UTIL_BBDD_EXAMPLE_SCHEMA", "public")

    origen = SyncDatabaseManager(db_type="postgresql", conn_params=conn_params_from_url(url))
    try:
        # 1. "transpile" exige sqlglot; "auto" (por defecto) copia sin reescribir si no está instalado
        planner = MigrationPlanner(source_engine="postgresql", target_engine="mysql", view_strategy="transpile")
        plan = planner.plan(connection=origen, schema=schema)

        # 2. SQL de cada vista en el dialecto destino y sus avisos (filtrar por code, no por el texto)
        for vista in plan.views:
            print(f"Vista {vista.name}: {vista.query}")
            for aviso in vista.warnings:
                print(f"  {aviso.severity} {aviso.code}: {aviso.message}")

        # 3. Validación: con destino MySQL, sintáctica con sqlglot (method="syntax")
        for resultado in plan.validate_views():
            estado = "válida" if resultado.valid else f"NO válida ({resultado.error})"
            print(f"Validación {resultado.view} [{resultado.method}]: {estado}")

        # 4. Script DDL completo (tablas y vistas)
        filename = f"{schema}_views_mysql.sql"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(plan.emit_ddl())
        print(f"Script guardado en: {filename}")
    finally:
        origen.close()


if __name__ == "__main__":
    main()
