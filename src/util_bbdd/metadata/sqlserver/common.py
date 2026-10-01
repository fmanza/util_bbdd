"""Helpers puros compartidos para metadata SQL Server.

Proporciona mapeos de tipos T-SQL a tipos genéricos, escaping de identificadores,
y funciones de normalización.
"""

from __future__ import annotations

from ..adapters.shared import normalize_column_type


def sqlserver_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos T-SQL a tipos genéricos.

    Cubre 40+ tipos SQL Server comunes incluyendo precisión variable,
    tipos de fecha/hora, XML y tipos especializados.

    Returns:
        dict[str, str]: Mapeo {tsql_type_upper: generic_type}
    """
    return {
        # Integers
        "INT": "integer",
        "INTEGER": "integer",
        "BIGINT": "bigint",
        "SMALLINT": "smallint",
        "TINYINT": "tinyint",
        # Numerics with precision
        "NUMERIC": "numeric",
        "DECIMAL": "decimal",
        "DEC": "decimal",
        "FLOAT": "float",
        "REAL": "float",
        # Currency
        "MONEY": "money",
        "SMALLMONEY": "smallmoney",
        # Strings
        "VARCHAR": "varchar",
        "NVARCHAR": "varchar",
        "NVARCHAR(MAX)": "text",
        "VARCHAR(MAX)": "text",
        "CHAR": "char",
        "NCHAR": "char",
        "TEXT": "text",
        "NTEXT": "text",
        # Binary
        "BINARY": "binary",
        "VARBINARY": "binary",
        "VARBINARY(MAX)": "binary",
        "IMAGE": "binary",
        # Date/Time
        "DATE": "date",
        "TIME": "time",
        "DATETIME": "datetime",
        "DATETIME2": "datetime2",
        "DATETIMEOFFSET": "datetimeoffset",
        "SMALLDATETIME": "datetime",
        # Special types
        "UNIQUEIDENTIFIER": "varchar",
        "ROWVERSION": "binary",
        "TIMESTAMP": "binary",
        "SQL_VARIANT": "object",
        "XML": "xml",
        "HIERARCHYID": "varchar",
        "GEOMETRY": "geometry",
        "GEOGRAPHY": "geography",
        "FILESTREAM": "binary",
    }


def normalize_sqlserver_type(tsql_type: str) -> str:
    """Normaliza un tipo T-SQL al tipo genérico.

    Para tipos con parámetros (e.g., "VARCHAR(MAX)", "NUMERIC(10,2)"), extrae la palabra base.
    Si no está en el mapeo, devuelve "object".

    Args:
        tsql_type: Tipo T-SQL crudado del sys.types (ej: "VARCHAR", "INT")

    Returns:
        str: Tipo genérico normalizado o "object" si no se mapea
    """
    if not tsql_type:
        return "object"

    tsql_type_clean = str(tsql_type).strip().upper()

    # Primero intentar mapeo completo (con parámetros como NVARCHAR(MAX))
    mapping = sqlserver_type_mapping()
    if tsql_type_clean in mapping:
        return mapping[tsql_type_clean]

    # Luego extraer tipo base (remover parámetros en paréntesis)
    if "(" in tsql_type_clean:
        base_type = tsql_type_clean.split("(")[0].strip()
    else:
        base_type = tsql_type_clean

    # Buscar en mapeo
    if base_type in mapping:
        return mapping[base_type]

    # Fallback
    return normalize_column_type(base_type, db_type="sqlserver") or "object"


def quote_sqlserver_identifier(identifier: str) -> str:
    """Escapa identificadores T-SQL con corchetes.

    SQL Server acepta corchetes, comillas dobles y comillas invertidas.
    Se usan corchetes por ser el estándar de SQL Server.

    Args:
        identifier: Identificador a escapar (nombre de tabla, columna, schema)

    Returns:
        str: Identificador escapado con corchetes
    """
    if not identifier:
        return "[]"

    identifier_str = str(identifier).strip()

    # Escapar corchetes internos duplicándolos
    escaped = identifier_str.replace("]", "]]")

    return f"[{escaped}]"


def is_system_schema_sqlserver(schema: str | None) -> bool:
    """Determina si un schema es sistema en SQL Server.

    SQL Server tiene schemas de sistema: sys, INFORMATION_SCHEMA, y bases de datos temporales (tempdb, model, msdb).

    Args:
        schema: Nombre del schema

    Returns:
        bool: True si es schema de sistema
    """
    if not schema:
        return False

    system_schemas = {
        "sys",
        "information_schema",
        "msdb",
        "model",
        "tempdb",
    }

    return str(schema).strip().lower() in system_schemas


def decode_sqlserver_cascade_action(action_code: int | None) -> str:
    """Decodifica código de acción CASCADE de FK en SQL Server.

    0=NO ACTION, 1=CASCADE, 2=SET NULL, 3=SET DEFAULT, 4=TRIGGER (custom)

    Args:
        action_code: Código de acción (0-4)

    Returns:
        str: Nombre de acción en mayúsculas
    """
    if action_code is None:
        return "NO ACTION"

    code_map = {
        0: "NO ACTION",
        1: "CASCADE",
        2: "SET NULL",
        3: "SET DEFAULT",
        4: "TRIGGER",
    }

    return code_map.get(int(action_code), "NO ACTION")


def escape_sqlserver_string(value: str) -> str:
    """Escapa strings para uso en SQL dinámico T-SQL.

    Duplica comillas simples para evitar inyección SQL.

    Args:
        value: String a escapar

    Returns:
        str: String escapado entre comillas simples
    """
    if not value:
        return "''"

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def fetch_compatibility_level_sql() -> str:
    """SQL que devuelve el nivel de compatibilidad de la base de datos actual.

    Lo usa el DELETE masivo de ``bulk`` en SQL Server: ``OPENJSON`` exige nivel ≥ 130 (SQL Server 2016).

    Returns:
        str: SQL con una fila y un entero.
    """
    return "SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()"
