"""Mapeo exhaustivo de tipos MariaDB → PostgreSQL.

Cubre los tipos más comunes de MariaDB con sus equivalentes PostgreSQL.
Los parámetros de longitud, precisión y escala se resuelven dinámicamente
en el transformer según los metadatos de la columna.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingMariaToPostgreSQL:
    """Definición de mapeo para un tipo MariaDB a PostgreSQL."""

    source_base: str
    pg_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico MariaDB → PostgreSQL.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
MARIADB_TO_POSTGRESQL: dict[str, TypeMappingMariaToPostgreSQL] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "TINYINT": TypeMappingMariaToPostgreSQL(
        "TINYINT",
        "SMALLINT",
        warning_msg="TINYINT MariaDB (-128..127) mapeado a SMALLINT PostgreSQL (-32768..32767); rango ampliado",
        severity="INFO",
    ),
    "BOOL": TypeMappingMariaToPostgreSQL("BOOL", "BOOLEAN"),
    "BOOLEAN": TypeMappingMariaToPostgreSQL("BOOLEAN", "BOOLEAN"),
    "SMALLINT": TypeMappingMariaToPostgreSQL("SMALLINT", "SMALLINT"),
    "MEDIUMINT": TypeMappingMariaToPostgreSQL("MEDIUMINT", "INTEGER"),
    "INT": TypeMappingMariaToPostgreSQL("INT", "INTEGER"),
    "INTEGER": TypeMappingMariaToPostgreSQL("INTEGER", "INTEGER"),
    "BIGINT": TypeMappingMariaToPostgreSQL("BIGINT", "BIGINT"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "DECIMAL": TypeMappingMariaToPostgreSQL("DECIMAL", "NUMERIC"),
    "NUMERIC": TypeMappingMariaToPostgreSQL("NUMERIC", "NUMERIC"),
    "FLOAT": TypeMappingMariaToPostgreSQL("FLOAT", "REAL"),
    "DOUBLE": TypeMappingMariaToPostgreSQL("DOUBLE", "DOUBLE PRECISION"),
    "DOUBLE PRECISION": TypeMappingMariaToPostgreSQL("DOUBLE PRECISION", "DOUBLE PRECISION"),
    "REAL": TypeMappingMariaToPostgreSQL("REAL", "REAL"),
    # PostgreSQL soporta BIT(n) nativo
    "BIT": TypeMappingMariaToPostgreSQL("BIT", "BIT"),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # PostgreSQL es Unicode-native; CHAR/VARCHAR se mapean directamente
    "CHAR": TypeMappingMariaToPostgreSQL("CHAR", "CHAR"),
    "VARCHAR": TypeMappingMariaToPostgreSQL("VARCHAR", "VARCHAR"),
    "TINYTEXT": TypeMappingMariaToPostgreSQL("TINYTEXT", "VARCHAR(255)"),
    "TEXT": TypeMappingMariaToPostgreSQL("TEXT", "TEXT"),
    "MEDIUMTEXT": TypeMappingMariaToPostgreSQL("MEDIUMTEXT", "TEXT"),
    "LONGTEXT": TypeMappingMariaToPostgreSQL("LONGTEXT", "TEXT"),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BINARY": TypeMappingMariaToPostgreSQL(
        "BINARY",
        "BYTEA",
        warning_msg="BINARY mapeado a BYTEA; longitud fija no preservada (BYTEA es variable)",
        severity="INFO",
    ),
    "VARBINARY": TypeMappingMariaToPostgreSQL("VARBINARY", "BYTEA"),
    "TINYBLOB": TypeMappingMariaToPostgreSQL("TINYBLOB", "BYTEA"),
    "BLOB": TypeMappingMariaToPostgreSQL("BLOB", "BYTEA"),
    "MEDIUMBLOB": TypeMappingMariaToPostgreSQL("MEDIUMBLOB", "BYTEA"),
    "LONGBLOB": TypeMappingMariaToPostgreSQL("LONGBLOB", "BYTEA"),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingMariaToPostgreSQL("DATE", "DATE"),
    "TIME": TypeMappingMariaToPostgreSQL("TIME", "TIME"),
    "DATETIME": TypeMappingMariaToPostgreSQL("DATETIME", "TIMESTAMP"),
    "TIMESTAMP": TypeMappingMariaToPostgreSQL(
        "TIMESTAMP",
        "TIMESTAMPTZ",
        warning_msg="TIMESTAMP MariaDB (UTC internamente) mapeado a TIMESTAMPTZ; verificar comportamiento de zona horaria",
        severity="INFO",
    ),
    "YEAR": TypeMappingMariaToPostgreSQL(
        "YEAR",
        "SMALLINT",
        warning_msg="YEAR MariaDB (1901-2155) mapeado a SMALLINT",
        severity="INFO",
    ),
    # ── JSON y tipos especiales ──────────────────────────────────────────────────
    # PostgreSQL tiene soporte nativo JSON/JSONB; JSONB es indexable
    "JSON": TypeMappingMariaToPostgreSQL(
        "JSON",
        "JSONB",
        warning_msg="JSON mapeado a JSONB (indexable, binario); usar JSON si se requiere preservar orden de claves",
        severity="INFO",
        proposals=("JSONB", "JSON"),
    ),
    "ENUM": TypeMappingMariaToPostgreSQL(
        "ENUM",
        "TEXT",
        warning_msg="ENUM mapeado a TEXT; considerar CREATE TYPE ... AS ENUM (...) para restricción de dominio",
        severity="WARNING",
        proposals=("TEXT", "CREATE TYPE name AS ENUM (...)"),
        ddl_comment="-- AVISO: ENUM → TEXT; considerar CREATE TYPE AS ENUM para restricción de dominio",
        requires_ddl_comment=True,
    ),
    "SET": TypeMappingMariaToPostgreSQL(
        "SET",
        "TEXT",
        warning_msg="SET mapeado a TEXT; considerar TEXT[] para múltiples valores en PostgreSQL",
        severity="WARNING",
        proposals=("TEXT", "TEXT[]"),
        ddl_comment="-- AVISO: SET → TEXT; considerar TEXT[] para semántica de múltiples valores",
        requires_ddl_comment=True,
    ),
    "UUID": TypeMappingMariaToPostgreSQL("UUID", "UUID"),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOMETRY": TypeMappingMariaToPostgreSQL(
        "GEOMETRY",
        "GEOMETRY",
        warning_msg="GEOMETRY mapeado a GEOMETRY; requiere extensión PostGIS (CREATE EXTENSION postgis)",
        severity="WARNING",
        ddl_comment="-- AVISO: GEOMETRY → GEOMETRY PostGIS; requiere CREATE EXTENSION postgis",
        requires_ddl_comment=True,
    ),
    "POINT": TypeMappingMariaToPostgreSQL(
        "POINT",
        "POINT",
        warning_msg="POINT mapeado a POINT nativo PostgreSQL; verificar compatibilidad de datos con datos MariaDB",
        severity="INFO",
    ),
    "LINESTRING": TypeMappingMariaToPostgreSQL(
        "LINESTRING",
        "GEOMETRY",
        warning_msg="LINESTRING mapeado a GEOMETRY PostGIS; requiere CREATE EXTENSION postgis",
        severity="WARNING",
        ddl_comment="-- AVISO: LINESTRING → GEOMETRY PostGIS; requiere extensión PostGIS",
        requires_ddl_comment=True,
    ),
    "POLYGON": TypeMappingMariaToPostgreSQL(
        "POLYGON",
        "POLYGON",
        warning_msg="POLYGON mapeado a POLYGON nativo PostgreSQL; verificar compatibilidad de datos",
        severity="INFO",
    ),
}


def resolve_mariadb_type_postgresql(mariadb_type: str) -> TypeMappingMariaToPostgreSQL | None:
    """Busca el mapeo para un tipo MariaDB hacia PostgreSQL (sin parámetros).

    Args:
        mariadb_type: Tipo MariaDB en crudo (ej. "INT", "VARCHAR", "DATETIME").

    Returns:
        TypeMappingMariaToPostgreSQL si existe, None si el tipo es desconocido.
    """
    key = mariadb_type.strip().upper()
    return MARIADB_TO_POSTGRESQL.get(key)


__all__: list[str] = [
    "TypeMappingMariaToPostgreSQL",
    "MARIADB_TO_POSTGRESQL",
    "resolve_mariadb_type_postgresql",
]
