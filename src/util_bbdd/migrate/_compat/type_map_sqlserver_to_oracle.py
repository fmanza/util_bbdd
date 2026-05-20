"""Mapeo exhaustivo de tipos SQL Server → Oracle.

Cubre los tipos estándar de SQL Server con sus equivalentes Oracle.
El campo ``oracle_type`` contiene el tipo Oracle base; los parámetros de longitud,
precisión y escala se resuelven dinámicamente en el transformer según los
metadatos de la columna (char_length, precision, scale).

``source_base`` es el tipo SQL Server en MAYÚSCULAS sin parámetros, equivalente
al valor de DATA_TYPE en INFORMATION_SCHEMA.COLUMNS devuelto en uppercase.

Nota sobre char_length: SQL Server usa -1 como sentinel para MAX en VARCHAR(MAX),
NVARCHAR(MAX) y VARBINARY(MAX). El transformer lo detecta para emitir CLOB/BLOB.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingSQLServerToOracle:
    """Definición de mapeo para un tipo SQL Server a Oracle."""

    source_base: str
    oracle_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico SQL Server → Oracle.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
SQLSERVER_TO_ORACLE: dict[str, TypeMappingSQLServerToOracle] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INT": TypeMappingSQLServerToOracle("INT", "NUMBER(10,0)"),
    "BIGINT": TypeMappingSQLServerToOracle("BIGINT", "NUMBER(19,0)"),
    "SMALLINT": TypeMappingSQLServerToOracle("SMALLINT", "NUMBER(5,0)"),
    # SQL Server TINYINT es 0..255 (unsigned); Oracle NUMBER(3,0) cubre -999..999
    "TINYINT": TypeMappingSQLServerToOracle(
        "TINYINT",
        "NUMBER(3,0)",
        warning_msg="TINYINT SQL Server (0..255 unsigned) mapeado a NUMBER(3,0) Oracle; rango ampliado",
        severity="INFO",
    ),
    "BIT": TypeMappingSQLServerToOracle(
        "BIT",
        "NUMBER(1,0)",
        warning_msg="BIT SQL Server (0/1/NULL) mapeado a NUMBER(1,0); Oracle < 23c no tiene tipo BOOLEAN nativo",
        severity="INFO",
    ),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    # DECIMAL/NUMERIC: precision/scale resueltos dinámicamente
    "DECIMAL": TypeMappingSQLServerToOracle("DECIMAL", "NUMBER"),
    "NUMERIC": TypeMappingSQLServerToOracle("NUMERIC", "NUMBER"),
    # SQL Server FLOAT(53) es IEEE 754 double precision
    "FLOAT": TypeMappingSQLServerToOracle(
        "FLOAT",
        "BINARY_DOUBLE",
        warning_msg="FLOAT SQL Server (IEEE 754 double) mapeado a BINARY_DOUBLE Oracle",
        severity="INFO",
    ),
    # SQL Server REAL equivale a FLOAT(24), IEEE 754 single
    "REAL": TypeMappingSQLServerToOracle(
        "REAL",
        "BINARY_FLOAT",
        warning_msg="REAL SQL Server (IEEE 754 single ~7 dígitos) mapeado a BINARY_FLOAT Oracle",
        severity="INFO",
    ),
    "MONEY": TypeMappingSQLServerToOracle(
        "MONEY",
        "NUMBER(19,4)",
        warning_msg="MONEY SQL Server mapeado a NUMBER(19,4); precisión monetaria preservada",
        severity="INFO",
    ),
    "SMALLMONEY": TypeMappingSQLServerToOracle(
        "SMALLMONEY",
        "NUMBER(10,4)",
        warning_msg="SMALLMONEY SQL Server mapeado a NUMBER(10,4)",
        severity="INFO",
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # VARCHAR/CHAR: oracle_type sin parámetros; char_length resuelto dinámicamente
    # char_length=-1 indica MAX → CLOB en el transformer
    "CHAR": TypeMappingSQLServerToOracle("CHAR", "CHAR"),
    "VARCHAR": TypeMappingSQLServerToOracle("VARCHAR", "VARCHAR2"),
    # SQL Server NCHAR/NVARCHAR: Unicode nativo; Oracle NCHAR2/NVARCHAR2 o CHAR/VARCHAR2
    "NCHAR": TypeMappingSQLServerToOracle(
        "NCHAR",
        "NCHAR",
        warning_msg="NCHAR SQL Server (Unicode) mapeado a NCHAR Oracle; verificar juego de caracteres NLS",
        severity="INFO",
    ),
    "NVARCHAR": TypeMappingSQLServerToOracle(
        "NVARCHAR",
        "NVARCHAR2",
        warning_msg="NVARCHAR SQL Server (Unicode) mapeado a NVARCHAR2 Oracle; verificar juego de caracteres NLS",
        severity="INFO",
    ),
    # TEXT/NTEXT: obsoletos en SQL Server 2005+
    "TEXT": TypeMappingSQLServerToOracle(
        "TEXT",
        "CLOB",
        warning_msg="TEXT SQL Server (obsoleto desde 2005) mapeado a CLOB Oracle",
        severity="WARNING",
        ddl_comment="-- AVISO: TEXT SQL Server obsoleto → CLOB Oracle; considerar VARCHAR2 si datos < 4000 chars",
        requires_ddl_comment=True,
    ),
    "NTEXT": TypeMappingSQLServerToOracle(
        "NTEXT",
        "CLOB",
        warning_msg="NTEXT SQL Server (obsoleto desde 2005) mapeado a CLOB Oracle",
        severity="WARNING",
        ddl_comment="-- AVISO: NTEXT SQL Server obsoleto → CLOB Oracle",
        requires_ddl_comment=True,
    ),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingSQLServerToOracle(
        "DATE",
        "DATE",
        warning_msg="DATE SQL Server (solo fecha) → DATE Oracle (incluye hora); hora será 00:00:00",
        severity="INFO",
    ),
    "TIME": TypeMappingSQLServerToOracle(
        "TIME",
        "VARCHAR2(15)",
        warning_msg="TIME SQL Server sin equivalente directo en Oracle; mapeado a VARCHAR2(15)",
        severity="WARNING",
        proposals=("VARCHAR2(15)", "INTERVAL DAY TO SECOND"),
        ddl_comment="-- AVISO: TIME → VARCHAR2(15) [A] | INTERVAL DAY TO SECOND [B]",
        requires_ddl_comment=True,
    ),
    "DATETIME": TypeMappingSQLServerToOracle(
        "DATETIME",
        "DATE",
        warning_msg="DATETIME SQL Server mapeado a DATE Oracle; fracciones de segundo (3ms precision) no preservadas",
        severity="INFO",
    ),
    "DATETIME2": TypeMappingSQLServerToOracle(
        "DATETIME2",
        "TIMESTAMP",
        warning_msg="DATETIME2 SQL Server mapeado a TIMESTAMP Oracle; hasta 7 decimales → Oracle soporta 9",
        severity="INFO",
    ),
    "SMALLDATETIME": TypeMappingSQLServerToOracle(
        "SMALLDATETIME",
        "DATE",
        warning_msg="SMALLDATETIME SQL Server (minutos) mapeado a DATE Oracle; segundos siempre 00",
        severity="INFO",
    ),
    "DATETIMEOFFSET": TypeMappingSQLServerToOracle(
        "DATETIMEOFFSET",
        "TIMESTAMP WITH TIME ZONE",
        warning_msg="DATETIMEOFFSET SQL Server mapeado a TIMESTAMP WITH TIME ZONE Oracle; verificar comportamiento TZ",
        severity="WARNING",
        ddl_comment="-- AVISO: DATETIMEOFFSET → TIMESTAMP WITH TIME ZONE; verificar preservación de offset",
        requires_ddl_comment=True,
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    # char_length=-1 indica MAX → BLOB en el transformer
    "BINARY": TypeMappingSQLServerToOracle("BINARY", "RAW"),
    "VARBINARY": TypeMappingSQLServerToOracle(
        "VARBINARY",
        "RAW",
        warning_msg="VARBINARY mapeado a RAW; Oracle RAW tiene límite 2000 bytes — usar BLOB si n>2000 o MAX",
        severity="WARNING",
        proposals=("RAW(n) si n<=2000", "BLOB si n>2000 o MAX"),
        ddl_comment="-- AVISO: VARBINARY → RAW (máx 2000 bytes Oracle) | BLOB si n>2000",
        requires_ddl_comment=True,
    ),
    # IMAGE: obsoleto en SQL Server 2005+
    "IMAGE": TypeMappingSQLServerToOracle(
        "IMAGE",
        "BLOB",
        warning_msg="IMAGE SQL Server (obsoleto desde 2005) mapeado a BLOB Oracle",
        severity="WARNING",
        ddl_comment="-- AVISO: IMAGE SQL Server obsoleto → BLOB Oracle",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "UNIQUEIDENTIFIER": TypeMappingSQLServerToOracle(
        "UNIQUEIDENTIFIER",
        "CHAR(36)",
        warning_msg="UNIQUEIDENTIFIER SQL Server mapeado a CHAR(36) (formato 8-4-4-4-12 en Oracle)",
        severity="INFO",
    ),
    "XML": TypeMappingSQLServerToOracle(
        "XML",
        "CLOB",
        warning_msg="XML SQL Server mapeado a CLOB Oracle; Oracle 12c+ soporta XMLType (propuesta B)",
        severity="WARNING",
        proposals=("CLOB", "XMLType -- Oracle 12c+"),
        ddl_comment="-- AVISO: XML → CLOB [A] | XMLType Oracle 12c+ [B]",
        requires_ddl_comment=True,
    ),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOGRAPHY": TypeMappingSQLServerToOracle(
        "GEOGRAPHY",
        "CLOB",
        warning_msg="GEOGRAPHY SQL Server sin equivalente directo; mapeado a CLOB. Oracle usa SDO_GEOMETRY",
        severity="ERROR",
        proposals=("CLOB", "SDO_GEOMETRY -- Oracle Spatial"),
        ddl_comment="-- AVISO: GEOGRAPHY → CLOB [A] | SDO_GEOMETRY Oracle Spatial [B]; requiere revisión",
        requires_ddl_comment=True,
    ),
    "GEOMETRY": TypeMappingSQLServerToOracle(
        "GEOMETRY",
        "CLOB",
        warning_msg="GEOMETRY SQL Server sin equivalente directo; mapeado a CLOB. Oracle usa SDO_GEOMETRY",
        severity="ERROR",
        proposals=("CLOB", "SDO_GEOMETRY -- Oracle Spatial"),
        ddl_comment="-- AVISO: GEOMETRY → CLOB [A] | SDO_GEOMETRY Oracle Spatial [B]; requiere revisión",
        requires_ddl_comment=True,
    ),
}


def resolve_sqlserver_type_oracle(sqlserver_type: str) -> TypeMappingSQLServerToOracle | None:
    """Busca el mapeo para un tipo SQL Server hacia Oracle (sin parámetros).

    Args:
        sqlserver_type: Tipo SQL Server en crudo (ej. "INT", "VARCHAR", "DATETIME2").

    Returns:
        TypeMappingSQLServerToOracle si existe, None si el tipo es desconocido.
    """
    key = sqlserver_type.strip().upper()
    return SQLSERVER_TO_ORACLE.get(key)


__all__: list[str] = [
    "TypeMappingSQLServerToOracle",
    "SQLSERVER_TO_ORACLE",
    "resolve_sqlserver_type_oracle",
]
