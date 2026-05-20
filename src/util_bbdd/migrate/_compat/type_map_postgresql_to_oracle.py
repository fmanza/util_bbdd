"""Mapeo exhaustivo de tipos PostgreSQL → Oracle.

Cubre los tipos estándar de PostgreSQL con sus equivalentes Oracle.
El campo ``oracle_type`` contiene el tipo Oracle base; los parámetros de longitud,
precisión y escala se resuelven dinámicamente en el transformer según los
metadatos de la columna (char_length, precision, scale).

``source_base`` es el tipo PostgreSQL en MAYÚSCULAS sin parámetros, equivalente
al valor de DATA_TYPE en INFORMATION_SCHEMA.COLUMNS devuelto en uppercase.
PostgreSQL usa tipos multi-palabra (ej. ``CHARACTER VARYING``,
``TIMESTAMP WITHOUT TIME ZONE``).

Nota: ``CHARACTER VARYING`` con ``char_length=None`` indica texto sin límite de
longitud → el transformer lo convierte a CLOB en Oracle.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingPostgreSQLToOracle:
    """Definición de mapeo para un tipo PostgreSQL a Oracle."""

    source_base: str
    oracle_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico PostgreSQL → Oracle.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
POSTGRESQL_TO_ORACLE: dict[str, TypeMappingPostgreSQLToOracle] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INTEGER": TypeMappingPostgreSQLToOracle("INTEGER", "NUMBER(10,0)"),
    "BIGINT": TypeMappingPostgreSQLToOracle("BIGINT", "NUMBER(19,0)"),
    "SMALLINT": TypeMappingPostgreSQLToOracle("SMALLINT", "NUMBER(5,0)"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    # NUMERIC/DECIMAL: precision/scale resueltos dinámicamente
    "NUMERIC": TypeMappingPostgreSQLToOracle("NUMERIC", "NUMBER"),
    "DECIMAL": TypeMappingPostgreSQLToOracle("DECIMAL", "NUMBER"),
    # PostgreSQL REAL equivale a IEEE 754 single precision (4 bytes)
    "REAL": TypeMappingPostgreSQLToOracle(
        "REAL",
        "BINARY_FLOAT",
        warning_msg="REAL PostgreSQL (IEEE 754 single ~7 dígitos) mapeado a BINARY_FLOAT Oracle",
        severity="INFO",
    ),
    # PostgreSQL DOUBLE PRECISION equivale a IEEE 754 double (8 bytes)
    "DOUBLE PRECISION": TypeMappingPostgreSQLToOracle(
        "DOUBLE PRECISION",
        "BINARY_DOUBLE",
        warning_msg="DOUBLE PRECISION PostgreSQL (IEEE 754 double) mapeado a BINARY_DOUBLE Oracle",
        severity="INFO",
    ),
    "MONEY": TypeMappingPostgreSQLToOracle(
        "MONEY",
        "NUMBER(19,4)",
        warning_msg="MONEY PostgreSQL mapeado a NUMBER(19,4); el símbolo de moneda se pierde",
        severity="WARNING",
        ddl_comment="-- AVISO: MONEY PostgreSQL → NUMBER(19,4); verificar formato de salida",
        requires_ddl_comment=True,
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # CHARACTER VARYING: char_length=None → CLOB; >4000 → CLOB; <=4000 → VARCHAR2(n)
    "CHARACTER VARYING": TypeMappingPostgreSQLToOracle("CHARACTER VARYING", "VARCHAR2"),
    # CHARACTER: CHAR(n) con longitud dinámica
    "CHARACTER": TypeMappingPostgreSQLToOracle("CHARACTER", "CHAR"),
    # TEXT: sin límite en PostgreSQL → CLOB Oracle
    "TEXT": TypeMappingPostgreSQLToOracle(
        "TEXT",
        "CLOB",
        warning_msg="TEXT PostgreSQL (sin límite) mapeado a CLOB Oracle; considerar VARCHAR2 si datos < 4000 chars",
        severity="INFO",
        ddl_comment="-- AVISO: TEXT → CLOB Oracle; considerar VARCHAR2 si datos < 4000 chars",
        requires_ddl_comment=True,
    ),
    # ── Booleano ─────────────────────────────────────────────────────────────────
    "BOOLEAN": TypeMappingPostgreSQLToOracle(
        "BOOLEAN",
        "NUMBER(1,0)",
        warning_msg="BOOLEAN PostgreSQL mapeado a NUMBER(1,0) Oracle; Oracle < 23c no tiene tipo BOOLEAN nativo",
        severity="WARNING",
        proposals=("NUMBER(1,0)", "CHAR(1) -- 'Y'/'N'"),
        ddl_comment="-- AVISO: BOOLEAN → NUMBER(1,0) [A] | CHAR(1) 'Y'/'N' [B]",
        requires_ddl_comment=True,
    ),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingPostgreSQLToOracle(
        "DATE",
        "DATE",
        warning_msg="DATE PostgreSQL (solo fecha) → DATE Oracle (incluye hora); hora será 00:00:00",
        severity="INFO",
    ),
    "TIME WITHOUT TIME ZONE": TypeMappingPostgreSQLToOracle(
        "TIME WITHOUT TIME ZONE",
        "VARCHAR2(15)",
        warning_msg="TIME WITHOUT TIME ZONE PostgreSQL sin equivalente directo en Oracle; mapeado a VARCHAR2(15)",
        severity="WARNING",
        proposals=("VARCHAR2(15)", "INTERVAL DAY TO SECOND"),
        ddl_comment="-- AVISO: TIME → VARCHAR2(15) [A] | INTERVAL DAY TO SECOND [B]",
        requires_ddl_comment=True,
    ),
    "TIME WITH TIME ZONE": TypeMappingPostgreSQLToOracle(
        "TIME WITH TIME ZONE",
        "VARCHAR2(21)",
        warning_msg="TIME WITH TIME ZONE PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(21)",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMETZ → VARCHAR2(21); verificar formato HH:MM:SS+HH:MM",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP WITHOUT TIME ZONE": TypeMappingPostgreSQLToOracle(
        "TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP"
    ),
    "TIMESTAMP WITH TIME ZONE": TypeMappingPostgreSQLToOracle(
        "TIMESTAMP WITH TIME ZONE",
        "TIMESTAMP WITH TIME ZONE",
        warning_msg="TIMESTAMP WITH TIME ZONE PostgreSQL mapeado a TIMESTAMP WITH TIME ZONE Oracle; verificar comportamiento TZ",
        severity="INFO",
    ),
    "INTERVAL": TypeMappingPostgreSQLToOracle(
        "INTERVAL",
        "INTERVAL DAY TO SECOND",
        warning_msg=(
            "INTERVAL PostgreSQL (año-mes y día-hora) mapeado a INTERVAL DAY TO SECOND Oracle; "
            "intervalos año-mes (YEAR TO MONTH) requieren revisión manual"
        ),
        severity="WARNING",
        proposals=("INTERVAL DAY TO SECOND", "INTERVAL YEAR TO MONTH"),
        ddl_comment="-- AVISO: INTERVAL PG → INTERVAL DAY TO SECOND [A] | YEAR TO MONTH [B]; revisar semántica",
        requires_ddl_comment=True,
    ),
    # ── UUID ──────────────────────────────────────────────────────────────────────
    "UUID": TypeMappingPostgreSQLToOracle(
        "UUID",
        "CHAR(36)",
        warning_msg="UUID PostgreSQL mapeado a CHAR(36) Oracle (formato 8-4-4-4-12); RAW(16) es alternativa compacta",
        severity="INFO",
        proposals=("CHAR(36)", "RAW(16)"),
    ),
    # ── JSON ──────────────────────────────────────────────────────────────────────
    "JSON": TypeMappingPostgreSQLToOracle(
        "JSON",
        "CLOB",
        warning_msg="JSON PostgreSQL mapeado a CLOB Oracle; Oracle 21c soporta tipo JSON nativo (propuesta B)",
        severity="WARNING",
        proposals=("CLOB", "JSON -- Oracle 21c+"),
        ddl_comment="-- AVISO: JSON → CLOB [A] | JSON nativo Oracle 21c+ [B]",
        requires_ddl_comment=True,
    ),
    "JSONB": TypeMappingPostgreSQLToOracle(
        "JSONB",
        "CLOB",
        warning_msg="JSONB PostgreSQL (JSON binario) mapeado a CLOB Oracle; Oracle 21c soporta JSON nativo",
        severity="WARNING",
        proposals=("CLOB", "JSON -- Oracle 21c+"),
        ddl_comment="-- AVISO: JSONB → CLOB [A] | JSON nativo Oracle 21c+ [B]",
        requires_ddl_comment=True,
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BYTEA": TypeMappingPostgreSQLToOracle("BYTEA", "BLOB"),
    # ── XML ───────────────────────────────────────────────────────────────────────
    "XML": TypeMappingPostgreSQLToOracle(
        "XML",
        "CLOB",
        warning_msg="XML PostgreSQL mapeado a CLOB Oracle; Oracle 12c+ soporta XMLType (propuesta B)",
        severity="WARNING",
        proposals=("CLOB", "XMLType -- Oracle 12c+"),
        ddl_comment="-- AVISO: XML → CLOB [A] | XMLType Oracle 12c+ [B]",
        requires_ddl_comment=True,
    ),
    # ── Red ───────────────────────────────────────────────────────────────────────
    "INET": TypeMappingPostgreSQLToOracle(
        "INET",
        "VARCHAR2(45)",
        warning_msg="INET PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(45) (IPv6 máx 39+prefijo)",
        severity="WARNING",
        ddl_comment="-- AVISO: INET → VARCHAR2(45); sin validación de formato en Oracle",
        requires_ddl_comment=True,
    ),
    "CIDR": TypeMappingPostgreSQLToOracle(
        "CIDR",
        "VARCHAR2(45)",
        warning_msg="CIDR PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(45)",
        severity="WARNING",
        ddl_comment="-- AVISO: CIDR → VARCHAR2(45); sin validación de rango en Oracle",
        requires_ddl_comment=True,
    ),
    "MACADDR": TypeMappingPostgreSQLToOracle(
        "MACADDR",
        "VARCHAR2(17)",
        warning_msg="MACADDR PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(17) (AA:BB:CC:DD:EE:FF)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR → VARCHAR2(17)",
        requires_ddl_comment=True,
    ),
    "MACADDR8": TypeMappingPostgreSQLToOracle(
        "MACADDR8",
        "VARCHAR2(23)",
        warning_msg="MACADDR8 PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(23)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR8 → VARCHAR2(23)",
        requires_ddl_comment=True,
    ),
    # ── Bit strings ───────────────────────────────────────────────────────────────
    # BIT(n): almacena cadena de bits '10110'; char_length=n → CHAR(n) Oracle
    "BIT": TypeMappingPostgreSQLToOracle(
        "BIT",
        "CHAR",
        warning_msg="BIT(n) PostgreSQL (cadena de bits) mapeado a CHAR(n) Oracle; almacena representación '0'/'1'",
        severity="WARNING",
        ddl_comment="-- AVISO: BIT(n) → CHAR(n); almacena representación textual de bits",
        requires_ddl_comment=True,
    ),
    "BIT VARYING": TypeMappingPostgreSQLToOracle(
        "BIT VARYING",
        "VARCHAR2",
        warning_msg="BIT VARYING PostgreSQL mapeado a VARCHAR2(n) Oracle; almacena representación textual",
        severity="WARNING",
        ddl_comment="-- AVISO: BIT VARYING → VARCHAR2(n); representación textual de bits",
        requires_ddl_comment=True,
    ),
    # ── OID ───────────────────────────────────────────────────────────────────────
    "OID": TypeMappingPostgreSQLToOracle(
        "OID",
        "NUMBER(10,0)",
        warning_msg="OID PostgreSQL (object identifier interno) mapeado a NUMBER(10,0); verificar uso",
        severity="WARNING",
        ddl_comment="-- AVISO: OID → NUMBER(10,0); OID es identificador interno de PostgreSQL",
        requires_ddl_comment=True,
    ),
    # ── Full-text search ─────────────────────────────────────────────────────────
    "TSVECTOR": TypeMappingPostgreSQLToOracle(
        "TSVECTOR",
        "CLOB",
        warning_msg="TSVECTOR PostgreSQL sin equivalente en Oracle; mapeado a CLOB — revisar implementación de búsqueda",
        severity="ERROR",
        ddl_comment="-- ERROR: TSVECTOR → CLOB; implementar full-text search Oracle Text manualmente",
        requires_ddl_comment=True,
    ),
    "TSQUERY": TypeMappingPostgreSQLToOracle(
        "TSQUERY",
        "CLOB",
        warning_msg="TSQUERY PostgreSQL sin equivalente en Oracle; mapeado a CLOB — revisar implementación de búsqueda",
        severity="ERROR",
        ddl_comment="-- ERROR: TSQUERY → CLOB; revisar implementación de búsqueda",
        requires_ddl_comment=True,
    ),
    # ── Tipos geométricos ────────────────────────────────────────────────────────
    "POINT": TypeMappingPostgreSQLToOracle(
        "POINT", "VARCHAR2(100)",
        warning_msg="POINT PostgreSQL sin equivalente directo en Oracle; mapeado a VARCHAR2(100). Oracle usa SDO_GEOMETRY",
        severity="ERROR",
        proposals=("VARCHAR2(100)", "SDO_GEOMETRY -- Oracle Spatial"),
        ddl_comment="-- ERROR: POINT → VARCHAR2(100) [A] | SDO_GEOMETRY Oracle Spatial [B]",
        requires_ddl_comment=True,
    ),
    "LINE": TypeMappingPostgreSQLToOracle(
        "LINE", "VARCHAR2(100)",
        warning_msg="LINE PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LINE → VARCHAR2(100); revisar con Oracle Spatial",
        requires_ddl_comment=True,
    ),
    "LSEG": TypeMappingPostgreSQLToOracle(
        "LSEG", "VARCHAR2(100)",
        warning_msg="LSEG PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LSEG → VARCHAR2(100)",
        requires_ddl_comment=True,
    ),
    "BOX": TypeMappingPostgreSQLToOracle(
        "BOX", "VARCHAR2(100)",
        warning_msg="BOX PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: BOX → VARCHAR2(100)",
        requires_ddl_comment=True,
    ),
    "PATH": TypeMappingPostgreSQLToOracle(
        "PATH", "VARCHAR2(200)",
        warning_msg="PATH PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(200)",
        severity="ERROR",
        ddl_comment="-- ERROR: PATH → VARCHAR2(200)",
        requires_ddl_comment=True,
    ),
    "POLYGON": TypeMappingPostgreSQLToOracle(
        "POLYGON", "VARCHAR2(200)",
        warning_msg="POLYGON PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(200)",
        severity="ERROR",
        ddl_comment="-- ERROR: POLYGON → VARCHAR2(200)",
        requires_ddl_comment=True,
    ),
    "CIRCLE": TypeMappingPostgreSQLToOracle(
        "CIRCLE", "VARCHAR2(100)",
        warning_msg="CIRCLE PostgreSQL sin equivalente en Oracle; mapeado a VARCHAR2(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: CIRCLE → VARCHAR2(100)",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "ARRAY": TypeMappingPostgreSQLToOracle(
        "ARRAY",
        "CLOB",
        warning_msg="Tipo ARRAY PostgreSQL sin equivalente en Oracle; mapeado a CLOB — revisar estructura",
        severity="ERROR",
        ddl_comment="-- ERROR: ARRAY → CLOB; normalizar en tablas separadas (1FN)",
        requires_ddl_comment=True,
    ),
    "USER-DEFINED": TypeMappingPostgreSQLToOracle(
        "USER-DEFINED",
        "CLOB",
        warning_msg="Tipo USER-DEFINED (enum/composite) PostgreSQL sin equivalente en Oracle; mapeado a CLOB",
        severity="ERROR",
        ddl_comment="-- ERROR: USER-DEFINED → CLOB; revisar tipo personalizado",
        requires_ddl_comment=True,
    ),
}


def resolve_postgresql_type_oracle(pg_type: str) -> TypeMappingPostgreSQLToOracle | None:
    """Busca el mapeo para un tipo PostgreSQL hacia Oracle (sin parámetros).

    Args:
        pg_type: Tipo PostgreSQL en crudo (ej. "INTEGER", "CHARACTER VARYING",
                 "TIMESTAMP WITHOUT TIME ZONE").

    Returns:
        TypeMappingPostgreSQLToOracle si existe, None si el tipo es desconocido.
    """
    key = pg_type.strip().upper()
    return POSTGRESQL_TO_ORACLE.get(key)


__all__: list[str] = [
    "TypeMappingPostgreSQLToOracle",
    "POSTGRESQL_TO_ORACLE",
    "resolve_postgresql_type_oracle",
]
