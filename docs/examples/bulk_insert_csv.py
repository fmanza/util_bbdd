"""
Bulk Insert from CSV with Audit Trail

Este ejemplo muestra cómo:
1. Cargar datos de un CSV con pandas
2. Insertar masivamente en una BD
3. Registrar auditoría de cambios
4. Manejar errores de validación
"""

import io

import pandas as pd

from util_bbdd import DatabaseException, SyncDatabaseManager, ValidationError

# Datos de ejemplo (en producción, leer desde archivo CSV)
CSV_DATA = """id,name,email,created_at
1,Alice Johnson,alice@example.com,2024-01-15
2,Bob Smith,bob@example.com,2024-02-20
3,Charlie Brown,charlie@example.com,2024-03-10"""


def demonstrate_bulk_insert():
    """Demostración de inserción masiva con auditoría."""

    # 1. Conectar a la BD
    manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"})

    # Crear tabla de prueba
    manager.execute_custom_many(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            created_at TEXT
        )"""
    )

    # 2. Cargar datos del CSV
    df = pd.read_csv(io.StringIO(CSV_DATA))
    print(f"📥 Cargados {len(df)} registros desde CSV")
    print(df)
    print()

    # 3. Crear instancia de bulk_crud (factory)
    from pathlib import Path

    from util_bbdd.bulk import bulk_crud as get_bulk_crud

    bulk_crud_instance = get_bulk_crud(
        engine=manager.engine, chunk_size=100, audit_csv_path=Path("audit_bulk_insert.csv")
    )

    print(f"📋 Preparando {len(df)} registros para inserción masiva...\n")

    # 4. Realizar inserción masiva desde DataFrame
    try:
        # Usar API real: bulk_insert_from_df()
        bulk_crud_instance.bulk_insert_from_df(
            df=df, tabla_destino="users", generar_sql=True, path_sql=Path("insert_queries.sql")
        )

        print(f"✅ Insertados: {len(df)} registros")
        print("📝 Auditoría guardada en: audit_bulk_insert.csv")
        print("🔍 Queries SQL guardadas en: insert_queries.sql\n")

    except ValidationError as e:
        print(f"❌ Error de validación: {e}")
    except DatabaseException as e:
        print(f"❌ Error de BD: {e}")

    # 5. Verificar datos
    result = manager.execute_custom_many("SELECT * FROM users")
    print("\n📊 Datos finales en BD:")
    for row in result:
        print(f"   {row}")

    # 6. Contar cambios
    count_result = manager.execute_custom_one("SELECT COUNT(*) FROM users")
    print(f"\n📝 Total de registros: {count_result[0]}")

    manager.close()


if __name__ == "__main__":
    demonstrate_bulk_insert()
