"""Mapeo exhaustivo de tipos Oracle → PostgreSQL.

Cubre 30+ tipos Oracle con sus equivalentes PostgreSQL, estrategia de
transformación y mensajes de aviso cuando la equivalencia no es exacta.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingPostgreSQL:
    """Definición de mapeo para un tipo Oracle a PostgreSQL."""

    oracle_base: str
    pg_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico Oracle → PostgreSQL.
# La clave es el tipo Oracle en MAYÚSCULAS sin parámetros.
ORACLE_TO_POSTGRESQL: dict[str, TypeMappingPostgreSQL] = {
    # ── Strings ───────────────────────────────────────────────────────────────
    # PostgreSQL usa UTF-8 por defecto; VARCHAR equivale a VARCHAR2 de Oracle.
    # No existe NVARCHAR en PG — se usa VARCHAR directamente.
    "VARCHAR2": TypeMappingPostgreSQL("VARCHAR2", "VARCHAR"),
    "VARCHAR": TypeMappingPostgreSQL("VARCHAR", "VARCHAR"),
    "NVARCHAR2": TypeMappingPostgreSQL(
        "NVARCHAR2",
        "VARCHAR",
        warning_msg="NVARCHAR2 mapeado a VARCHAR (PostgreSQL es Unicode-native, no requiere N-prefix)",
        severity="INFO",
    ),
    "CHAR": TypeMappingPostgreSQL("CHAR", "CHAR"),
    "NCHAR": TypeMappingPostgreSQL(
        "NCHAR",
        "CHAR",
        warning_msg="NCHAR mapeado a CHAR (PostgreSQL es Unicode-native)",
        severity="INFO",
    ),
    # ── Números enteros y decimales (NUMBER se resuelve dinámicamente) ────────
    "INTEGER": TypeMappingPostgreSQL("INTEGER", "INTEGER"),
    "INT": TypeMappingPostgreSQL("INT", "INTEGER"),
    "SMALLINT": TypeMappingPostgreSQL("SMALLINT", "SMALLINT"),
    "NUMBER": TypeMappingPostgreSQL(
        "NUMBER",
        "DOUBLE PRECISION",
        warning_msg="NUMBER sin precisión explícita mapeado a DOUBLE PRECISION",
        severity="WARNING",
        ddl_comment="-- AVISO: NUMBER sin precisión → DOUBLE PRECISION (pérdida de exactitud posible)",
        requires_ddl_comment=True,
    ),
    "NUMERIC": TypeMappingPostgreSQL("NUMERIC", "NUMERIC"),
    "DECIMAL": TypeMappingPostgreSQL("DECIMAL", "NUMERIC"),
    # ── Punto flotante ────────────────────────────────────────────────────────
    "FLOAT": TypeMappingPostgreSQL("FLOAT", "DOUBLE PRECISION"),
    "REAL": TypeMappingPostgreSQL("REAL", "REAL"),
    "DOUBLE PRECISION": TypeMappingPostgreSQL("DOUBLE PRECISION", "DOUBLE PRECISION"),
    "BINARY_FLOAT": TypeMappingPostgreSQL(
        "BINARY_FLOAT",
        "REAL",
        warning_msg="BINARY_FLOAT (24 bits IEEE) mapeado a REAL; posible diferencia de precisión extrema",
        severity="INFO",
    ),
    "BINARY_DOUBLE": TypeMappingPostgreSQL("BINARY_DOUBLE", "DOUBLE PRECISION"),
    # ── Fecha y hora ──────────────────────────────────────────────────────────
    # DATE en Oracle incluye componente horario; DATE en PG es solo fecha.
    "DATE": TypeMappingPostgreSQL(
        "DATE",
        "TIMESTAMP",
        warning_msg="DATE Oracle incluye componente horario; mapeado a TIMESTAMP en PostgreSQL",
        severity="WARNING",
        ddl_comment="-- AVISO: DATE Oracle contiene hora; usar TIMESTAMP",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP": TypeMappingPostgreSQL("TIMESTAMP", "TIMESTAMP"),
    "TIMESTAMP WITH TIME ZONE": TypeMappingPostgreSQL(
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMPTZ",
        warning_msg="TIMESTAMP WITH TIME ZONE mapeado a TIMESTAMPTZ; zona horaria preservada",
        severity="INFO",
    ),
    "TIMESTAMP WITH LOCAL TIME ZONE": TypeMappingPostgreSQL(
        "TIMESTAMP WITH LOCAL TIME ZONE",
        "TIMESTAMP",
        warning_msg="TIMESTAMP WITH LOCAL TIME ZONE convertido a TIMESTAMP; zona horaria no preservada",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMP WITH LOCAL TIME ZONE → TIMESTAMP; zona horaria perdida",
        requires_ddl_comment=True,
    ),
    # ── Intervalos (PostgreSQL soporta INTERVAL nativo) ──────────────────────
    "INTERVAL YEAR TO MONTH": TypeMappingPostgreSQL(
        "INTERVAL YEAR TO MONTH",
        "INTERVAL",
        warning_msg="INTERVAL YEAR TO MONTH mapeado a INTERVAL nativo de PostgreSQL",
        severity="INFO",
    ),
    "INTERVAL DAY TO SECOND": TypeMappingPostgreSQL(
        "INTERVAL DAY TO SECOND",
        "INTERVAL",
        warning_msg="INTERVAL DAY TO SECOND mapeado a INTERVAL nativo de PostgreSQL",
        severity="INFO",
    ),
    # ── LOB ───────────────────────────────────────────────────────────────────
    "CLOB": TypeMappingPostgreSQL("CLOB", "TEXT"),
    "NCLOB": TypeMappingPostgreSQL("NCLOB", "TEXT"),
    "BLOB": TypeMappingPostgreSQL("BLOB", "BYTEA"),
    "LONG": TypeMappingPostgreSQL(
        "LONG",
        "TEXT",
        warning_msg="LONG (deprecated en Oracle) mapeado a TEXT",
        severity="INFO",
    ),
    "LONG RAW": TypeMappingPostgreSQL("LONG RAW", "BYTEA"),
    "RAW": TypeMappingPostgreSQL("RAW", "BYTEA"),
    # ── Sin equivalente directo ───────────────────────────────────────────────
    "BFILE": TypeMappingPostgreSQL(
        "BFILE",
        "TEXT",
        warning_msg="BFILE sin equivalente en PostgreSQL; mapeado a TEXT para ruta (propuesta A)",
        severity="WARNING",
        proposals=("TEXT -- ruta de archivo",),
        ddl_comment="-- AVISO: BFILE → TEXT ruta [A]; revisar lógica de aplicación",
        requires_ddl_comment=True,
    ),
    "XMLTYPE": TypeMappingPostgreSQL(
        "XMLTYPE",
        "XML",
        warning_msg="XMLType mapeado a XML nativo de PostgreSQL (propuesta A)",
        severity="WARNING",
        proposals=("XML", "TEXT"),
        ddl_comment="-- AVISO: XMLType → XML [A] | TEXT [B]",
        requires_ddl_comment=True,
    ),
    # ROWID/UROWID: columna omitida — sin equivalente semántico
    "ROWID": TypeMappingPostgreSQL(
        "ROWID",
        "",
        warning_msg="ROWID sin equivalente semántico en PostgreSQL; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: ROWID omitido (sin equivalente en PostgreSQL)",
        requires_ddl_comment=True,
    ),
    "UROWID": TypeMappingPostgreSQL(
        "UROWID",
        "",
        warning_msg="UROWID sin equivalente semántico en PostgreSQL; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: UROWID omitido (sin equivalente en PostgreSQL)",
        requires_ddl_comment=True,
    ),
}


def resolve_oracle_type_postgresql(oracle_type: str) -> TypeMappingPostgreSQL | None:
    """Busca el mapeo para un tipo Oracle hacia PostgreSQL (sin parámetros).

    Args:
        oracle_type: Tipo Oracle en crudo (ej. "VARCHAR2", "NUMBER", "TIMESTAMP WITH TIME ZONE")

    Returns:
        TypeMappingPostgreSQL si existe, None si el tipo es desconocido.
    """
    key = oracle_type.strip().upper()
    return ORACLE_TO_POSTGRESQL.get(key)


def resolve_number_type_postgresql(
    precision: int | None,
    scale: int | None,
    fallback: str = "DOUBLE PRECISION",
) -> tuple[str, str | None]:
    """Resuelve el tipo PostgreSQL para NUMBER Oracle según precision/scale.

    Args:
        precision: DATA_PRECISION de Oracle (puede ser None).
        scale: DATA_SCALE de Oracle (puede ser None).
        fallback: Tipo destino cuando no hay precision/scale ("DOUBLE PRECISION" por defecto).

    Returns:
        (pg_type, optional_ddl_comment)
    """
    if precision is None:
        comment = f"-- AVISO: NUMBER sin precisión → {fallback} (pérdida de exactitud posible)"
        return fallback, comment

    effective_scale = scale if scale is not None else 0

    if effective_scale > 0:
        return f"NUMERIC({precision},{effective_scale})", None

    # scale == 0: tipo entero según precisión
    if precision <= 4:
        return "SMALLINT", None
    if precision <= 9:
        return "INTEGER", None
    if precision <= 18:
        return "BIGINT", None

    return f"NUMERIC({precision},0)", None


__all__: list[str] = [
    "TypeMappingPostgreSQL",
    "ORACLE_TO_POSTGRESQL",
    "resolve_oracle_type_postgresql",
    "resolve_number_type_postgresql",
]
