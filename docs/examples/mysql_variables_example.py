"""
Ejemplos ejecutables: Validación de Variables MySQL/MariaDB

Este módulo demuestra cómo usar MySQLVariableValidator y MySQLOptimalConfig
en diferentes escenarios de producción.

Advertencia: Estos ejemplos usan conexiones mockeadas para no requerir
una BD real durante la ejecución. Reemplaza las conexiones mock con
conexiones reales según tu entorno.

Uso:
    python mysql_variables_example.py
"""

from unittest.mock import MagicMock

# ============================================================================
# Función 1: Lectura de variables sin BulkCrud (standalone)
# ============================================================================


def example_1_standalone_read():
    """Lee variables MySQL sin usar BulkCrud."""
    print("\n" + "=" * 70)
    print("Ejemplo 1: Lectura Standalone de Variables MySQL")
    print("=" * 70)

    # Simular conexión MySQL con mock
    from util_bbdd.connection.mariadb._variables import MySQLVariableValidator

    mock_connection = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.side_effect = [
        [("max_allowed_packet", "67108864")],  # 64 MB
        [("innodb_buffer_pool_size", "1073741824")],  # 1 GB
    ]
    mock_connection.execute.return_value = mock_result

    # Crear validador y leer
    validator = MySQLVariableValidator(mock_connection)
    vars_actual = validator.read_variables()

    print("\nVariables leídas desde servidor:")
    for name, value in vars_actual.items():
        mb = value / 1_048_576
        print(f"  {name}: {mb:.1f} MB")


# ============================================================================
# Función 2: Validación contra configuración recomendada
# ============================================================================


def example_2_validate_against_recommended():
    """Valida variables actuales contra configuración recomendada."""
    print("\n" + "=" * 70)
    print("Ejemplo 2: Validación contra Configuración Recomendada")
    print("=" * 70)

    from util_bbdd.connection.mariadb._config import MySQLOptimalConfig
    from util_bbdd.connection.mariadb._variables import MySQLVariableValidator

    # Mock: servidor con valores bajos
    mock_connection = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.side_effect = [
        [("max_allowed_packet", "16777216")],  # 16 MB (insuficiente)
        [("innodb_buffer_pool_size", "268435456")],  # 256 MB (insuficiente)
    ]
    mock_connection.execute.return_value = mock_result

    validator = MySQLVariableValidator(mock_connection)
    actual = validator.read_variables()

    # Obtener recomendación para 1M filas
    recommended = MySQLOptimalConfig.suggest(num_rows=1_000_000)

    print("\nValores actuales:")
    for name, value in actual.items():
        print(f"  {name}: {value / 1_048_576:.1f} MB")

    print("\nValores recomendados (para 1M filas):")
    print(f"  max_allowed_packet: {recommended.max_allowed_packet / 1_048_576:.1f} MB")
    print(f"  innodb_buffer_pool_size: {recommended.innodb_buffer_pool_size / 1_048_576:.1f} MB")

    # Validar
    is_valid = validator.validate(
        {
            "max_allowed_packet": recommended.max_allowed_packet,
            "innodb_buffer_pool_size": recommended.innodb_buffer_pool_size,
        }
    )

    print("\nEstado de validación:")
    for var, valid in is_valid.items():
        status = "✓ VÁLIDO" if valid else "✗ INSUFICIENTE"
        print(f"  {var}: {status}")


# ============================================================================
# Función 3: Perfiles de configuración
# ============================================================================


def example_3_configuration_profiles():
    """Demuestra los tres perfiles predefinidos."""
    print("\n" + "=" * 70)
    print("Ejemplo 3: Perfiles de Configuración Predefinidos")
    print("=" * 70)

    from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

    profiles = {
        "Desarrollo": MySQLOptimalConfig.dev(),
        "Producción": MySQLOptimalConfig.production(),
        "Alto Volumen": MySQLOptimalConfig.high_volume(),
    }

    print(f"\n{'Perfil':<15} {'max_allowed_packet':<20} {'innodb_buffer_pool_size':<20}")
    print("-" * 55)

    for name, config in profiles.items():
        packet_mb = config.max_allowed_packet / 1_048_576
        pool_mb = config.innodb_buffer_pool_size / 1_048_576
        print(f"{name:<15} {packet_mb:>6.0f} MB         {pool_mb:>6.0f} MB")


# ============================================================================
# Función 4: Heurística de suggest() por volumen de datos
# ============================================================================


def example_4_suggest_heuristic():
    """Demuestra la heurística de suggest() según número de filas."""
    print("\n" + "=" * 70)
    print("Ejemplo 4: Heurística de suggest() por Volumen de Datos")
    print("=" * 70)

    from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

    test_cases = [
        (50_000, "Local (< 50K)"),
        (500_000, "Staging (100K–1M)"),
        (2_000_000, "Producción (> 1M)"),
        (50_000_000, "Migración masiva"),
    ]

    print(f"\n{'Filas':<15} {'Escenario':<25} {'max_allowed_packet':<20} {'innodb_buffer_pool_size':<20}")
    print("-" * 80)

    for num_rows, scenario in test_cases:
        config = MySQLOptimalConfig.suggest(num_rows=num_rows)
        packet_mb = config.max_allowed_packet / 1_048_576
        pool_gb = config.innodb_buffer_pool_size / 1_073_741_824
        print(f"{num_rows:<15,} {scenario:<25} {packet_mb:>6.0f} MB         {pool_gb:>6.1f} GB")


# ============================================================================
# Función 5: Simulación de error (conexión None)
# ============================================================================


def example_5_error_handling():
    """Demuestra cómo se manejan errores (ej. conexión None)."""
    print("\n" + "=" * 70)
    print("Ejemplo 5: Manejo de Errores")
    print("=" * 70)

    from util_bbdd.connection.mariadb._variables import MySQLVariableValidator

    print("\nIntentando crear validador con connection=None...")
    try:
        validator = MySQLVariableValidator(None)
        print("ERROR: Debería haber lanzado ValueError")
    except ValueError as e:
        print(f"✓ ValueError capturado: {e}")


# ============================================================================
# Función 6: Simulación de BulkCrud validando automáticamente
# ============================================================================


def example_6_bulk_crud_auto_validation():
    """Simula BulkCrud con validación automática de MySQL."""
    print("\n" + "=" * 70)
    print("Ejemplo 6: BulkCrud con Validación Automática")
    print("=" * 70)

    # Mock de engine MySQL
    mock_engine = MagicMock()
    mock_engine.dialect.name = "mysql"

    mock_connection = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall.side_effect = [
        [("max_allowed_packet", "67108864")],  # 64 MB
        [("innodb_buffer_pool_size", "1073741824")],  # 1 GB
    ]
    mock_connection.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Nota: Aquí simularíamos el init de BulkCrud, pero en un entorno real:
    # bulk = BulkCrud(engine=mock_engine)
    # En su __init__, automáticamente:
    # 1. Detectaría motor = 'mysql'
    # 2. Crearía MySQLVariableValidator
    # 3. Leería variables y validaría
    # 4. Emitiría logs INFO/WARNING

    print("\nEn un escenario real con BulkCrud(engine), verías logs como:")
    print("INFO: MySQL variables: max_allowed_packet=64 MB, innodb_buffer_pool_size=1 GB")
    print("INFO: Configuración óptima para ~1M filas: max_allowed_packet=64 MB, innodb_buffer_pool_size=1 GB")


# ============================================================================
# Main: Ejecutar todos los ejemplos
# ============================================================================


def main():
    """Ejecuta todos los ejemplos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Ejemplos: Validación de Variables MySQL/MariaDB (v0.10.0+)".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        example_1_standalone_read()
        example_2_validate_against_recommended()
        example_3_configuration_profiles()
        example_4_suggest_heuristic()
        example_5_error_handling()
        example_6_bulk_crud_auto_validation()

        print("\n" + "=" * 70)
        print("✓ Todos los ejemplos ejecutados correctamente")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\n✗ Error durante ejecución: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
