"""
Ejemplo de uso de las clases de consultas de base de datos separadas
"""

from pathlib import Path

from conn_params_builder import build_conn_params
from database_manager import DatabaseManager
from database_queries import DatabaseQueries


def ejemplo_uso_database_queries():
    """Ejemplo de uso de la clase DatabaseQueries"""
    print("=== Ejemplo de DatabaseQueries ===")

    # Inicializar gestor de consultas para PostgreSQL
    queries = DatabaseQueries("postgresql")

    # Obtener consulta de tablas
    query_tablas = queries.get_tables_query("public")
    print(f"Consulta de tablas: {query_tablas}")

    # Obtener consulta de columnas
    query_columnas = queries.get_columns_query("public", "usuarios")
    print(f"Consulta de columnas: {query_columnas}")

    # Validar parámetros de consulta
    es_valido = queries.validate_query_parameters("obtener_tablas", database="public")
    print(f"¿Parámetros válidos?: {es_valido}")

    # Obtener información de consultas
    info = queries.get_query_info()
    print(f"Total de consultas: {info['total_queries']}")
    print(f"Nombres disponibles: {info['query_names']}")


def ejemplo_uso_query_executor():
    """Ejemplo de uso de DatabaseQueryExecutor con una conexión simulada"""
    print("\n=== Ejemplo de DatabaseQueryExecutor ===")

    # Nota: Este ejemplo requiere una conexión real
    # Aquí solo mostramos la estructura

    queries = DatabaseQueries("postgresql")

    # Simulación de parámetros de conexión
    conn_params = build_conn_params(
        "postgresql",
        host="localhost",
        port=5432,
        database="test_db",
        user="postgres",
        password="password",
        schema="public",
    )

    print("Para usar DatabaseQueryExecutor, necesitarías:")
    print("1. Una conexión real a la base de datos")
    print("2. Un cursor de esa conexión")
    print("3. Una instancia de DatabaseQueries")

    # Ejemplo teórico:
    # conn_params["database"] = "public"
    # db = DatabaseManager("postgresql", conn_params)
    # resultados = db.get_tables()
    # print(f"Tablas encontradas: {resultados}")


def ejemplo_uso_database_manager_refactorizado():
    """Ejemplo de uso del DatabaseManager refactorizado"""
    print("\n=== Ejemplo de DatabaseManager Refactorizado ===")

    # Parámetros de conexión (ejemplo PostgreSQL)
    conn_params = build_conn_params(
        "postgresql",
        host="localhost",
        port=5432,
        user="postgres",
        password="password",
        database="postgres",
        schema="public",
    )

    try:
        # Crear gestor de base de datos
        db_manager = DatabaseManager(
            db_type="postgresql",
            conn_params=conn_params,
        )

        print("✅ Conexión establecida exitosamente")

        # Obtener información de la base de datos
        info = db_manager.get_database_info()
        print(f"Tipo de BD: {info['db_type']}")
        print(f"Estado: {info['connection_status']}")
        print(f"Consultas disponibles: {info['available_queries']}")

        # Ejecutar algunas consultas
        print("\n--- Consultas Disponibles ---")
        for query_name in db_manager.get_available_queries():
            print(f"- {query_name}")

        # Cerrar conexión
        db_manager.close()
        print("✅ Conexión cerrada")

    except Exception as e:
        print(f"❌ Error: {e}")


def ejemplo_beneficios_separacion():
    """Demostración de los beneficios de separar las consultas"""
    print("\n=== Beneficios de la Separación ===")

    print("1. ✅ Separación de responsabilidades:")
    print("   - DatabaseQueries: Gestiona las consultas SQL")
    print("   - DatabaseQueryExecutor: Ejecuta consultas")
    print("   - DatabaseManager: Gestiona conexiones y delega")

    print("\n2. ✅ Reutilización de consultas:")
    queries = DatabaseQueries("postgresql")
    print(f"   - Consultas disponibles: {len(queries.get_available_query_names())}")

    print("\n3. ✅ Validación de parámetros:")
    es_valido = queries.validate_query_parameters("obtener_tablas", database="public")
    print(f"   - Validación de parámetros: {es_valido}")

    print("\n4. ✅ Información de consultas:")
    info = queries.get_query_info()
    print(f"   - Total consultas: {info['total_queries']}")

    print("\n5. ✅ Flexibilidad:")
    print("   - Fácil agregar nuevos tipos de consultas")
    print("   - Fácil modificar consultas existentes")
    print("   - Fácil añadir validaciones adicionales")


def ejemplo_extension_personalizada():
    """Ejemplo de cómo extender el sistema con consultas personalizadas"""
    print("\n=== Ejemplo de Extensión Personalizada ===")

    # Crear un archivo JSON personalizado con consultas adicionales
    custom_queries = {
        "postgresql": {
            "tablas_con_mas_filas": """
                SELECT table_name, n_tup_ins - n_tup_upd as estimated_rows
                FROM pg_stat_user_tables
                ORDER BY estimated_rows DESC
                LIMIT 10
            """,
            "tablas_con_indices": """
                SELECT t.table_name, COUNT(i.indexname) as index_count
                FROM pg_tables t
                LEFT JOIN pg_indexes i ON t.tablename = i.tablename
                WHERE t.schemaname = '{database}'
                GROUP BY t.table_name
                ORDER BY index_count DESC
            """
        }
    }

    # Guardar consultas personalizadas
    import json
    custom_queries_path = Path("custom_queries.json")
    with open(custom_queries_path, "w") as f:
        json.dump(custom_queries, f, indent=2)

    print("✅ Archivo de consultas personalizadas creado")

    # Usar consultas personalizadas
    queries = DatabaseQueries("postgresql", custom_queries_path)

    print("Consultas personalizadas disponibles:")
    for query_name in queries.get_available_query_names():
        if query_name not in ["obtener_tablas", "columnas_tabla", "create_table", "indices", "claves_primarias", "claves_foraneas", "claves_unicas"]:
            print(f"  - {query_name}")

    # Validar y obtener consulta personalizada
    es_valido = queries.validate_query_parameters("tablas_con_mas_filas")
    print(f"¿Consulta válida?: {es_valido}")

    if es_valido:
        query = queries.get_query("tablas_con_mas_filas")
        print(f"Consulta SQL: {query.strip()}")

    # Limpiar
    custom_queries_path.unlink(missing_ok=True)
    print("✅ Archivo temporal eliminado")


if __name__ == "__main__":
    """Función principal que ejecuta todos los ejemplos"""
    print("🚀 Ejemplos de Uso de Clases de Base de Datos Separadas")
    print("=" * 60)

    ejemplo_uso_database_queries()
    ejemplo_uso_query_executor()
    ejemplo_uso_database_manager_refactorizado()
    ejemplo_beneficios_separacion()
    ejemplo_extension_personalizada()

    print("\n🎯 Resumen:")
    print("1. DatabaseQueries: Gestiona plantillas SQL y validación")
    print("2. DatabaseQueryExecutor: Ejecuta consultas con conexión real")
    print("3. DatabaseManager: Orquesta conexión y delega consultas")
    print("4. Arquitectura más limpia, mantenible y extensible")
    print("5. Fácil agregar nuevos tipos de consultas y validaciones")
