"""Helpers puros compartidos para metadata Oracle.

Proporciona mapeos de tipos Oracle a tipos genéricos, escaping de identificadores,
y funciones de normalización.
"""

from __future__ import annotations

from typing import Any

from ..adapters.shared import normalize_column_type


def oracle_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos Oracle a tipos genéricos.

    Cubre 30+ tipos Oracle comunes incluyendo tipos con precisión/escala,
    LOB y pseudocolumnas, excluyendo ROWID.

    Returns:
        dict[str, str]: Mapeo {oracle_type_upper: generic_type}
    """
    return {
        "VARCHAR2": "varchar",
        "VARCHAR": "varchar",
        "NVARCHAR2": "varchar",
        "CHAR": "char",
        "NCHAR": "char",
        "NUMBER": "numeric",
        "NUMERIC": "numeric",
        "DECIMAL": "decimal",
        "INT": "integer",
        "INTEGER": "integer",
        "SMALLINT": "smallint",
        "FLOAT": "float",
        "REAL": "float",
        "DOUBLE PRECISION": "float",
        "DATE": "date",
        "TIMESTAMP": "timestamp",
        "TIMESTAMP WITH TIME ZONE": "timestamp",
        "TIMESTAMP WITH LOCAL TIME ZONE": "timestamp",
        "INTERVAL YEAR TO MONTH": "interval",
        "INTERVAL DAY TO SECOND": "interval",
        "BINARY_FLOAT": "float",
        "BINARY_DOUBLE": "float",
        "RAW": "binary",
        "LONG RAW": "binary",
        "BLOB": "blob",
        "CLOB": "clob",
        "NCLOB": "clob",
        "BFILE": "bfile",
        "LONG": "text",
        "ROWID": "rowid",
        "UROWID": "rowid",
        "XMLType": "xml",
    }


def normalize_oracle_type(oracle_type: str | None) -> str:
    """Normaliza un tipo Oracle al tipo genérico.

    Para tipos con precisión/escala (e.g., "NUMBER(10,2)"), extrae la palabra base.
    Si no está en el mapeo, devuelve "object".

    Args:
        oracle_type: Tipo Oracle crudado del query (ej: "VARCHAR2", "NUMBER(10,2)"), o None

    Returns:
        str: Tipo genérico normalizado o "object" si no se mapea
    """
    if not oracle_type:
        return "object"

    oracle_type_clean = str(oracle_type).strip().upper()

    # Extraer tipo base (remover parámetros en paréntesis)
    if "(" in oracle_type_clean:
        base_type = oracle_type_clean.split("(")[0].strip()
    else:
        base_type = oracle_type_clean

    # Buscar en mapeo
    mapping = oracle_type_mapping()
    if base_type in mapping:
        return mapping[base_type]

    # Tipos con espacios (ej: "TIMESTAMP WITH TIME ZONE")
    if base_type in mapping:
        return mapping[base_type]

    # Fallback
    return normalize_column_type(base_type, db_type="oracle") or "object"


def quote_oracle_identifier(identifier: str) -> str:
    """Escapa identificadores Oracle con comillas dobles.

    Oracle es case-insensitive para identificadores sin comillas.
    Con comillas dobles, preserva mayúsculas/minúsculas.

    Args:
        identifier: Identificador a escapar (ej: "user_table", "User Table")

    Returns:
        str: Identificador entre comillas dobles con interiores escapados
    """
    if not identifier:
        return '""'

    safe_identifier = str(identifier).replace('"', '""')
    return f'"{safe_identifier}"'


def escape_oracle_string(value: str) -> str:
    """Escapa comillas simples para SQL literal Oracle.

    Args:
        value: String a escapar

    Returns:
        str: String escapado para LIKE patterns y SQL literals
    """
    return str(value).replace("'", "''")


def is_system_schema_oracle(owner: str) -> bool:
    """Determina si un esquema es del sistema Oracle (debe excluirse).

    Excluye: SYS, SYSTEM, XDB, APEX_*, MDSYS, ORDDATA, SI_INFORMTN_SCHEMA,
    CTXSYS, TXNSYS, WM*, WMSYS, etc.

    Args:
        owner: Nombre del propietario/schema

    Returns:
        bool: True si es un schema de sistema
    """
    if not owner:
        return False

    owner_upper = str(owner).upper()

    system_schemas = {
        "SYS",
        "SYSTEM",
        "XDB",
        "MDSYS",
        "ORDDATA",
        "SI_INFORMTN_SCHEMA",
        "CTXSYS",
        "TXNSYS",
        "WMSYS",
        "OLAPSYS",
        "OWBSYS",
        "FLOWS_FILES",
        "FLOW_REPLICATION_ADMIN",
    }

    if owner_upper in system_schemas:
        return True

    # Prefijos de schemas de sistema
    system_prefixes = ["APEX_", "WM", "ORDS", "RMAN", "DVF", "C##"]
    for prefix in system_prefixes:
        if owner_upper.startswith(prefix):
            return True

    return False


def normalize_oracle_bind_identifier(value: str | None) -> str | None:
    """Normaliza a mayúsculas un identificador antes de bindearlo en una query Oracle.

    MEO-04 (AUDIT_CODE 2026-09-22): los diccionarios de datos de Oracle
    (``ALL_TABLES.OWNER``, ``ALL_TAB_COLUMNS.TABLE_NAME``, etc.) almacenan los
    nombres en MAYÚSCULAS salvo que se hayan creado con identificador citado
    (``"MiTabla"``, minoritario). Bindear ``schema``/``table`` en minúsculas sin
    normalizar devuelve 0 filas de forma silenciosa, sin ningún error.

    Args:
        value: Valor a normalizar (``None`` se preserva tal cual).

    Returns:
        str | None: ``value.upper()``, o ``None``/cadena vacía sin cambios.
    """
    return value.upper() if value else value


def get_oracle_table_type(object_type: str) -> str:
    """Normaliza OBJECT_TYPE de all_tables a tipo genérico (TABLE/VIEW).

    Args:
        object_type: OBJECT_TYPE de Oracle (TABLE, VIEW, CLUSTER, etc)

    Returns:
        str: Tipo normalizado (TABLE/VIEW/SYSTEM TABLE/EXTERNAL TABLE)
    """
    if not object_type:
        return "TABLE"

    obj_type_upper = str(object_type).upper()

    if "VIEW" in obj_type_upper:
        return "VIEW"
    if "CLUSTER" in obj_type_upper:
        return "CLUSTER"
    if "EXTERNAL" in obj_type_upper:
        return "EXTERNAL TABLE"
    if "SYSTEM" in obj_type_upper:
        return "SYSTEM TABLE"

    return "TABLE"


def parse_oracle_number_precision_scale(data_precision: Any, data_scale: Any) -> tuple[int | None, int | None]:
    """Parsea precision y scale de NUMBER Oracle.

    Args:
        data_precision: DATA_PRECISION de all_tab_columns (puede ser None o int)
        data_scale: DATA_SCALE de all_tab_columns (puede ser None o int)

    Returns:
        tuple[int | None, int | None]: (precision, scale) normalizados
    """
    try:
        precision = int(data_precision) if data_precision is not None else None
    except (ValueError, TypeError):
        precision = None

    try:
        scale = int(data_scale) if data_scale is not None else None
    except (ValueError, TypeError):
        scale = None

    return (precision, scale)


__all__: list[str] = [
    "oracle_type_mapping",
    "normalize_oracle_type",
    "normalize_oracle_bind_identifier",
    "quote_oracle_identifier",
    "escape_oracle_string",
    "is_system_schema_oracle",
    "get_oracle_table_type",
    "parse_oracle_number_precision_scale",
]
