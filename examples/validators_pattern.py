"""
Patrón de Validadores — Validación de parámetros de query por motor

Este ejemplo muestra cómo:
1. Obtener el validador de un motor con la factory `get_type_validator`
2. Validar parámetros contra una `QueryDefinition` (caso válido)
3. Detectar parámetros requeridos ausentes o vacíos (caso inválido)
4. Recibir advertencias (warnings) sin invalidar la query
5. Manejar un motor no soportado (ValueError de la factory)
6. Comprobar el cacheo de instancias de la factory

No requiere servidor de BD: solo construye definiciones y valida en memoria.
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators import get_type_validator


def demonstrate_validators() -> None:
    """Demostrar el patrón de validadores por motor."""

    # 1. Factory: obtener el validador del motor
    print("1. Factory de validadores\n")
    validator = get_type_validator("sqlite")
    print(f"   db_type del validador: {validator.db_type}")
    print(f"   clase: {type(validator).__name__}\n")

    # Definición de query con un parámetro requerido
    query_def = QueryDefinition(
        name="get_table_columns",
        db_type="sqlite",
        sql_template="PRAGMA table_info(:table_name)",
        required_params=["table_name"],
    )

    # 2. Caso válido: todos los parámetros requeridos presentes
    print("2. Parámetros válidos\n")
    is_valid, warnings = validator.validate_parameters(query_def, {"table_name": "clientes"})
    print(f"   is_valid={is_valid}, warnings={warnings}\n")

    # 3. Caso inválido: falta el parámetro requerido
    print("3. Parámetro requerido ausente\n")
    is_valid, warnings = validator.validate_parameters(query_def, {})
    print(f"   is_valid={is_valid}, warnings={warnings}\n")

    # 3b. Caso inválido: parámetro presente pero vacío
    print("4. Parámetro vacío\n")
    is_valid, warnings = validator.validate_parameters(query_def, {"table_name": "   "})
    print(f"   is_valid={is_valid}, warnings={warnings}\n")

    # 4. Warning sin invalidar: database_file vacío es válido pero advertido
    print("5. Advertencia sin invalidar\n")
    is_valid, warnings = validator.validate_parameters(
        query_def, {"table_name": "clientes", "database_file": ""}
    )
    print(f"   is_valid={is_valid}, warnings={warnings}\n")

    # 5. Motor no soportado → ValueError de la factory
    print("6. Motor no soportado\n")
    try:
        get_type_validator("motor_inexistente")
    except ValueError as exc:
        print(f"   ValueError capturado: {exc}\n")

    # 6. La factory cachea: misma instancia para el mismo motor
    print("7. Cacheo de la factory\n")
    print(f"   misma instancia: {get_type_validator('sqlite') is get_type_validator('sqlite')}")


if __name__ == "__main__":
    demonstrate_validators()
