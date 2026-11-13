"""
Ejemplos ejecutables: Validación de Variables MySQL/MariaDB

Este módulo demuestra cómo usar MySQLVariableValidator y MySQLOptimalConfig.

Los ejemplos 1, 2 y 5 usan una conexión simulada (mock) que responde a ``SHOW VARIABLES WHERE Variable_name = '<nombre>'``,
así que no necesitan servidor. El ejemplo 6 crea una ``BulkCrud`` real si se define la variable de entorno
UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy de un MySQL o MariaDB de pruebas
(p. ej. ``mysql+pymysql://usuario:clave@servidor/bd``).

Uso:
    python mysql_variables_example.py
"""

import logging
import os

from unittest.mock import MagicMock

from util_bbdd.connection.mariadb import MySQLOptimalConfig, MySQLVariableValidator


def _mock_connection(values: dict[str, int]) -> MagicMock:
    """Conexión simulada: responde a SHOW VARIABLES WHERE Variable_name = '<nombre>' con el valor de ``values``."""

    def execute(statement: object) -> MagicMock:
        result = MagicMock()
        name = str(statement).split("'")[1]
        result.fetchall.return_value = [(name, str(values[name]))] if name in values else []
        return result

    connection = MagicMock()
    connection.execute.side_effect = execute
    return connection


# ============================================================================
# Función 1: Lectura de variables sin BulkCrud (standalone)
# ============================================================================


def example_1_standalone_read() -> None:
    """Lee variables MySQL sin usar BulkCrud."""
    print("\n" + "=" * 70)
    print("Ejemplo 1: Lectura Standalone de Variables MySQL")
    print("=" * 70)

    connection = _mock_connection({"max_allowed_packet": 67_108_864, "innodb_buffer_pool_size": 1_073_741_824})
    validator = MySQLVariableValidator(connection)
    vars_actual = validator.read_variables()

    print("\nVariables leídas desde servidor:")
    for name, value in sorted(vars_actual.items()):
        print(f"  {name}: {validator.format_bytes(value)}")


# ============================================================================
# Función 2: Validación contra configuración recomendada
# ============================================================================


def example_2_validate_against_recommended() -> None:
    """Valida variables actuales contra configuración recomendada."""
    print("\n" + "=" * 70)
    print("Ejemplo 2: Validación contra Configuración Recomendada")
    print("=" * 70)

    # Servidor con valores bajos: 16 MB y 256 MB
    connection = _mock_connection({"max_allowed_packet": 16_777_216, "innodb_buffer_pool_size": 268_435_456})
    validator = MySQLVariableValidator(connection)
    actual = validator.read_variables()

    # Recomendación para 1M filas
    recommended = MySQLOptimalConfig.suggest(num_rows=1_000_000)

    print("\nValores actuales:")
    for name, value in sorted(actual.items()):
        print(f"  {name}: {validator.format_bytes(value)}")

    print("\nValores recomendados (para 1M filas):")
    print(f"  innodb_buffer_pool_size: {validator.format_bytes(recommended.innodb_buffer_pool_size)}")
    print(f"  max_allowed_packet: {validator.format_bytes(recommended.max_allowed_packet)}")

    is_valid = validator.validate(
        {
            "max_allowed_packet": recommended.max_allowed_packet,
            "innodb_buffer_pool_size": recommended.innodb_buffer_pool_size,
        }
    )

    print("\nEstado de validación:")
    for var, valid in sorted(is_valid.items()):
        status = "✓ VÁLIDO" if valid else "✗ INSUFICIENTE"
        print(f"  {var}: {status}")


# ============================================================================
# Función 3: Perfiles de configuración
# ============================================================================


def example_3_configuration_profiles() -> None:
    """Demuestra los tres perfiles predefinidos."""
    print("\n" + "=" * 70)
    print("Ejemplo 3: Perfiles de Configuración Predefinidos")
    print("=" * 70)

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


def example_4_suggest_heuristic() -> None:
    """Demuestra la heurística de suggest() según número de filas."""
    print("\n" + "=" * 70)
    print("Ejemplo 4: Heurística de suggest() por Volumen de Datos")
    print("=" * 70)

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
# Función 5: Manejo de errores (conexión None)
# ============================================================================


def example_5_error_handling() -> None:
    """Demuestra cómo se manejan errores (ej. conexión None)."""
    print("\n" + "=" * 70)
    print("Ejemplo 5: Manejo de Errores")
    print("=" * 70)

    print("\nIntentando crear validador con connection=None...")
    try:
        MySQLVariableValidator(None)
        print("ERROR: Debería haber lanzado ValueError")
    except ValueError as e:
        print(f"✓ ValueError capturado: {e}")


# ============================================================================
# Función 6: BulkCrud revisando el servidor al crearse
# ============================================================================


def example_6_bulk_crud_auto_validation() -> None:
    """BulkCrud revisa el motor una vez por engine al crearse (EngineReadinessAdvisor)."""
    print("\n" + "=" * 70)
    print("Ejemplo 6: BulkCrud con Validación Automática")
    print("=" * 70)

    url = os.environ.get("UTIL_BBDD_EXAMPLE_URL")
    if not url:
        print("\nDefine UTIL_BBDD_EXAMPLE_URL (MySQL o MariaDB de pruebas) para ver el informe real.")
        print("Con un engine MySQL/MariaDB, BulkCrud(engine) registra un 'ENGINE READINESS REPORT' con")
        print("innodb_buffer_pool_size y max_allowed_packet (OK o WARN con el SET GLOBAL recomendado).")
        return

    from sqlalchemy import create_engine

    from util_bbdd import BulkCrud

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = create_engine(url)
    try:
        BulkCrud(engine)  # el informe sale en el log (INFO/WARNING) la primera vez por engine
    finally:
        engine.dispose()


# ============================================================================
# Main: Ejecutar todos los ejemplos
# ============================================================================


def main() -> None:
    """Ejecuta todos los ejemplos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + "  Ejemplos: Validación de Variables MySQL/MariaDB".center(68) + "║")
    print("╚" + "=" * 68 + "╝")

    example_1_standalone_read()
    example_2_validate_against_recommended()
    example_3_configuration_profiles()
    example_4_suggest_heuristic()
    example_5_error_handling()
    example_6_bulk_crud_auto_validation()

    print("\n" + "=" * 70)
    print("✓ Todos los ejemplos ejecutados correctamente")
    print("=" * 70)


if __name__ == "__main__":
    main()
