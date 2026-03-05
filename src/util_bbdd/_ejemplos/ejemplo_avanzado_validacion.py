"""
Ejemplos avanzados de uso del sistema mejorado de validación y consultas
"""

from pathlib import Path

from database_queries import create_advanced_queries
from database_type_validator import DatabaseTypeValidator


def ejemplo_consultas_avanzadas():
    """Ejemplo de uso de consultas avanzadas con validación mejorada"""
    print("=== Ejemplo de DatabaseQueries (Unificado) ===")

    try:
        # Crear consultas avanzadas con validación automática
        queries = create_advanced_queries("postgresql")

        print("✅ Consultas avanzadas inicializadas")

        # Obtener metadatos del tipo de base de datos
        metadata = queries.get_database_metadata()
        print(f"Tipo de BD: {metadata['name']}")
        print(f"Descripción: {metadata['description'][:80]}...")
        print(f"Características: {len(metadata['supported_features'])}")

        # Obtener requisitos del driver
        driver_reqs = queries.get_driver_requirements()
        print("\n--- Requisitos del Driver ---")
        print(f"Paquete: {driver_reqs['pip_package']}")
        print(f"Instalación: {driver_reqs['install_command']}")
        print(f"Requisitos del sistema: {driver_reqs['system_requirements']}")

        # Obtener ejemplos de conexión
        examples = queries.get_connection_examples()
        print("\n--- Ejemplos de Conexión ---")
        for example_name, example_config in examples.items():
            print(f"\n📝 {example_name}:")
            for key, value in example_config.items():
                if key == "password":
                    print(f"   {key}: {'*' * 8}")
                else:
                    print(f"   {key}: {value}")

        # Validar una consulta específica
        print("\n--- Validación de Consultas ---")
        is_valid, errors = queries.validate_query_for_db_type("columnas_tabla", database="public", tabla="usuarios")

        if is_valid:
            print("✅ Consulta válida")
        else:
            print("❌ Consulta con errores:")
            for error in errors:
                print(f"   - {error}")

        # Obtener dependencias de una consulta
        deps = queries.get_query_dependencies("columnas_tabla")
        print("\n--- Dependencias de Consulta ---")
        print(f"Tablas involucradas: {deps['tables']}")
        print(f"Schemas: {deps['schemata']}")

        # Obtener sugerencias de rendimiento
        perf_hints = queries.get_query_performance_hints("obtener_tablas")
        print("\n--- Sugerencias de Rendimiento ---")
        print(f"Complejidad: {perf_hints['complexity']}")
        print("Recomendaciones:")
        for rec in perf_hints["recommendations"]:
            print(f"   • {rec}")

        # Obtener documentación completa de una consulta
        docs = queries.get_query_documentation("columnas_tabla")
        print("\n--- Documentación de Consulta ---")
        print(f"Nombre: {docs['query_name']}")
        print(f"Descripción: {docs['description']}")
        print(f"Parámetros requeridos: {docs['parameters']}")

        print("Ejemplos de uso:")
        for example in docs["examples"]:
            print(f"   • {example['description']}")
            print(f"     Parámetros: {example['parameters']}")

    except Exception as e:
        print(f"❌ Error: {e}")


def ejemplo_validacion_sintaxis_sql():
    """Ejemplo de validación de sintaxis SQL"""
    print("\n=== Ejemplo de Validación de Sintaxis SQL ===")

    from advanced_database_queries import create_query_validator

    # Crear validador de consultas
    validator = create_query_validator("postgresql")

    # Casos de prueba
    test_queries = [
        ("SELECT * FROM usuarios", "Consulta simple válida"),
        ("SELECT nombre, email FROM usuarios WHERE edad > 18", "Consulta con WHERE válida"),
        ("SELECT * FROM usuarios WHERE", "Consulta incompleta"),
        ("SELECT * FROM usuarios WHERE nombre LIKE '%test'", "Consulta con patrón ineficiente"),
        ("SELECT * FROM usuarios ORDER BY nombre LIMIT 10", "Consulta con ORDER BY y LIMIT"),
        ("SELECT * FROM usuarios WHERE (nombre = 'test'", "Paréntesis desbalanceados"),
    ]

    for sql, description in test_queries:
        print(f"\n--- {description} ---")
        print(f"SQL: {sql}")

        is_valid, errors = validator.validate_sql_syntax(sql)

        if is_valid:
            print("✅ Sintaxis válida")
        else:
            print("❌ Sintaxis inválida:")
            for error in errors:
                print(f"   • {error}")

        # Obtener sugerencias de optimización
        suggestions = validator.suggest_query_optimizations(sql)
        if suggestions:
            print("💡 Sugerencias de optimización:")
            for suggestion in suggestions:
                print(f"   • {suggestion}")


def ejemplo_documentacion_personalizada():
    """Ejemplo de generación de documentación personalizada"""
    print("\n=== Ejemplo de Documentación Personalizada ===")

    try:
        queries = create_advanced_queries("postgresql")

        # Exportar documentación completa
        output_file = Path("postgres_queries_documentation.json")
        queries.export_queries_documentation(output_file)
        print(f"✅ Documentación exportada a: {output_file}")

        # Mostrar resumen de la documentación
        docs_content = {
            "db_type": "postgresql",
            "total_queries": len(queries.get_available_query_names()),
            "db_features": len(queries.get_database_metadata().get("supported_features", [])),
        }

        print("--- Resumen de Documentación ---")
        print(f"Tipo de BD: {docs_content['db_type']}")
        print(f"Total de consultas: {docs_content['total_queries']}")
        print(f"Características soportadas: {docs_content['db_features']}")

        # Limpiar archivo temporal
        if output_file.exists():
            output_file.unlink()

    except Exception as e:
        print(f"❌ Error: {e}")


def ejemplo_wizard_configuracion():
    """Ejemplo de asistente de configuración inteligente"""
    print("\n=== Asistente de Configuración Inteligente ===")

    validator = DatabaseTypeValidator()

    # 1. Seleccionar tipo de base de datos con información
    print("Tipos de bases de datos disponibles:")
    db_types = validator.get_supported_db_types()

    for i, db_type in enumerate(db_types, 1):
        info = validator.get_db_type_info(db_type)
        print(f"{i}. {info['name']}")
        print(f"   {info['description'][:60]}...")
        print(f"   Características: {len(info['supported_features'])}")
        print(f"   Puerto por defecto: {info['default_port']}")
        print()

    # 2. Configurar según tipo seleccionado (simulamos PostgreSQL)
    selected_type = "postgresql"

    # 3. Obtener información detallada del tipo seleccionado
    info = validator.get_db_type_info(selected_type)
    print(f"--- Configurando {info['name']} ---")

    # 4. Validar requisitos del sistema
    driver_info = info.get("driver_info", {})
    system_reqs = driver_info.get("system_requirements", [])

    if system_reqs:
        print("Requisitos del sistema:")
        for req in system_reqs:
            print(f"   • {req}")

    # 5. Generar configuración con validación
    required_params = validator.get_required_params(selected_type)
    optional_params = validator.get_optional_params(selected_type)

    config = {}

    # Parámetros requeridos con validación
    print(f"\nParámetros requeridos para {info['name']}:")
    for param in required_params:
        while True:
            value = input(f"{param}: ").strip()
            if value:
                config[param] = value
                break
            else:
                print(f"❌ {param} es requerido")

    # Parámetros opcionales con defaults
    print("\nParámetros opcionales (presione Enter para usar defaults):")
    for param_info in optional_params:
        param_name = param_info["name"]
        default_value = param_info.get("default")
        param_type = param_info.get("type")

        prompt = f"{param_name}"
        if default_value:
            prompt += f" [{default_value}]"
        prompt += ": "

        value = input(prompt).strip()

        if not value and default_value:
            value = default_value

        # Validar tipo
        if value and param_type == "integer":
            try:
                value = int(value)
            except ValueError:
                print(f"⚠️  Usando valor por defecto para {param_name}")
                value = default_value

        if value:
            config[param_name] = value

    # 6. Validar configuración completa
    try:
        validator.validate_connection_params(selected_type, config)
        print("✅ Configuración válida")

        # 7. Probar conexión (simulada)
        print("\n--- Intentando conectar ---")
        print(f"Tipo: {selected_type}")
        print(f"Configuración: {config}")

        # Aquí iría la conexión real:
        # config["database"] = "public"
        # db_manager = DatabaseManager(selected_type, config)

        print("✅ Configuración completada exitosamente")

        # 8. Guardar configuración
        import json

        config_file = Path("database_config.json")
        with open(config_file, "w") as f:
            json.dump(
                {"db_type": selected_type, "connection_params": config, "generated_at": "2024-01-28", "description": f"Configuración generada para {info['name']}"}, f, indent=2
            )

        print(f"📁 Configuración guardada en: {config_file}")

    except ValueError as e:
        print(f"❌ Error de validación: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")


def ejemplo_comparacion_tipos_bd():
    """Ejemplo de comparación entre tipos de bases de datos"""
    print("\n=== Comparación de Tipos de Bases de Datos ===")

    validator = DatabaseTypeValidator()
    supported_types = validator.get_supported_db_types()

    # Tabla comparativa
    comparison = {}

    for db_type in supported_types:
        info = validator.get_db_type_info(db_type)
        comparison[db_type] = {
            "name": info.get("name", ""),
            "description": info.get("description", ""),
            "default_port": info.get("default_port", 0),
            "features_count": len(info.get("supported_features", [])),
            "required_params": len(validator.get_required_params(db_type)),
            "optional_params": len(validator.get_optional_params(db_type)),
            "driver_package": info.get("driver_info", {}).get("pip_package", ""),
        }

    # Mostrar tabla comparativa
    print(f"{'Tipo':<12} {'Nombre':<12} {'Puerto':<8} {'Features':<10} {'Params':<12} {'Driver':<20}")
    print("-" * 80)

    for db_type, data in comparison.items():
        params_total = data["required_params"] + data["optional_params"]
        print(f"{db_type:<12} {data['name']:<12} {data['default_port']:<8} {data['features_count']:<10} {params_total:<12} {data['driver_package']:<20}")

    # Detalles de características
    print("\n--- Características por Tipo de BD ---")
    for db_type in supported_types:
        info = validator.get_db_type_info(db_type)
        features = info.get("supported_features", [])

        print(f"\n{info['name']} ({db_type}):")
        print(f"  Características ({len(features)}):")
        for i, feature in enumerate(features[:5], 1):
            print(f"    {i}. {feature}")
        if len(features) > 5:
            print(f"    ... y {len(features) - 5} más")


def ejemplo_analisis_rendimiento():
    """Ejemplo de análisis de rendimiento de consultas"""
    print("\n=== Análisis de Rendimiento de Consultas ---")

    queries = create_advanced_queries("postgresql")
    validator = queries.db_validator

    # Consultas de ejemplo para análisis
    example_queries = [
        {"name": "Consulta Simple", "sql": "SELECT id, nombre FROM productos WHERE activo = true", "table": "productos"},
        {
            "name": "Consulta Compleja",
            "sql": """
                SELECT p.id, p.nombre, c.nombre as categoria, COUNT(v.id) as ventas
                FROM productos p
                JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN ventas v ON v.producto_id = p.id
                WHERE p.precio > 100 AND p.fecha_creacion >= '2024-01-01'
                GROUP BY p.id, p.nombre, c.nombre
                ORDER BY ventas DESC
                LIMIT 50
            """,
            "table": "productos",
        },
        {"name": "Consulta Potencialmente Lenta", "sql": "SELECT * FROM ventas WHERE cliente_nombre LIKE '%juan%'", "table": "ventas"},
    ]

    from advanced_database_queries import create_query_validator

    query_validator = create_query_validator("postgresql")

    for query_info in example_queries:
        print(f"\n--- {query_info['name']} ---")
        print(f"SQL: {query_info['sql'].strip()}")

        # Validar sintaxis
        is_valid, errors = query_validator.validate_sql_syntax(query_info["sql"])

        if is_valid:
            print("✅ Sintaxis válida")

            # Obtener sugerencias de optimización
            suggestions = query_validator.suggest_query_optimizations(query_info["sql"])
            if suggestions:
                print("💡 Sugerencias de optimización:")
                for suggestion in suggestions:
                    print(f"   • {suggestion}")

            # Analizar complejidad basada en cláusulas
            sql_upper = query_info["sql"].upper()
            complexity_score = 0

            if "WHERE" in sql_upper:
                complexity_score += 1
            if "JOIN" in sql_upper:
                complexity_score += 2
                joins = sql_upper.count("JOIN")
                complexity_score += joins
            if "GROUP BY" in sql_upper:
                complexity_score += 2
            if "ORDER BY" in sql_upper:
                complexity_score += 1
            if "SUBQUERY" in sql_upper or "SELECT" in sql_upper and sql_upper.count("SELECT") > 1:
                complexity_score += 3

            print(f"📊 Puntuación de complejidad: {complexity_score}")

            if complexity_score <= 2:
                print("🟢 Complejidad baja - Buena para producción")
            elif complexity_score <= 5:
                print("🟡 Complejidad media - Considerar optimización")
            else:
                print("🔴 Complejidad alta - Requiere optimización")

        else:
            print("❌ Sintaxis inválida:")
            for error in errors:
                print(f"   • {error}")


if __name__ == "__main__":
    """Función principal que ejecuta todos los ejemplos avanzados"""
    print("🚀 Ejemplos Avanzados del Sistema de Validación y Consultas")
    print("=" * 80)

    ejemplo_consultas_avanzadas()
    ejemplo_validacion_sintaxis_sql()
    ejemplo_documentacion_personalizada()
    ejemplo_wizard_configuracion()
    ejemplo_comparacion_tipos_bd()
    ejemplo_analisis_rendimiento()

    print("\n🎯 Resumen de Características Avanzadas:")
    print("1. ✅ Validación avanzada de consultas SQL")
    print("2. ✅ Análisis de rendimiento y optimización")
    print("3. ✅ Generación automática de documentación")
    print("4. ✅ Asistente inteligente de configuración")
    print("5. ✅ Comparación entre tipos de bases de datos")
    print("6. ✅ Sugerencias de optimización personalizadas")
    print("7. ✅ Integración completa con database_types.json")
    print("8. ✅ Extensionibilidad y personalización")
