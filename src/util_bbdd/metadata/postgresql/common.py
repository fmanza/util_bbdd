"""Helpers puros compartidos para metadata PostgreSQL."""

from __future__ import annotations

from typing import Any

from ..adapters.shared import normalize_column_type


def escape_pg_literal(value: str) -> str:
    """Escapa comillas simples para SQL literal PostgreSQL."""
    return str(value).replace("'", "''")


def quote_pg_identifier(identifier: str) -> str:
    """Quote de identificadores PostgreSQL con comillas dobles."""
    safe_identifier = str(identifier).replace('"', '""')
    return f'"{safe_identifier}"'


def normalize_postgres_type(pg_type: str) -> str:
    """Normaliza un tipo PostgreSQL usando la función compartida de mapeo.

    Para tipos compuestos (e.g. "timestamp with time zone"), extrae la palabra base.
    """
    pg_type_lower = str(pg_type).lower().strip()

    # Extraer primera palabra para tipos compuestos
    # ej: "timestamp with time zone" → "timestamp"
    if " " in pg_type_lower:
        first_word = pg_type_lower.split()[0]
        return normalize_column_type(first_word, db_type="postgresql")

    return normalize_column_type(pg_type, db_type="postgresql")


def parse_pg_array_type(typename: str) -> tuple[str, bool]:
    """Detecta si un tipo es array y retorna (base_type, is_array).

    Ejemplos:
        - "integer[]" → ("integer", True)
        - "integer" → ("integer", False)
        - "text[][]" → ("text", True)
    """
    typename_clean = str(typename).strip()
    # Simplemente contar [] al final
    if typename_clean.endswith("[]"):
        base = typename_clean.rstrip("[]")
        return (base, True)
    return (typename_clean, False)


def parse_pg_type_with_params(typename: str) -> dict[str, Any]:
    """Parsea un tipo PostgreSQL y extrae parámetros (p.ej. varchar(255)).

    Retorna dict con:
        - name: nombre base del tipo
        - is_array: si es array
        - length: longitud si aplica (p.ej. varchar)
        - precision/scale: si aplica (p.ej. numeric)
    """
    base_type, is_array = parse_pg_array_type(typename)

    result: dict[str, Any] = {"name": base_type, "is_array": is_array}

    # Detectar parámetros en paréntesis (ej: varchar(255), numeric(10,2))
    if "(" in base_type and ")" in base_type:
        base_name = base_type.split("(")[0]
        params_str = base_type.split("(")[1].split(")")[0]
        result["name"] = base_name

        parts = [p.strip() for p in params_str.split(",")]
        if len(parts) == 1:
            try:
                result["length"] = int(parts[0])
            except ValueError:
                result["length"] = parts[0]
        elif len(parts) == 2:
            try:
                result["precision"] = int(parts[0])
                result["scale"] = int(parts[1])
            except ValueError:
                result["precision"] = parts[0]
                result["scale"] = parts[1]

    return result


# Mapping básico OID → nombre de tipo (primeros 100 OIDs frecuentes)
_PG_OID_BUILTIN_TYPES: dict[int, str] = {
    16: "boolean",
    17: "bytea",
    20: "bigint",
    21: "smallint",
    23: "integer",
    25: "text",
    26: "oid",
    27: "tid",
    28: "xid",
    29: "cid",
    114: "json",
    142: "xml",
    143: "_xml",
    199: "_json",
    600: "point",
    601: "lseg",
    602: "path",
    603: "box",
    604: "polygon",
    628: "line",
    629: "_line",
    700: "real",
    701: "double precision",
    702: "abstime",
    703: "reltime",
    704: "tinterval",
    705: "unknown",
    718: "circle",
    719: "_circle",
    790: "money",
    791: "_money",
    829: "macaddr",
    869: "inet",
    919: "_int2",
    1000: "_bool",
    1007: "_int4",
    1016: "_int8",
    1017: "_point",
    1021: "_float4",
    1022: "_float8",
    1028: "_uuid",
    1033: "aclitem",
    1040: "macaddr8",
    1041: "_macaddr8",
    1042: "bpchar",
    1043: "varchar",
    1082: "date",
    1083: "time",
    1114: "timestamp",
    1115: "_timestamp",
    1182: "_date",
    1183: "_time",
    1184: "timestamp with time zone",
    1185: "_timestamptz",
    1186: "interval",
    1187: "_interval",
    1231: "_numeric",
    1266: "time with time zone",
    1267: "_timetz",
    1700: "numeric",
    2278: "void",
    2950: "uuid",
    3614: "tsvector",
    3615: "tsquery",
    3802: "jsonb",
    3807: "_jsonb",
    4089: "_text",
}


def get_pg_type_name_from_oid(oid: int) -> str | None:
    """Retorna el nombre del tipo PostgreSQL a partir de OID, si existe en mapeo."

    Args:
        oid: OID del tipo PostgreSQL

    Returns:
        Nombre del tipo o None si no está en el mapeo.
    """
    return _PG_OID_BUILTIN_TYPES.get(oid)


__all__: list[str] = [
    "escape_pg_literal",
    "quote_pg_identifier",
    "normalize_postgres_type",
    "parse_pg_array_type",
    "parse_pg_type_with_params",
    "get_pg_type_name_from_oid",
]
