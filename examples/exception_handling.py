"""
Exception Handling — Patrones de manejo de errores

Este ejemplo muestra cómo:
1. Capturar excepciones específicas
2. Implementar retry logic
3. Loguear errores apropiadamente
4. Recuperarse de fallos
"""

import logging

from util_bbdd import DatabaseException, SyncDatabaseManager
from util_bbdd.exceptions import QueryTimeoutError, ValidationError

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)


def demonstrate_exception_handling():
    """Demostrar patrones de error handling."""

    # 1. Manejo básico de conexión
    print("1. Basic Connection Error Handling\n")

    try:
        SyncDatabaseManager(db_type="motor_no_soportado", conn_params={})
    except DatabaseException as e:
        logger.error(f"Configuration failed: {e}")
        print(f"   Error de configuracion capturado: {type(e).__name__}\n")

    # 2. Usar conexión exitosa (SQLite en memoria)
    manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"})

    manager.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")

    # 3. Manejo de errores de query
    print("2. Query Validation Errors\n")

    try:
        # Syntax error
        result = manager.execute_custom_many("SELECT * FORM test")  # Typo: FORM vs FROM
    except ValidationError as e:
        logger.warning(f"Query validation error: {e}")
        print("   Error de sintaxis detectado\n")
    except Exception:
        print("   Error de query capturado\n")

    # 4. Retry logic
    print("3. Retry Logic\n")

    def execute_with_retry(query, max_retries=3):
        """Ejecutar query con reintentos."""
        for attempt in range(1, max_retries + 1):
            try:
                result = manager.execute_custom_many(query)
                logger.info(f"Success on attempt {attempt}")
                return result
            except QueryTimeoutError:
                if attempt == max_retries:
                    logger.error(f"Failed after {max_retries} retries")
                    raise
                logger.warning(f"Timeout on attempt {attempt}, retrying...")
                print(f"   Reintento {attempt}...")

    result = execute_with_retry("SELECT 1", max_retries=3)
    if result:
        print("   Exito en reintento\n")

    # 5. Captura estratificada
    print("4. Layered Exception Handling\n")

    try:
        manager.execute_custom_many("INSERT INTO test VALUES (1, 'value')")
        manager.execute_custom_many("INSERT INTO test VALUES (1, 'duplicate')")  # Violación PK
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        print("   Error de validacion (PK duplicada)\n")
    except DatabaseException as e:
        logger.error(f"Database error: {e}")
        print("   Error de BD\n")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print("   Error inesperado\n")

    # 6. Context manager para cleanup automático
    print("5. Automatic Cleanup with Context Manager\n")

    try:
        with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as mgr:
            _ = mgr.execute_custom_many("SELECT 1")
            print("   Query ejecutada dentro de context manager")
    except Exception as e:
        logger.error(f"Error in context: {e}")
    print("   Conexion cerrada automaticamente\n")

    manager.close()


if __name__ == "__main__":
    demonstrate_exception_handling()
