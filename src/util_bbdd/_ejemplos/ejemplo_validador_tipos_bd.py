"""
Ejemplo de uso del validador de tipos de bases de datos y DatabaseManager mejorado
"""

from conn_params_builder import build_conn_params
from database_manager import DatabaseManager
from database_type_validator import DatabaseTypeValidator


def ejemplo_validador_tipos_bd():
    """Ejemplo de uso del validador de tipos de bases de datos"""
    print("=== Ejemplo de DatabaseTypeValidator ===")

    # Crear validador
    validator = DatabaseTypeValidator()

    # Obtener tipos soportados
    print(f"Tipos soportados: {validator.get_supported_db_types()}")

    # Validar tipos
    print("\n--- Validación de Tipos ---")
    for db_type in ["postgresql", "mysql", "oracle"]:
        try:
            validator.validate_db_type(db_type)
            print(f"✅ {db_type}: Válido")
        except ValueError as e:
            print(f"❌ {db_type}: {e}")

    # Obtener información de PostgreSQL
    print("\n--- Información de PostgreSQL ---")
    pg_info = validator.get_db_type_info("postgresql")
    print(f"Nombre: {pg_info.get('name')}")
    print(f"Descripción: {pg_info.get('description')}")
    print(f"Puerto por defecto: {pg_info.get('default_port')}")
    print(f"Características: {len(pg_info.get('supported_features', []))}")

    # Parámetros de conexión
    print("\n--- Parámetros de Conexión PostgreSQL ---")
    required = validator.get_required_params("postgresql")
    optional = validator.get_optional_params("postgresql")
    print(f"Requeridos: {required}")
    print(f"Opcionales: {[p.get('name') for p in optional]}")

    # Validar parámetros
    print("\n--- Validación de Parámetros ---")
    conn_params_valid = {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "password",
        "database": "testdb"
    }

    conn_params_invalid = {
        "host": "localhost",
        "user": "postgres"
        # Faltan password y database
    }

    try:
        validator.validate_connection_params("postgresql", conn_params_valid)
        print("✅ Parámetros válidos")
    except ValueError as e:
        print(f"❌ Parámetros inválidos: {e}")

    try:
        validator.validate_connection_params("postgresql", conn_params_invalid)
        print("✅ Parámetros válidos")
    except ValueError as e:
        print(f"❌ Parámetros inválidos: {e}")


def ejemplo_database_manager_mejorado():
    """Ejemplo de uso del DatabaseManager mejorado con validación"""
    print("\n=== Ejemplo de DatabaseManager Mejorado ===")

    # Parámetros de conexión PostgreSQL
    conn_params = build_conn_params(
        "postgresql",
        host="localhost",
        port=5432,
        user="postgres",
        password="password",
        database="testdb",
        schema="public",
    )

    try:
        # Crear gestor de base de datos
        db_manager = DatabaseManager(
            db_type="postgresql",
            conn_params=conn_params,
        )

        print("✅ Conexión establecida exitosamente")

        # Obtener información del tipo de base de datos
        print("\n--- Información del Tipo de Base de Datos ---")
        db_info = db_manager.get_database_type_info()
        print(f"Tipo: {db_info.get('name')}")
        print(f"Descripción: {db_info.get('description')}")
        print(f"Versión soportada: {db_info.get('version_range')}")

        # Obtener información del driver
        print("\n--- Información del Driver ---")
        driver_info = db_manager.get_database_type_driver_info()
        print(f"Paquete: {driver_info.get('pip_package')}")
        print(f"Instalación: {driver_info.get('install_command')}")

        # Obtener parámetros de conexión
        print("\n--- Parámetros de Conexión ---")
        required = db_manager.get_required_params()
        optional = db_manager.get_optional_params()
        print(f"Requeridos: {required}")
        print(f"Opcionales: {len(optional)} parámetros")

        # Obtener características soportadas
        print("\n--- Características Soportadas ---")
        features = db_manager.get_database_type_features()
        for i, feature in enumerate(features[:5], 1):
            print(f"  {i}. {feature}")
        if len(features) > 5:
            print(f"  ... y {len(features) - 5} más")

        # Obtener información completa
        print("\n--- Información Completa de la Base de Datos ---")
        complete_info = db_manager.get_database_info()
        print(f"Tipo BD: {complete_info['db_type']}")
        print(f"Nombre BD: {complete_info['db_type_name']}")
        print(f"Estado: {complete_info['connection_status']}")
        print(f"Consultas disponibles: {len(complete_info['available_queries'])}")

        # Cerrar conexión
        db_manager.close()
        print("\n✅ Conexión cerrada")

    except Exception as e:
        print(f"❌ Error: {e}")


def ejemplo_errores_validacion():
    """Ejemplo de manejo de errores de validación"""
    print("\n=== Ejemplo de Errores de Validación ===")

    validator = DatabaseTypeValidator()

    # Error 1: Tipo no soportado
    print("--- Error 1: Tipo no soportado ---")
    try:
        validator.validate_db_type("mongodb")
    except ValueError as e:
        print(f"✅ Error capturado: {e}")

    # Error 2: Parámetros faltantes
    print("\n--- Error 2: Parámetros faltantes ---")
    try:
        validator.validate_connection_params("postgresql", {"host": "localhost"})
    except ValueError as e:
        print(f"✅ Error capturado: {e}")

    # Error 3: Parámetros inválidos para DatabaseManager
    print("\n--- Error 3: DatabaseManager con parámetros inválidos ---")
    try:
        db_manager = DatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost", "database": "testdb"},  # Parámetros incompletos
        )
    except ValueError as e:
        print(f"✅ Error capturado: {e}")


def ejemplo_funciones_estaticas():
    """Ejemplo de uso de funciones estáticas"""
    print("\n=== Ejemplo de Funciones Estáticas ===")

    # Métodos estáticos de DatabaseManager
    print("--- Métodos Estáticos de DatabaseManager ---")
    supported = DatabaseManager.get_supported_db_types()
    print(f"Tipos soportados: {supported}")

    is_supported = DatabaseManager.is_db_type_supported("postgresql")
    print(f"¿PostgreSQL soportado?: {is_supported}")

    try:
        DatabaseManager.validate_db_type_static("postgresql")
        print("✅ Validación estática exitosa")
    except ValueError as e:
        print(f"❌ Error: {e}")

    # Funciones de conveniencia
    print("\n--- Funciones de Conveniencia ---")
    from database_type_validator import get_db_type_info, validate_db_type

    try:
        validate_db_type("postgresql")
        print("✅ Validación de conveniencia exitosa")
    except ValueError as e:
        print(f"❌ Error: {e}")

    info = get_db_type_info("postgresql")
    print(f"Info de conveniencia: {info.get('name')}")


def ejemplo_parametros_opcionales():
    """Ejemplo de uso de parámetros opcionales"""
    print("\n=== Ejemplo de Parámetros Opcionales ---")

    validator = DatabaseTypeValidator()

    # Obtener información de parámetros opcionales de PostgreSQL
    optional_params = validator.get_optional_params("postgresql")

    print("--- Parámetros Opcionales de PostgreSQL ---")
    for param in optional_params:
        name = param.get("name")
        param_type = param.get("type")
        default = param.get("default")
        description = param.get("description")

        print(f"\n📋 {name}")
        print(f"   Tipo: {param_type}")
        print(f"   Default: {default}")
        print(f"   Descripción: {description}")

    # Ejemplo de configuración completa
    print("\n--- Ejemplo de Configuración Completa ---")
    complete_config = {
        # Parámetros requeridos
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secure_password",
        "database": "production_db",

        # Parámetros opcionales
        "sslmode": "require",
        "application_name": "Database Manager",
        "connect_timeout": 20,
        "keepalives": True
    }

    try:
        validator.validate_connection_params("postgresql", complete_config)
        print("✅ Configuración completa válida")
    except ValueError as e:
        print(f"❌ Error: {e}")


def ejemplo_ejemplos_configuracion():
    """Ejemplo de uso de ejemplos de configuración"""
    print("\n=== Ejemplo de Configuración desde JSON ---")

    validator = DatabaseTypeValidator()

    # Obtener ejemplos para cada tipo de base de datos
    for db_type in validator.get_supported_db_types():
        print(f"\n--- Ejemplos para {db_type.upper()} ---")
        examples = validator.get_db_type_examples(db_type)

        for example_name, example_config in examples.items():
            print(f"\n📝 {example_name}:")
            for key, value in example_config.items():
                if key == "password":
                    print(f"   {key}: {'*' * len(str(value))}")
                else:
                    print(f"   {key}: {value}")


def ejemplo_mensajes_error():
    """Ejemplo de uso de mensajes de error personalizados"""
    print("\n=== Ejemplo de Mensajes de Error Personalizados ---")

    validator = DatabaseTypeValidator()

    # Usar mensajes de error del JSON
    print("--- Mensajes de Error del JSON ---")

    try:
        validator.validate_db_type("tipo_inexistente")
    except ValueError as e:
        print(f"✅ Mensaje personalizado: {e}")

    # Obtener mensaje de error específico
    error_msg = validator.get_error_message(
        "unsupported_db_type",
        db_type="tipo_inexistente",
        supported_types=", ".join(validator.get_supported_db_types())
    )
    print(f"Mensaje formateado: {error_msg}")


if __name__ == "__main__":
    """Función principal que ejecuta todos los ejemplos"""
    print("🚀 Ejemplos de Validador de Tipos de Base de Datos y DatabaseManager Mejorado")
    print("=" * 80)

    ejemplo_validador_tipos_bd()
    ejemplo_database_manager_mejorado()
    ejemplo_errores_validacion()
    ejemplo_funciones_estaticas()
    ejemplo_parametros_opcionales()
    ejemplo_ejemplos_configuracion()
    ejemplo_mensajes_error()

    print("\n🎯 Resumen de Mejoras:")
    print("1. ✅ Validación de tipos de base de datos desde JSON")
    print("2. ✅ Validación de parámetros de conexión")
    print("3. ✅ Información detallada de cada tipo de BD")
    print("4. ✅ Mensajes de error personalizados")
    print("5. ✅ Ejemplos de configuración incluidos")
    print("6. ✅ Funciones estáticas para conveniencia")
    print("7. ✅ Compatibilidad total con código existente")
    print("8. ✅ Documentación completa y metadatos")
