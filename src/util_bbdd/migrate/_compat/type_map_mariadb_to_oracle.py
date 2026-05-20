"""Mapeo exhaustivo de tipos MariaDB → Oracle.

Cubre los tipos más comunes de MariaDB con sus equivalentes Oracle.
El campo ``oracle_type`` contiene el tipo Oracle base; los parámetros de longitud,
precisión y escala se resuelven dinámicamente en el transformer según los
metadatos de la columna (char_length, precision, scale).

Nota sobre ``source_base``: el campo es el tipo MariaDB en MAYÚSCULAS sin parámetros
(ej. "INT", "VARCHAR", "DATETIME"), equivalente al valor de DATA_TYPE en
INFORMATION_SCHEMA.COLUMNS devuelto en uppercase.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingMariaToOracle:
    """Definición de mapeo para un tipo MariaDB a Oracle."""

    source_base: str
    oracle_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico MariaDB → Oracle.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
MARIADB_TO_ORACLE: dict[str, TypeMappingMariaToOracle] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "TINYINT": TypeMappingMariaToOracle("TINYINT", "NUMBER(3,0)"),
    "BOOL": TypeMappingMariaToOracle(
        "BOOL",
        "NUMBER(1,0)",
        warning_msg="BOOL mapeado a NUMBER(1,0); Oracle < 23c no tiene tipo BOOLEAN nativo",
        severity="INFO",
    ),
    "BOOLEAN": TypeMappingMariaToOracle(
        "BOOLEAN",
        "NUMBER(1,0)",
        warning_msg="BOOLEAN mapeado a NUMBER(1,0); Oracle < 23c no tiene tipo BOOLEAN nativo",
        severity="INFO",
    ),
    "SMALLINT": TypeMappingMariaToOracle("SMALLINT", "NUMBER(5,0)"),
    "MEDIUMINT": TypeMappingMariaToOracle("MEDIUMINT", "NUMBER(7,0)"),
    "INT": TypeMappingMariaToOracle("INT", "NUMBER(10,0)"),
    "INTEGER": TypeMappingMariaToOracle("INTEGER", "NUMBER(10,0)"),
    "BIGINT": TypeMappingMariaToOracle("BIGINT", "NUMBER(19,0)"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    # DECIMAL/NUMERIC: oracle_type="NUMBER"; precision/scale resueltos dinámicamente
    "DECIMAL": TypeMappingMariaToOracle("DECIMAL", "NUMBER"),
    "NUMERIC": TypeMappingMariaToOracle("NUMERIC", "NUMBER"),
    "FLOAT": TypeMappingMariaToOracle(
        "FLOAT",
        "BINARY_FLOAT",
        warning_msg="FLOAT mapeado a BINARY_FLOAT (IEEE 754 single ~7 dígitos); posible diferencia de precisión",
        severity="INFO",
    ),
    "DOUBLE": TypeMappingMariaToOracle(
        "DOUBLE",
        "BINARY_DOUBLE",
        warning_msg="DOUBLE mapeado a BINARY_DOUBLE (IEEE 754 double)",
        severity="INFO",
    ),
    "DOUBLE PRECISION": TypeMappingMariaToOracle("DOUBLE PRECISION", "BINARY_DOUBLE"),
    "REAL": TypeMappingMariaToOracle("REAL", "BINARY_FLOAT"),
    "BIT": TypeMappingMariaToOracle(
        "BIT",
        "RAW",
        warning_msg="BIT mapeado a RAW en Oracle; BIT(1) puede preferirse como NUMBER(1,0)",
        severity="WARNING",
        proposals=("RAW(n_bytes)", "NUMBER(1,0) para BIT(1)"),
        ddl_comment="-- AVISO: BIT → RAW; revisar si BIT(1) se prefiere como NUMBER(1,0)",
        requires_ddl_comment=True,
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # VARCHAR/CHAR: oracle_type sin parámetros; char_length resuelto dinámicamente
    "CHAR": TypeMappingMariaToOracle("CHAR", "CHAR"),
    "VARCHAR": TypeMappingMariaToOracle("VARCHAR", "VARCHAR2"),
    "TINYTEXT": TypeMappingMariaToOracle(
        "TINYTEXT",
        "VARCHAR2",
        warning_msg="TINYTEXT mapeado a VARCHAR2(255)",
        severity="INFO",
    ),
    "TEXT": TypeMappingMariaToOracle(
        "TEXT",
        "CLOB",
        warning_msg="TEXT mapeado a CLOB en Oracle",
        severity="INFO",
    ),
    "MEDIUMTEXT": TypeMappingMariaToOracle("MEDIUMTEXT", "CLOB"),
    "LONGTEXT": TypeMappingMariaToOracle("LONGTEXT", "CLOB"),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BINARY": TypeMappingMariaToOracle("BINARY", "RAW"),
    "VARBINARY": TypeMappingMariaToOracle(
        "VARBINARY",
        "RAW",
        warning_msg="VARBINARY mapeado a RAW; Oracle RAW tiene límite de 2000 bytes — usar BLOB si n>2000",
        severity="WARNING",
        proposals=("RAW(n) si n<=2000", "BLOB si n>2000"),
        ddl_comment="-- AVISO: VARBINARY → RAW (máx 2000 bytes Oracle); usar BLOB si n>2000",
        requires_ddl_comment=True,
    ),
    "TINYBLOB": TypeMappingMariaToOracle("TINYBLOB", "BLOB"),
    "BLOB": TypeMappingMariaToOracle("BLOB", "BLOB"),
    "MEDIUMBLOB": TypeMappingMariaToOracle("MEDIUMBLOB", "BLOB"),
    "LONGBLOB": TypeMappingMariaToOracle("LONGBLOB", "BLOB"),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingMariaToOracle(
        "DATE",
        "DATE",
        warning_msg="DATE MariaDB (solo fecha) → DATE Oracle (incluye hora); hora será 00:00:00",
        severity="INFO",
    ),
    "TIME": TypeMappingMariaToOracle(
        "TIME",
        "VARCHAR2(15)",
        warning_msg="TIME sin equivalente directo en Oracle; mapeado a VARCHAR2(15) (propuesta A)",
        severity="WARNING",
        proposals=("VARCHAR2(15)", "INTERVAL DAY TO SECOND"),
        ddl_comment="-- AVISO: TIME → VARCHAR2(15) [A] | INTERVAL DAY TO SECOND [B]",
        requires_ddl_comment=True,
    ),
    "DATETIME": TypeMappingMariaToOracle(
        "DATETIME",
        "DATE",
        warning_msg="DATETIME mapeado a DATE Oracle; fracciones de segundo de DATETIME(fsp>0) no preservadas",
        severity="INFO",
    ),
    "TIMESTAMP": TypeMappingMariaToOracle(
        "TIMESTAMP",
        "TIMESTAMP",
        warning_msg="TIMESTAMP MariaDB (UTC internamente) → TIMESTAMP Oracle (sin zona); revisar comportamiento TZ",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMP MariaDB → TIMESTAMP Oracle; zona horaria no preservada",
        requires_ddl_comment=True,
    ),
    "YEAR": TypeMappingMariaToOracle(
        "YEAR",
        "NUMBER(4,0)",
        warning_msg="YEAR MariaDB (1901-2155) mapeado a NUMBER(4,0)",
        severity="INFO",
    ),
    # ── JSON y tipos especiales ──────────────────────────────────────────────────
    "JSON": TypeMappingMariaToOracle(
        "JSON",
        "CLOB",
        warning_msg="JSON mapeado a CLOB; Oracle 21c+ soporta tipo JSON nativo (propuesta B)",
        severity="WARNING",
        proposals=("CLOB", "JSON -- Oracle 21c+"),
        ddl_comment="-- AVISO: JSON → CLOB [A] | JSON Oracle 21c+ [B]",
        requires_ddl_comment=True,
    ),
    "ENUM": TypeMappingMariaToOracle(
        "ENUM",
        "VARCHAR2",
        warning_msg="ENUM mapeado a VARCHAR2(255); añadir CHECK constraint manualmente para restricción de dominio",
        severity="WARNING",
        proposals=("VARCHAR2(255)", "CHECK (col IN ('v1','v2',...))"),
        ddl_comment="-- AVISO: ENUM → VARCHAR2(255); añadir CHECK constraint para restricción de dominio",
        requires_ddl_comment=True,
    ),
    "SET": TypeMappingMariaToOracle(
        "SET",
        "VARCHAR2",
        warning_msg="SET (múltiples valores) mapeado a VARCHAR2(255); semántica de conjunto no preservada",
        severity="WARNING",
        proposals=("VARCHAR2(255)", "CLOB -- si valores muy largos"),
        ddl_comment="-- AVISO: SET → VARCHAR2(255); semántica de conjunto no preservada",
        requires_ddl_comment=True,
    ),
    "UUID": TypeMappingMariaToOracle(
        "UUID",
        "CHAR(36)",
        warning_msg="UUID mapeado a CHAR(36) (formato string estándar 8-4-4-4-12)",
        severity="INFO",
    ),
    # ── Tipos espaciales ─────────────────────────────────────────────────────────
    "GEOMETRY": TypeMappingMariaToOracle(
        "GEOMETRY",
        "CLOB",
        warning_msg="GEOMETRY sin equivalente directo; mapeado a CLOB. Oracle usa SDO_GEOMETRY (Oracle Spatial)",
        severity="ERROR",
        proposals=("CLOB", "SDO_GEOMETRY -- Oracle Spatial"),
        ddl_comment="-- AVISO: GEOMETRY → CLOB [A] | SDO_GEOMETRY Oracle Spatial [B]; requiere revisión",
        requires_ddl_comment=True,
    ),
    "POINT": TypeMappingMariaToOracle(
        "POINT",
        "CLOB",
        warning_msg="POINT sin equivalente directo; mapeado a CLOB",
        severity="ERROR",
        ddl_comment="-- AVISO: POINT → CLOB; requiere revisión manual",
        requires_ddl_comment=True,
    ),
    "LINESTRING": TypeMappingMariaToOracle(
        "LINESTRING",
        "CLOB",
        warning_msg="LINESTRING sin equivalente directo; mapeado a CLOB",
        severity="ERROR",
        ddl_comment="-- AVISO: LINESTRING → CLOB; requiere revisión manual",
        requires_ddl_comment=True,
    ),
    "POLYGON": TypeMappingMariaToOracle(
        "POLYGON",
        "CLOB",
        warning_msg="POLYGON sin equivalente directo; mapeado a CLOB",
        severity="ERROR",
        ddl_comment="-- AVISO: POLYGON → CLOB; requiere revisión manual",
        requires_ddl_comment=True,
    ),
}


def resolve_mariadb_type_oracle(mariadb_type: str) -> TypeMappingMariaToOracle | None:
    """Busca el mapeo para un tipo MariaDB hacia Oracle (sin parámetros).

    Args:
        mariadb_type: Tipo MariaDB en crudo (ej. "INT", "VARCHAR", "DATETIME").

    Returns:
        TypeMappingMariaToOracle si existe, None si el tipo es desconocido.
    """
    key = mariadb_type.strip().upper()
    return MARIADB_TO_ORACLE.get(key)


__all__: list[str] = [
    "TypeMappingMariaToOracle",
    "MARIADB_TO_ORACLE",
    "resolve_mariadb_type_oracle",
]
