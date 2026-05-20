"""Mapeo exhaustivo de tipos SQL Server → PostgreSQL.

Cubre los tipos estándar de SQL Server con sus equivalentes PostgreSQL.
Los parámetros de longitud, precisión y escala se resuelven dinámicamente
en el transformer según los metadatos de la columna.

``source_base`` es el tipo SQL Server en MAYÚSCULAS sin parámetros.

Nota sobre char_length: SQL Server usa -1 como sentinel para MAX en VARCHAR(MAX),
NVARCHAR(MAX) y VARBINARY(MAX). El transformer lo detecta para emitir
TEXT/BYTEA según corresponda.

PostgreSQL es Unicode-native; NCHAR/NVARCHAR se mapean directamente a CHAR/VARCHAR.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingSQLServerToPostgreSQL:
    """Definición de mapeo para un tipo SQL Server a PostgreSQL."""

    source_base: str
    pg_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico SQL Server → PostgreSQL.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
SQLSERVER_TO_POSTGRESQL: dict[str, TypeMappingSQLServerToPostgreSQL] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INT": TypeMappingSQLServerToPostgreSQL("INT", "INTEGER"),
    "BIGINT": TypeMappingSQLServerToPostgreSQL("BIGINT", "BIGINT"),
    "SMALLINT": TypeMappingSQLServerToPostgreSQL("SMALLINT", "SMALLINT"),
    # SQL Server TINYINT unsigned (0..255); PostgreSQL SMALLINT (-32768..32767)
    "TINYINT": TypeMappingSQLServerToPostgreSQL(
        "TINYINT",
        "SMALLINT",
        warning_msg="TINYINT SQL Server (0..255 unsigned) mapeado a SMALLINT PostgreSQL; rango ampliado",
        severity="INFO",
    ),
    "BIT": TypeMappingSQLServerToPostgreSQL(
        "BIT",
        "BOOLEAN",
        warning_msg="BIT SQL Server (0/1/NULL) mapeado a BOOLEAN PostgreSQL",
        severity="INFO",
    ),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "DECIMAL": TypeMappingSQLServerToPostgreSQL("DECIMAL", "NUMERIC"),
    "NUMERIC": TypeMappingSQLServerToPostgreSQL("NUMERIC", "NUMERIC"),
    "FLOAT": TypeMappingSQLServerToPostgreSQL(
        "FLOAT",
        "DOUBLE PRECISION",
        warning_msg="FLOAT SQL Server (IEEE 754 double) mapeado a DOUBLE PRECISION PostgreSQL",
        severity="INFO",
    ),
    "REAL": TypeMappingSQLServerToPostgreSQL(
        "REAL",
        "REAL",
        warning_msg="REAL SQL Server (IEEE 754 single) mapeado a REAL PostgreSQL",
        severity="INFO",
    ),
    "MONEY": TypeMappingSQLServerToPostgreSQL(
        "MONEY",
        "NUMERIC(19,4)",
        warning_msg="MONEY SQL Server mapeado a NUMERIC(19,4) PostgreSQL; considerar tipo MONEY nativo de PG",
        severity="INFO",
        proposals=("NUMERIC(19,4)", "MONEY -- tipo nativo PostgreSQL"),
    ),
    "SMALLMONEY": TypeMappingSQLServerToPostgreSQL(
        "SMALLMONEY",
        "NUMERIC(10,4)",
        warning_msg="SMALLMONEY SQL Server mapeado a NUMERIC(10,4) PostgreSQL",
        severity="INFO",
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # PostgreSQL es Unicode-native; NCHAR/NVARCHAR se mapean directamente
    # char_length=-1 indica MAX → TEXT en el transformer
    "CHAR": TypeMappingSQLServerToPostgreSQL("CHAR", "CHAR"),
    "VARCHAR": TypeMappingSQLServerToPostgreSQL("VARCHAR", "VARCHAR"),
    "NCHAR": TypeMappingSQLServerToPostgreSQL(
        "NCHAR",
        "CHAR",
        warning_msg="NCHAR SQL Server (Unicode) mapeado a CHAR PostgreSQL (Unicode-native)",
        severity="INFO",
    ),
    "NVARCHAR": TypeMappingSQLServerToPostgreSQL(
        "NVARCHAR",
        "VARCHAR",
        warning_msg="NVARCHAR SQL Server (Unicode) mapeado a VARCHAR PostgreSQL (Unicode-native)",
        severity="INFO",
    ),
    "TEXT": TypeMappingSQLServerToPostgreSQL(
        "TEXT",
        "TEXT",
        warning_msg="TEXT SQL Server (obsoleto desde 2005) mapeado a TEXT PostgreSQL",
        severity="WARNING",
        ddl_comment="-- AVISO: TEXT SQL Server obsoleto → TEXT PostgreSQL",
        requires_ddl_comment=True,
    ),
    "NTEXT": TypeMappingSQLServerToPostgreSQL(
        "NTEXT",
        "TEXT",
        warning_msg="NTEXT SQL Server (obsoleto desde 2005) mapeado a TEXT PostgreSQL",
        severity="WARNING",
        ddl_comment="-- AVISO: NTEXT SQL Server obsoleto → TEXT PostgreSQL",
        requires_ddl_comment=True,
    ),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingSQLServerToPostgreSQL("DATE", "DATE"),
    "TIME": TypeMappingSQLServerToPostgreSQL("TIME", "TIME"),
    "DATETIME": TypeMappingSQLServerToPostgreSQL(
        "DATETIME",
        "TIMESTAMP",
        warning_msg="DATETIME SQL Server mapeado a TIMESTAMP PostgreSQL (sin zona horaria)",
        severity="INFO",
    ),
    # DATETIME2 hasta 7 fracciones; PostgreSQL TIMESTAMP soporta hasta 6
    "DATETIME2": TypeMappingSQLServerToPostgreSQL(
        "DATETIME2",
        "TIMESTAMP(6)",
        warning_msg=(
            "DATETIME2 SQL Server (hasta 7 fracciones de segundo) mapeado a TIMESTAMP(6) PostgreSQL; "
            "última fracción truncada"
        ),
        severity="INFO",
    ),
    "SMALLDATETIME": TypeMappingSQLServerToPostgreSQL(
        "SMALLDATETIME",
        "TIMESTAMP",
        warning_msg="SMALLDATETIME SQL Server (precisión minutos) mapeado a TIMESTAMP PostgreSQL",
        severity="INFO",
    ),
    # DATETIMEOFFSET → TIMESTAMPTZ: equivalente más directo en PostgreSQL
    "DATETIMEOFFSET": TypeMappingSQLServerToPostgreSQL(
        "DATETIMEOFFSET",
        "TIMESTAMPTZ",
        warning_msg="DATETIMEOFFSET SQL Server mapeado a TIMESTAMPTZ PostgreSQL; verificar comportamiento TZ",
        severity="INFO",
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    # char_length=-1 indica MAX → BYTEA en el transformer
    "BINARY": TypeMappingSQLServerToPostgreSQL(
        "BINARY",
        "BYTEA",
        warning_msg="BINARY SQL Server (longitud fija) mapeado a BYTEA PostgreSQL (variable)",
        severity="INFO",
    ),
    "VARBINARY": TypeMappingSQLServerToPostgreSQL("VARBINARY", "BYTEA"),
    "IMAGE": TypeMappingSQLServerToPostgreSQL(
        "IMAGE",
        "BYTEA",
        warning_msg="IMAGE SQL Server (obsoleto desde 2005) mapeado a BYTEA PostgreSQL",
        severity="WARNING",
        ddl_comment="-- AVISO: IMAGE SQL Server obsoleto → BYTEA PostgreSQL",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "UNIQUEIDENTIFIER": TypeMappingSQLServerToPostgreSQL(
        "UNIQUEIDENTIFIER",
        "UUID",
        warning_msg="UNIQUEIDENTIFIER SQL Server mapeado a UUID PostgreSQL (tipo nativo)",
        severity="INFO",
    ),
    "XML": TypeMappingSQLServerToPostgreSQL(
        "XML",
        "XML",
        warning_msg="XML SQL Server mapeado a XML PostgreSQL (tipo nativo); verificar compatibilidad de contenido",
        severity="INFO",
    ),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOGRAPHY": TypeMappingSQLServerToPostgreSQL(
        "GEOGRAPHY",
        "GEOMETRY",
        warning_msg=(
            "GEOGRAPHY SQL Server (coordenadas esféricas) mapeado a GEOMETRY PostGIS; "
            "requiere CREATE EXTENSION postgis y conversión de datos"
        ),
        severity="ERROR",
        ddl_comment="-- AVISO: GEOGRAPHY SS → GEOMETRY PostGIS; requiere extensión PostGIS y conversión de datos",
        requires_ddl_comment=True,
    ),
    "GEOMETRY": TypeMappingSQLServerToPostgreSQL(
        "GEOMETRY",
        "GEOMETRY",
        warning_msg=(
            "GEOMETRY SQL Server mapeado a GEOMETRY PostGIS; "
            "requiere CREATE EXTENSION postgis; verificar compatibilidad de datos espaciales"
        ),
        severity="WARNING",
        ddl_comment="-- AVISO: GEOMETRY SS → GEOMETRY PostGIS; requiere CREATE EXTENSION postgis",
        requires_ddl_comment=True,
    ),
}


def resolve_sqlserver_type_postgresql(sqlserver_type: str) -> TypeMappingSQLServerToPostgreSQL | None:
    """Busca el mapeo para un tipo SQL Server hacia PostgreSQL (sin parámetros).

    Args:
        sqlserver_type: Tipo SQL Server en crudo (ej. "INT", "NVARCHAR", "DATETIMEOFFSET").

    Returns:
        TypeMappingSQLServerToPostgreSQL si existe, None si el tipo es desconocido.
    """
    key = sqlserver_type.strip().upper()
    return SQLSERVER_TO_POSTGRESQL.get(key)


__all__: list[str] = [
    "TypeMappingSQLServerToPostgreSQL",
    "SQLSERVER_TO_POSTGRESQL",
    "resolve_sqlserver_type_postgresql",
]
