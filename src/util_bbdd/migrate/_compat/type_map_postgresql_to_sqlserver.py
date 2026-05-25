"""Mapeo exhaustivo de tipos PostgreSQL → SQL Server.

Cubre los tipos estándar de PostgreSQL con sus equivalentes SQL Server.
El campo ``ss_type`` contiene el tipo SQL Server base o completo; los
parámetros dinámicos (longitud, precisión, escala) se resuelven en el transformer.

``source_base`` es el tipo PostgreSQL en MAYÚSCULAS sin parámetros, equivalente
al valor de DATA_TYPE en INFORMATION_SCHEMA.COLUMNS devuelto en uppercase.
PostgreSQL usa tipos multi-palabra (ej. ``CHARACTER VARYING``,
``TIMESTAMP WITHOUT TIME ZONE``).

Nota: ``CHARACTER VARYING`` con ``char_length=None`` indica texto sin límite
→ el transformer lo convierte a NVARCHAR(MAX) en SQL Server.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingPostgreSQLToSQLServer:
    """Definición de mapeo para un tipo PostgreSQL a SQL Server."""

    source_base: str
    ss_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


_NVARCHAR_MAX = "NVARCHAR(MAX)"
_VARCHAR_100 = "VARCHAR(100)"
_VARCHAR_200 = "VARCHAR(200)"

# Mapeo canónico PostgreSQL → SQL Server.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
POSTGRESQL_TO_SQLSERVER: dict[str, TypeMappingPostgreSQLToSQLServer] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INTEGER": TypeMappingPostgreSQLToSQLServer("INTEGER", "INT"),
    "BIGINT": TypeMappingPostgreSQLToSQLServer("BIGINT", "BIGINT"),
    "SMALLINT": TypeMappingPostgreSQLToSQLServer("SMALLINT", "SMALLINT"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "NUMERIC": TypeMappingPostgreSQLToSQLServer("NUMERIC", "NUMERIC"),
    "DECIMAL": TypeMappingPostgreSQLToSQLServer("DECIMAL", "DECIMAL"),
    "REAL": TypeMappingPostgreSQLToSQLServer("REAL", "REAL"),
    "DOUBLE PRECISION": TypeMappingPostgreSQLToSQLServer(
        "DOUBLE PRECISION",
        "FLOAT",
        warning_msg="DOUBLE PRECISION PostgreSQL (IEEE 754 double) mapeado a FLOAT SQL Server",
        severity="INFO",
    ),
    "MONEY": TypeMappingPostgreSQLToSQLServer(
        "MONEY",
        "MONEY",
        warning_msg="MONEY PostgreSQL mapeado a MONEY SQL Server; verificar símbolo de moneda",
        severity="INFO",
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # CHARACTER VARYING: char_length=None → NVARCHAR(MAX); >4000 → NVARCHAR(MAX)
    "CHARACTER VARYING": TypeMappingPostgreSQLToSQLServer("CHARACTER VARYING", "NVARCHAR"),
    "CHARACTER": TypeMappingPostgreSQLToSQLServer("CHARACTER", "NCHAR"),
    "TEXT": TypeMappingPostgreSQLToSQLServer("TEXT", _NVARCHAR_MAX),
    # ── Booleano ─────────────────────────────────────────────────────────────────
    "BOOLEAN": TypeMappingPostgreSQLToSQLServer(
        "BOOLEAN",
        "BIT",
        warning_msg="BOOLEAN PostgreSQL mapeado a BIT SQL Server; BIT acepta 0/1/NULL",
        severity="INFO",
    ),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingPostgreSQLToSQLServer("DATE", "DATE"),
    "TIME WITHOUT TIME ZONE": TypeMappingPostgreSQLToSQLServer("TIME WITHOUT TIME ZONE", "TIME(6)"),
    "TIME WITH TIME ZONE": TypeMappingPostgreSQLToSQLServer(
        "TIME WITH TIME ZONE",
        "VARCHAR(21)",
        warning_msg="TIME WITH TIME ZONE PostgreSQL sin equivalente directo en SQL Server; mapeado a VARCHAR(21)",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMETZ → VARCHAR(21); SQL Server TIME no soporta zona horaria",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP WITHOUT TIME ZONE": TypeMappingPostgreSQLToSQLServer("TIMESTAMP WITHOUT TIME ZONE", "DATETIME2(6)"),
    "TIMESTAMP WITH TIME ZONE": TypeMappingPostgreSQLToSQLServer(
        "TIMESTAMP WITH TIME ZONE",
        "DATETIMEOFFSET(6)",
        warning_msg="TIMESTAMP WITH TIME ZONE PostgreSQL mapeado a DATETIMEOFFSET(6) SQL Server; verificar comportamiento TZ",
        severity="INFO",
    ),
    "INTERVAL": TypeMappingPostgreSQLToSQLServer(
        "INTERVAL",
        "VARCHAR(30)",
        warning_msg="INTERVAL PostgreSQL sin equivalente directo en SQL Server; mapeado a VARCHAR(30)",
        severity="WARNING",
        ddl_comment="-- AVISO: INTERVAL → VARCHAR(30); revisar lógica de cálculo de intervalos",
        requires_ddl_comment=True,
    ),
    # ── UUID ──────────────────────────────────────────────────────────────────────
    "UUID": TypeMappingPostgreSQLToSQLServer(
        "UUID",
        "UNIQUEIDENTIFIER",
        warning_msg="UUID PostgreSQL mapeado a UNIQUEIDENTIFIER SQL Server",
        severity="INFO",
    ),
    # ── JSON ──────────────────────────────────────────────────────────────────────
    "JSON": TypeMappingPostgreSQLToSQLServer(
        "JSON",
        _NVARCHAR_MAX,
        warning_msg=(
            "JSON PostgreSQL mapeado a NVARCHAR(MAX) SQL Server; "
            "SQL Server 2016+ soporta JSON vía OPENJSON/FOR JSON pero no tiene tipo nativo"
        ),
        severity="WARNING",
        ddl_comment="-- AVISO: JSON → NVARCHAR(MAX); usar OPENJSON/FOR JSON en SS 2016+",
        requires_ddl_comment=True,
    ),
    "JSONB": TypeMappingPostgreSQLToSQLServer(
        "JSONB",
        _NVARCHAR_MAX,
        warning_msg="JSONB PostgreSQL mapeado a NVARCHAR(MAX) SQL Server; sin tipo JSONB nativo",
        severity="WARNING",
        ddl_comment="-- AVISO: JSONB → NVARCHAR(MAX); SQL Server no tiene JSONB nativo",
        requires_ddl_comment=True,
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BYTEA": TypeMappingPostgreSQLToSQLServer("BYTEA", "VARBINARY(MAX)"),
    # ── XML ───────────────────────────────────────────────────────────────────────
    "XML": TypeMappingPostgreSQLToSQLServer(
        "XML",
        "XML",
        warning_msg="XML PostgreSQL mapeado a XML SQL Server (tipo nativo disponible)",
        severity="INFO",
    ),
    # ── Red ───────────────────────────────────────────────────────────────────────
    "INET": TypeMappingPostgreSQLToSQLServer(
        "INET",
        "VARCHAR(45)",
        warning_msg="INET PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(45)",
        severity="WARNING",
        ddl_comment="-- AVISO: INET → VARCHAR(45); sin validación de formato IP en SQL Server",
        requires_ddl_comment=True,
    ),
    "CIDR": TypeMappingPostgreSQLToSQLServer(
        "CIDR",
        "VARCHAR(45)",
        warning_msg="CIDR PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(45)",
        severity="WARNING",
        ddl_comment="-- AVISO: CIDR → VARCHAR(45); sin validación de rango CIDR en SQL Server",
        requires_ddl_comment=True,
    ),
    "MACADDR": TypeMappingPostgreSQLToSQLServer(
        "MACADDR",
        "VARCHAR(17)",
        warning_msg="MACADDR PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(17)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR → VARCHAR(17)",
        requires_ddl_comment=True,
    ),
    "MACADDR8": TypeMappingPostgreSQLToSQLServer(
        "MACADDR8",
        "VARCHAR(23)",
        warning_msg="MACADDR8 PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(23)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR8 → VARCHAR(23)",
        requires_ddl_comment=True,
    ),
    # ── Bit strings ───────────────────────────────────────────────────────────────
    # SQL Server BIT es 0/1, no BIT(n); para BIT(1) el mapeo es directo
    "BIT": TypeMappingPostgreSQLToSQLServer(
        "BIT",
        "BIT",
        warning_msg=(
            "BIT(n) PostgreSQL (cadena de n bits) mapeado a BIT SQL Server (solo 0/1); "
            "BIT(n) con n>1 requiere VARBINARY o CHAR"
        ),
        severity="WARNING",
        proposals=("BIT -- si n=1", "VARBINARY(n) -- si n>1"),
        ddl_comment="-- AVISO: BIT(n) PG → BIT SS solo si n=1; usar VARBINARY para n>1",
        requires_ddl_comment=True,
    ),
    "BIT VARYING": TypeMappingPostgreSQLToSQLServer(
        "BIT VARYING",
        "VARBINARY",
        warning_msg="BIT VARYING PostgreSQL mapeado a VARBINARY(n) SQL Server",
        severity="WARNING",
        ddl_comment="-- AVISO: BIT VARYING → VARBINARY(n); almacena representación binaria",
        requires_ddl_comment=True,
    ),
    # ── OID ───────────────────────────────────────────────────────────────────────
    "OID": TypeMappingPostgreSQLToSQLServer(
        "OID",
        "INT",
        warning_msg="OID PostgreSQL (object identifier interno) mapeado a INT SQL Server; verificar uso",
        severity="WARNING",
        ddl_comment="-- AVISO: OID → INT; OID es identificador interno de PostgreSQL",
        requires_ddl_comment=True,
    ),
    # ── Full-text search ─────────────────────────────────────────────────────────
    "TSVECTOR": TypeMappingPostgreSQLToSQLServer(
        "TSVECTOR",
        _NVARCHAR_MAX,
        warning_msg="TSVECTOR PostgreSQL sin equivalente en SQL Server; mapeado a NVARCHAR(MAX) — revisar full-text search",
        severity="ERROR",
        ddl_comment="-- ERROR: TSVECTOR → NVARCHAR(MAX); implementar Full-Text Index SQL Server manualmente",
        requires_ddl_comment=True,
    ),
    "TSQUERY": TypeMappingPostgreSQLToSQLServer(
        "TSQUERY",
        _NVARCHAR_MAX,
        warning_msg="TSQUERY PostgreSQL sin equivalente en SQL Server; mapeado a NVARCHAR(MAX)",
        severity="ERROR",
        ddl_comment="-- ERROR: TSQUERY → NVARCHAR(MAX); revisar implementación de búsqueda",
        requires_ddl_comment=True,
    ),
    # ── Tipos geométricos ────────────────────────────────────────────────────────
    "POINT": TypeMappingPostgreSQLToSQLServer(
        "POINT",
        _VARCHAR_100,
        warning_msg="POINT PostgreSQL sin equivalente directo en SQL Server; mapeado a VARCHAR(100). SQL Server usa geometry/geography",
        severity="ERROR",
        proposals=(_VARCHAR_100, "geometry -- SQL Server Spatial"),
        ddl_comment="-- ERROR: POINT → VARCHAR(100) [A] | geometry SQL Server Spatial [B]",
        requires_ddl_comment=True,
    ),
    "LINE": TypeMappingPostgreSQLToSQLServer(
        "LINE",
        _VARCHAR_100,
        warning_msg="LINE PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LINE → VARCHAR(100); revisar con SQL Server Spatial",
        requires_ddl_comment=True,
    ),
    "LSEG": TypeMappingPostgreSQLToSQLServer(
        "LSEG",
        _VARCHAR_100,
        warning_msg="LSEG PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LSEG → VARCHAR(100)",
        requires_ddl_comment=True,
    ),
    "BOX": TypeMappingPostgreSQLToSQLServer(
        "BOX",
        _VARCHAR_100,
        warning_msg="BOX PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: BOX → VARCHAR(100)",
        requires_ddl_comment=True,
    ),
    "PATH": TypeMappingPostgreSQLToSQLServer(
        "PATH",
        _VARCHAR_200,
        warning_msg="PATH PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(200)",
        severity="ERROR",
        ddl_comment="-- ERROR: PATH → VARCHAR(200)",
        requires_ddl_comment=True,
    ),
    "POLYGON": TypeMappingPostgreSQLToSQLServer(
        "POLYGON",
        _VARCHAR_200,
        warning_msg="POLYGON PostgreSQL mapeado a VARCHAR(200) SQL Server; usar geometry para datos espaciales reales",
        severity="ERROR",
        proposals=(_VARCHAR_200, "geometry -- SQL Server Spatial"),
        ddl_comment="-- ERROR: POLYGON → VARCHAR(200) [A] | geometry SQL Server Spatial [B]",
        requires_ddl_comment=True,
    ),
    "CIRCLE": TypeMappingPostgreSQLToSQLServer(
        "CIRCLE",
        _VARCHAR_100,
        warning_msg="CIRCLE PostgreSQL sin equivalente en SQL Server; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: CIRCLE → VARCHAR(100)",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "ARRAY": TypeMappingPostgreSQLToSQLServer(
        "ARRAY",
        _NVARCHAR_MAX,
        warning_msg="Tipo ARRAY PostgreSQL sin equivalente en SQL Server; mapeado a NVARCHAR(MAX) — revisar estructura",
        severity="ERROR",
        ddl_comment="-- ERROR: ARRAY → NVARCHAR(MAX); normalizar en tablas separadas (1FN)",
        requires_ddl_comment=True,
    ),
    "USER-DEFINED": TypeMappingPostgreSQLToSQLServer(
        "USER-DEFINED",
        _NVARCHAR_MAX,
        warning_msg="Tipo USER-DEFINED (enum/composite) PostgreSQL sin equivalente en SQL Server; mapeado a NVARCHAR(MAX)",
        severity="ERROR",
        ddl_comment="-- ERROR: USER-DEFINED → NVARCHAR(MAX); revisar tipo personalizado",
        requires_ddl_comment=True,
    ),
}


def resolve_postgresql_type_sqlserver(pg_type: str) -> TypeMappingPostgreSQLToSQLServer | None:
    """Busca el mapeo para un tipo PostgreSQL hacia SQL Server (sin parámetros).

    Args:
        pg_type: Tipo PostgreSQL en crudo (ej. "INTEGER", "CHARACTER VARYING",
                 "TIMESTAMP WITH TIME ZONE").

    Returns:
        TypeMappingPostgreSQLToSQLServer si existe, None si el tipo es desconocido.
    """
    key = pg_type.strip().upper()
    return POSTGRESQL_TO_SQLSERVER.get(key)


__all__: list[str] = [
    "TypeMappingPostgreSQLToSQLServer",
    "POSTGRESQL_TO_SQLSERVER",
    "resolve_postgresql_type_sqlserver",
]
