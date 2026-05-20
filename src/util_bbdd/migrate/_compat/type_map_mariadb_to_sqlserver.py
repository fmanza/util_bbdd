"""Mapeo exhaustivo de tipos MariaDB → SQL Server.

Cubre los tipos más comunes de MariaDB con sus equivalentes SQL Server.
Los parámetros de longitud, precisión y escala se resuelven dinámicamente
en el transformer según los metadatos de la columna.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingMariaToSQLServer:
    """Definición de mapeo para un tipo MariaDB a SQL Server."""

    source_base: str
    sqlserver_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico MariaDB → SQL Server.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
MARIADB_TO_SQLSERVER: dict[str, TypeMappingMariaToSQLServer] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    # TINYINT: MariaDB signed (-128..127) vs SQL Server unsigned (0..255) — aviso
    "TINYINT": TypeMappingMariaToSQLServer(
        "TINYINT",
        "TINYINT",
        warning_msg="TINYINT MariaDB signed (-128..127) vs SQL Server TINYINT unsigned (0..255); revisar valores negativos",
        severity="WARNING",
        ddl_comment="-- AVISO: TINYINT rango distinto (MariaDB signed vs SS unsigned 0-255)",
        requires_ddl_comment=True,
    ),
    "BOOL": TypeMappingMariaToSQLServer("BOOL", "BIT"),
    "BOOLEAN": TypeMappingMariaToSQLServer("BOOLEAN", "BIT"),
    "SMALLINT": TypeMappingMariaToSQLServer("SMALLINT", "SMALLINT"),
    "MEDIUMINT": TypeMappingMariaToSQLServer("MEDIUMINT", "INT"),
    "INT": TypeMappingMariaToSQLServer("INT", "INT"),
    "INTEGER": TypeMappingMariaToSQLServer("INTEGER", "INT"),
    "BIGINT": TypeMappingMariaToSQLServer("BIGINT", "BIGINT"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "DECIMAL": TypeMappingMariaToSQLServer("DECIMAL", "DECIMAL"),
    "NUMERIC": TypeMappingMariaToSQLServer("NUMERIC", "NUMERIC"),
    "FLOAT": TypeMappingMariaToSQLServer("FLOAT", "REAL"),
    "DOUBLE": TypeMappingMariaToSQLServer("DOUBLE", "FLOAT(53)"),
    "DOUBLE PRECISION": TypeMappingMariaToSQLServer("DOUBLE PRECISION", "FLOAT(53)"),
    "REAL": TypeMappingMariaToSQLServer("REAL", "REAL"),
    "BIT": TypeMappingMariaToSQLServer(
        "BIT",
        "BIT",
        warning_msg="BIT(n>1) MariaDB (n bits) → BIT SQL Server (1 bit solo); revisar si n>1",
        severity="WARNING",
        ddl_comment="-- AVISO: BIT(n>1) MariaDB → BIT SQL Server (solo 1 bit)",
        requires_ddl_comment=True,
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # SQL Server usa N-prefix para Unicode nativo; VARCHAR→NVARCHAR, CHAR→NCHAR
    "CHAR": TypeMappingMariaToSQLServer(
        "CHAR",
        "NCHAR",
        warning_msg="CHAR mapeado a NCHAR (Unicode nativo en SQL Server)",
        severity="INFO",
    ),
    "VARCHAR": TypeMappingMariaToSQLServer(
        "VARCHAR",
        "NVARCHAR",
        warning_msg="VARCHAR mapeado a NVARCHAR (Unicode nativo en SQL Server)",
        severity="INFO",
    ),
    "TINYTEXT": TypeMappingMariaToSQLServer("TINYTEXT", "NVARCHAR(255)"),
    "TEXT": TypeMappingMariaToSQLServer("TEXT", "NVARCHAR(MAX)"),
    "MEDIUMTEXT": TypeMappingMariaToSQLServer("MEDIUMTEXT", "NVARCHAR(MAX)"),
    "LONGTEXT": TypeMappingMariaToSQLServer("LONGTEXT", "NVARCHAR(MAX)"),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BINARY": TypeMappingMariaToSQLServer("BINARY", "BINARY"),
    "VARBINARY": TypeMappingMariaToSQLServer("VARBINARY", "VARBINARY"),
    "TINYBLOB": TypeMappingMariaToSQLServer("TINYBLOB", "VARBINARY(255)"),
    "BLOB": TypeMappingMariaToSQLServer("BLOB", "VARBINARY(MAX)"),
    "MEDIUMBLOB": TypeMappingMariaToSQLServer("MEDIUMBLOB", "VARBINARY(MAX)"),
    "LONGBLOB": TypeMappingMariaToSQLServer("LONGBLOB", "VARBINARY(MAX)"),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingMariaToSQLServer("DATE", "DATE"),
    "TIME": TypeMappingMariaToSQLServer("TIME", "TIME"),
    "DATETIME": TypeMappingMariaToSQLServer("DATETIME", "DATETIME2"),
    "TIMESTAMP": TypeMappingMariaToSQLServer(
        "TIMESTAMP",
        "DATETIME2",
        warning_msg="TIMESTAMP MariaDB (UTC internamente) → DATETIME2 SQL Server (sin zona); revisar comportamiento TZ",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMP MariaDB → DATETIME2 SQL Server; zona horaria no preservada",
        requires_ddl_comment=True,
    ),
    "YEAR": TypeMappingMariaToSQLServer(
        "YEAR",
        "SMALLINT",
        warning_msg="YEAR MariaDB (1901-2155) mapeado a SMALLINT",
        severity="INFO",
    ),
    # ── JSON y tipos especiales ──────────────────────────────────────────────────
    "JSON": TypeMappingMariaToSQLServer(
        "JSON",
        "NVARCHAR(MAX)",
        warning_msg="JSON mapeado a NVARCHAR(MAX); SQL Server 2016+ tiene funciones JSON pero no tipo nativo",
        severity="WARNING",
        ddl_comment="-- AVISO: JSON → NVARCHAR(MAX); SQL Server 2016+ soporta JSON functions",
        requires_ddl_comment=True,
    ),
    "ENUM": TypeMappingMariaToSQLServer(
        "ENUM",
        "NVARCHAR",
        warning_msg="ENUM mapeado a NVARCHAR(255); añadir CHECK constraint manualmente",
        severity="WARNING",
        ddl_comment="-- AVISO: ENUM → NVARCHAR(255); añadir CHECK constraint para restricción de dominio",
        requires_ddl_comment=True,
    ),
    "SET": TypeMappingMariaToSQLServer(
        "SET",
        "NVARCHAR(255)",
        warning_msg="SET mapeado a NVARCHAR(255); semántica de conjunto no preservada",
        severity="WARNING",
        ddl_comment="-- AVISO: SET → NVARCHAR(255); semántica de conjunto no preservada",
        requires_ddl_comment=True,
    ),
    "UUID": TypeMappingMariaToSQLServer("UUID", "UNIQUEIDENTIFIER"),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOMETRY": TypeMappingMariaToSQLServer(
        "GEOMETRY",
        "GEOMETRY",
        warning_msg="GEOMETRY mapeado a GEOMETRY SQL Server (tipo nativo); verificar compatibilidad de datos",
        severity="WARNING",
        ddl_comment="-- AVISO: GEOMETRY → GEOMETRY SQL Server; verificar compatibilidad de datos",
        requires_ddl_comment=True,
    ),
    "POINT": TypeMappingMariaToSQLServer("POINT", "GEOMETRY"),
    "LINESTRING": TypeMappingMariaToSQLServer("LINESTRING", "GEOMETRY"),
    "POLYGON": TypeMappingMariaToSQLServer("POLYGON", "GEOMETRY"),
}


def resolve_mariadb_type_sqlserver(mariadb_type: str) -> TypeMappingMariaToSQLServer | None:
    """Busca el mapeo para un tipo MariaDB hacia SQL Server (sin parámetros).

    Args:
        mariadb_type: Tipo MariaDB en crudo (ej. "INT", "VARCHAR", "DATETIME").

    Returns:
        TypeMappingMariaToSQLServer si existe, None si el tipo es desconocido.
    """
    key = mariadb_type.strip().upper()
    return MARIADB_TO_SQLSERVER.get(key)


__all__: list[str] = [
    "TypeMappingMariaToSQLServer",
    "MARIADB_TO_SQLSERVER",
    "resolve_mariadb_type_sqlserver",
]
