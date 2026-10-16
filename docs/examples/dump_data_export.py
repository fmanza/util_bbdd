"""Ejemplo: Volcar datos de PostgreSQL a SQL Server con DumpOrchestrator.

Los engines se crean con las URL de SQLAlchemy de las variables de entorno UTIL_BBDD_EXAMPLE_SOURCE_URL (p. ej.
``postgresql+psycopg://user:password@prod-server:5432/production_db``) y UTIL_BBDD_EXAMPLE_TARGET_URL (p. ej.
``mssql+pymssql://user:password@analytics-server/analytics_db``); los schemas, de UTIL_BBDD_EXAMPLE_SOURCE_SCHEMA
(``public`` por defecto) y UTIL_BBDD_EXAMPLE_TARGET_SCHEMA (``dbo`` por defecto). Las tablas deben existir ya en el
destino: el volcado copia datos, no DDL. Sin las dos URL, el ejemplo termina explicando cómo configurarlas.

Uso:
    python dump_data_export.py
"""

import os

from pathlib import Path

from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator


def main() -> None:
    source_url = os.environ.get("UTIL_BBDD_EXAMPLE_SOURCE_URL")
    target_url = os.environ.get("UTIL_BBDD_EXAMPLE_TARGET_URL")
    if not (source_url and target_url):
        print("Define UTIL_BBDD_EXAMPLE_SOURCE_URL y UTIL_BBDD_EXAMPLE_TARGET_URL con las URL SQLAlchemy, p. ej.")
        print("postgresql+psycopg://user:password@prod-server:5432/production_db  (origen, psycopg 3)")
        print("mssql+pymssql://user:password@analytics-server/analytics_db        (destino)")
        return

    # 1. Engines
    src_engine = create_engine(source_url)
    dst_engine = create_engine(target_url)
    try:
        # 2. Configuración
        config = DumpConfig(
            source_engine=src_engine,
            target_engine=dst_engine,
            source_schema=os.environ.get("UTIL_BBDD_EXAMPLE_SOURCE_SCHEMA", "public"),
            target_schema=os.environ.get("UTIL_BBDD_EXAMPLE_TARGET_SCHEMA", "dbo"),
            chunk_size=1_000,
            output_dir=Path("reports"),
            truncate_target=True,
        )

        # 3. Ejecutar volcado
        result = DumpOrchestrator(config).run()

        # 4. Revisar resultado
        print(f"Informe: {result.report}")
        print(f"Orden de carga: {result.load_order}")

        for tr in result.table_results:
            print(
                f"  [{tr.status.upper():15}] {tr.table_name:30} "
                f"origen={tr.source_rows:>8}  destino={tr.target_rows_after:>8}"
            )
            if tr.error_msg:
                print(f"    ERROR: {tr.error_msg}")
    finally:
        src_engine.dispose()
        dst_engine.dispose()


if __name__ == "__main__":
    main()
