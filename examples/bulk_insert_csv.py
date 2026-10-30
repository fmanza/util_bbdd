"""
Ejemplo: Bulk insert desde CSV con auditoría y lectura del historial de operaciones.
Requisitos: util_bbdd con el extra postgresql (o el driver del motor que uses)

La conexión se lee de la URL de SQLAlchemy de la variable de entorno UTIL_BBDD_EXAMPLE_URL, por ejemplo
``postgresql+psycopg://postgres:secret@localhost:5432/test_db``; los parámetros de la query de la URL se pasan
también al manager (p. ej. ``?schema=pruebas``). Sin la URL, el ejemplo termina explicando cómo configurarla.

Uso:
    python bulk_insert_csv.py
"""

import os

from pathlib import Path

import pandas as pd

from sqlalchemy import text
from sqlalchemy.engine import make_url

from util_bbdd import BulkCrud, DatabaseException, SyncDatabaseManager
from util_bbdd.bulk import AuditManager
from util_bbdd.bulk.options import AuditOptions


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
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy de un PostgreSQL de pruebas, p. ej.")
        print("postgresql+psycopg://postgres:secret@localhost:5432/test_db")
        return

    # Crear datos de ejemplo
    df_data = pd.DataFrame(
        {
            "id": range(1, 101),
            "nombre": [f"Usuario{i}" for i in range(1, 101)],
            "email": [f"user{i}@example.com" for i in range(1, 101)],
        }
    )

    # Guardar CSV temporal
    csv_input = Path("usuarios_input.csv")
    df_data.to_csv(csv_input, index=False)

    # Engine SQLAlchemy del manager
    mgr = SyncDatabaseManager(db_type="postgresql", conn_params=conn_params_from_url(url))
    try:
        engine = mgr.get_sqlalchemy_engine()

        # Tabla destino (BulkCrud no crea tablas)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS usuarios "
                    "(id INTEGER PRIMARY KEY, nombre VARCHAR(50), email VARCHAR(100))"
                )
            )
            conn.execute(text("DELETE FROM usuarios"))

        # Bulk insert con auditoría: audit.csv_path es la ruta del fichero CSV (el directorio se crea si falta)
        audit_csv = Path("audit_bulk") / "auditoria.csv"
        bcm = BulkCrud(engine=engine, audit=AuditOptions(csv_path=audit_csv))
        try:
            df = pd.read_csv(csv_input)
            bcm.bulk_insert_from_df(df, tabla_destino="usuarios", generar_sql=False)
        except DatabaseException as exc:
            print(f"Error de base de datos: {exc}")
            raise

        # === ANÁLISIS DE AUDITORÍA ===
        print("\n=== Audit Report ===")
        audit = AuditManager(audit_csv)
        df_audit = audit.leer_auditoria()  # el CSV es tabulado y con coma decimal: leerlo con AuditManager
        print(df_audit[["operacion", "tabla", "total_filas", "tiempo_seg", "timestamp"]].tail(1))

        stats = audit.obtener_estadisticas()
        print(f"\n✓ Operaciones registradas: {stats['total_operaciones']}")
        print(f"✓ Filas insertadas (última operación): {int(df_audit['total_filas'].iloc[-1])}")
        print(f"✓ Motor: {df_audit['motor'].iloc[-1]}")
    finally:
        # Limpieza
        csv_input.unlink(missing_ok=True)
        mgr.close()


if __name__ == "__main__":
    main()
