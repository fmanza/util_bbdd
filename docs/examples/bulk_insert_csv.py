"""
Bulk Insert from CSV with Audit Trail

Este ejemplo muestra cómo:
1. Cargar datos de un CSV con pandas
2. Insertar masivamente en una BD
3. Registrar auditoría de cambios
4. Manejar errores de validación
"""

import io
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from util_bbdd import DatabaseException, ValidationError
from util_bbdd.bulk import bulk_crud

# Datos de ejemplo (en producción, leer desde archivo CSV)
CSV_DATA = """id,name,email,created_at
1,Alice Johnson,alice@example.com,2024-01-15
2,Bob Smith,bob@example.com,2024-02-20
3,Charlie Brown,charlie@example.com,2024-03-10"""


def demonstrate_bulk_insert():
    """Demostración de inserción masiva con auditoría."""

    # 1. Crear una BD SQLite local para que SQLAlchemy y bulk_crud compartan conexion.
    engine = create_engine("sqlite:///bulk_insert_demo.db")

    # Crear tabla de prueba
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.execute(
            text(
                """CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TEXT
                )"""
            )
        )

    # 2. Cargar datos del CSV
    df = pd.read_csv(io.StringIO(CSV_DATA))
    print(f"Cargados {len(df)} registros desde CSV")
    print(df)
    print()

    # 3. Crear instancia de bulk_crud
    bulk_crud_instance = bulk_crud(engine=engine, chunk_size=100, audit_csv_path=Path("audit_bulk_insert.csv"))

    print(f"Preparando {len(df)} registros para insercion masiva...\n")

    # 4. Realizar inserción masiva desde DataFrame
    try:
        # generar_sql=False ejecuta el INSERT. Con generar_sql=True solo escribe SQL a fichero.
        bulk_crud_instance.bulk_insert_from_df(
            df=df,
            tabla_destino="users",
            generar_sql=False,
        )

        print(f"Insertados: {len(df)} registros")
        print("Auditoria guardada en: audit_bulk_insert.csv")

    except ValidationError as e:
        print(f"Error de validacion: {e}")
    except DatabaseException as e:
        print(f"Error de BD: {e}")

    # 5. Verificar datos
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, name, email, created_at FROM users ORDER BY id")).fetchall()
        count_result = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()

    print("\nDatos finales en BD:")
    for row in result:
        print(f"   {row}")

    # 6. Contar cambios
    print(f"\nTotal de registros: {count_result}")


if __name__ == "__main__":
    demonstrate_bulk_insert()
