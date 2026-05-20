"""Mapeo exhaustivo de tipos SQL Server → MariaDB.

Cubre los tipos estándar de SQL Server con sus equivalentes MariaDB.
Los parámetros de longitud, precisión y escala se resuelven dinámicamente
en el transformer según los metadatos de la columna.

``source_base`` es el tipo SQL Server en MAYÚSCULAS sin parámetros.

Nota sobre char_length: SQL Server usa -1 como sentinel para MAX en VARCHAR(MAX),
NVARCHAR(MAX) y VARBINARY(MAX). El transformer lo detecta para emitir
TEXT/LONGTEXT/LONGBLOB según el tipo.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingSQLServerToMariaDB:
    """Definición de mapeo para un tipo SQL Server a MariaDB."""

    source_base: str
    mariadb_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico SQL Server → MariaDB.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
SQLSERVER_TO_MARIADB: dict[str, TypeMappingSQLServerToMariaDB] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INT": TypeMappingSQLServerToMariaDB("INT", "INT"),
    "BIGINT": TypeMappingSQLServerToMariaDB("BIGINT", "BIGINT"),
    "SMALLINT": TypeMappingSQLServerToMariaDB("SMALLINT", "SMALLINT"),
    # SQL Server TINYINT unsigned (0..255); MariaDB TINYINT signed (-128..127)
    # Se usa SMALLINT para evitar overflow en valores 128-255
    "TINYINT": TypeMappingSQLServerToMariaDB(
        "TINYINT",
        "SMALLINT",
        warning_msg=(
            "TINYINT SQL Server (0..255 unsigned) mapeado a SMALLINT MariaDB; "
            "usar TINYINT UNSIGNED en MariaDB si se desea preservar el rango exacto"
        ),
        severity="WARNING",
        proposals=("SMALLINT", "TINYINT UNSIGNED"),
        ddl_comment="-- AVISO: TINYINT SS (0-255) → SMALLINT MariaDB; considerar TINYINT UNSIGNED",
        requires_ddl_comment=True,
    ),
    "BIT": TypeMappingSQLServerToMariaDB(
        "BIT",
        "TINYINT(1)",
        warning_msg="BIT SQL Server (0/1/NULL) mapeado a TINYINT(1) MariaDB (equivalente a BOOL)",
        severity="INFO",
    ),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "DECIMAL": TypeMappingSQLServerToMariaDB("DECIMAL", "DECIMAL"),
    "NUMERIC": TypeMappingSQLServerToMariaDB("NUMERIC", "DECIMAL"),
    "FLOAT": TypeMappingSQLServerToMariaDB(
        "FLOAT",
        "DOUBLE",
        warning_msg="FLOAT SQL Server (IEEE 754 double) mapeado a DOUBLE MariaDB",
        severity="INFO",
    ),
    "REAL": TypeMappingSQLServerToMariaDB(
        "REAL",
        "FLOAT",
        warning_msg="REAL SQL Server (IEEE 754 single) mapeado a FLOAT MariaDB",
        severity="INFO",
    ),
    "MONEY": TypeMappingSQLServerToMariaDB(
        "MONEY",
        "DECIMAL(19,4)",
        warning_msg="MONEY SQL Server mapeado a DECIMAL(19,4) MariaDB",
        severity="INFO",
    ),
    "SMALLMONEY": TypeMappingSQLServerToMariaDB(
        "SMALLMONEY",
        "DECIMAL(10,4)",
        warning_msg="SMALLMONEY SQL Server mapeado a DECIMAL(10,4) MariaDB",
        severity="INFO",
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # char_length=-1 indica MAX → TEXT/LONGTEXT en el transformer
    "CHAR": TypeMappingSQLServerToMariaDB("CHAR", "CHAR"),
    "VARCHAR": TypeMappingSQLServerToMariaDB("VARCHAR", "VARCHAR"),
    # NCHAR/NVARCHAR: Unicode nativo SS → MariaDB usa charset utf8mb4 nativo
    "NCHAR": TypeMappingSQLServerToMariaDB(
        "NCHAR",
        "CHAR",
        warning_msg="NCHAR SQL Server (Unicode) mapeado a CHAR MariaDB; usar charset utf8mb4 en la BD destino",
        severity="INFO",
    ),
    "NVARCHAR": TypeMappingSQLServerToMariaDB(
        "NVARCHAR",
        "VARCHAR",
        warning_msg="NVARCHAR SQL Server (Unicode) mapeado a VARCHAR MariaDB; usar charset utf8mb4 en la BD destino",
        severity="INFO",
    ),
    "TEXT": TypeMappingSQLServerToMariaDB(
        "TEXT",
        "LONGTEXT",
        warning_msg="TEXT SQL Server (obsoleto desde 2005) mapeado a LONGTEXT MariaDB",
        severity="WARNING",
        ddl_comment="-- AVISO: TEXT SQL Server obsoleto → LONGTEXT MariaDB",
        requires_ddl_comment=True,
    ),
    "NTEXT": TypeMappingSQLServerToMariaDB(
        "NTEXT",
        "LONGTEXT",
        warning_msg="NTEXT SQL Server (obsoleto desde 2005) mapeado a LONGTEXT MariaDB",
        severity="WARNING",
        ddl_comment="-- AVISO: NTEXT SQL Server obsoleto → LONGTEXT MariaDB",
        requires_ddl_comment=True,
    ),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingSQLServerToMariaDB("DATE", "DATE"),
    "TIME": TypeMappingSQLServerToMariaDB("TIME", "TIME"),
    "DATETIME": TypeMappingSQLServerToMariaDB("DATETIME", "DATETIME"),
    # DATETIME2 puede tener hasta 7 decimales; MariaDB max 6
    "DATETIME2": TypeMappingSQLServerToMariaDB(
        "DATETIME2",
        "DATETIME(6)",
        warning_msg="DATETIME2 SQL Server (hasta 7 fracciones) mapeado a DATETIME(6) MariaDB; última fracción truncada",
        severity="INFO",
    ),
    "SMALLDATETIME": TypeMappingSQLServerToMariaDB(
        "SMALLDATETIME",
        "DATETIME",
        warning_msg="SMALLDATETIME SQL Server (precisión minutos) mapeado a DATETIME MariaDB",
        severity="INFO",
    ),
    # MariaDB no tiene tipo TZ-aware nativo; se usa VARCHAR(35) para preservar offset
    "DATETIMEOFFSET": TypeMappingSQLServerToMariaDB(
        "DATETIMEOFFSET",
        "VARCHAR(35)",
        warning_msg=(
            "DATETIMEOFFSET SQL Server (con offset TZ) mapeado a VARCHAR(35) MariaDB; "
            "MariaDB no tiene tipo datetime con zona horaria nativo"
        ),
        severity="WARNING",
        proposals=("VARCHAR(35)", "DATETIME -- si se descarta el offset"),
        ddl_comment="-- AVISO: DATETIMEOFFSET → VARCHAR(35) MariaDB; zona horaria no preservada semánticamente",
        requires_ddl_comment=True,
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    # char_length=-1 indica MAX → LONGBLOB en el transformer
    "BINARY": TypeMappingSQLServerToMariaDB("BINARY", "BINARY"),
    "VARBINARY": TypeMappingSQLServerToMariaDB("VARBINARY", "VARBINARY"),
    "IMAGE": TypeMappingSQLServerToMariaDB(
        "IMAGE",
        "LONGBLOB",
        warning_msg="IMAGE SQL Server (obsoleto desde 2005) mapeado a LONGBLOB MariaDB",
        severity="WARNING",
        ddl_comment="-- AVISO: IMAGE SQL Server obsoleto → LONGBLOB MariaDB",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "UNIQUEIDENTIFIER": TypeMappingSQLServerToMariaDB(
        "UNIQUEIDENTIFIER",
        "CHAR(36)",
        warning_msg="UNIQUEIDENTIFIER SQL Server mapeado a CHAR(36) MariaDB (formato 8-4-4-4-12)",
        severity="INFO",
    ),
    "XML": TypeMappingSQLServerToMariaDB(
        "XML",
        "LONGTEXT",
        warning_msg="XML SQL Server mapeado a LONGTEXT MariaDB; sin validación de esquema XML",
        severity="WARNING",
        ddl_comment="-- AVISO: XML → LONGTEXT MariaDB; sin validación XSD",
        requires_ddl_comment=True,
    ),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOGRAPHY": TypeMappingSQLServerToMariaDB(
        "GEOGRAPHY",
        "GEOMETRY",
        warning_msg=(
            "GEOGRAPHY SQL Server (coordenadas esféricas) mapeado a GEOMETRY MariaDB; "
            "formato de datos puede requerir conversión"
        ),
        severity="ERROR",
        ddl_comment="-- AVISO: GEOGRAPHY SS → GEOMETRY MariaDB; formato de datos distinto; revisar manualmente",
        requires_ddl_comment=True,
    ),
    "GEOMETRY": TypeMappingSQLServerToMariaDB(
        "GEOMETRY",
        "GEOMETRY",
        warning_msg="GEOMETRY SQL Server mapeado a GEOMETRY MariaDB; verificar compatibilidad de datos espaciales",
        severity="WARNING",
        ddl_comment="-- AVISO: GEOMETRY SS → GEOMETRY MariaDB; verificar compatibilidad de datos",
        requires_ddl_comment=True,
    ),
}


def resolve_sqlserver_type_mariadb(sqlserver_type: str) -> TypeMappingSQLServerToMariaDB | None:
    """Busca el mapeo para un tipo SQL Server hacia MariaDB (sin parámetros).

    Args:
        sqlserver_type: Tipo SQL Server en crudo (ej. "INT", "NVARCHAR", "DATETIME2").

    Returns:
        TypeMappingSQLServerToMariaDB si existe, None si el tipo es desconocido.
    """
    key = sqlserver_type.strip().upper()
    return SQLSERVER_TO_MARIADB.get(key)


__all__: list[str] = [
    "TypeMappingSQLServerToMariaDB",
    "SQLSERVER_TO_MARIADB",
    "resolve_sqlserver_type_mariadb",
]
