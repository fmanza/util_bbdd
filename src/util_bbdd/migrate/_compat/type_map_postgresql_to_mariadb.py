"""Mapeo exhaustivo de tipos PostgreSQL → MariaDB.

Cubre los tipos estándar de PostgreSQL con sus equivalentes MariaDB.
El campo ``mariadb_type`` contiene el tipo MariaDB base o completo; los
parámetros dinámicos (longitud, precisión, escala) se resuelven en el transformer.

``source_base`` es el tipo PostgreSQL en MAYÚSCULAS sin parámetros, equivalente
al valor de DATA_TYPE en INFORMATION_SCHEMA.COLUMNS devuelto en uppercase.
PostgreSQL usa tipos multi-palabra (ej. ``CHARACTER VARYING``,
``TIMESTAMP WITHOUT TIME ZONE``).

Nota: ``CHARACTER VARYING`` con ``char_length=None`` indica texto sin límite
→ el transformer lo convierte a LONGTEXT en MariaDB.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingPostgreSQLToMariaDB:
    """Definición de mapeo para un tipo PostgreSQL a MariaDB."""

    source_base: str
    mariadb_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


_VARCHAR_100 = "VARCHAR(100)"

# Mapeo canónico PostgreSQL → MariaDB.
# Clave: DATA_TYPE de INFORMATION_SCHEMA en MAYÚSCULAS, sin parámetros.
POSTGRESQL_TO_MARIADB: dict[str, TypeMappingPostgreSQLToMariaDB] = {
    # ── Enteros ──────────────────────────────────────────────────────────────────
    "INTEGER": TypeMappingPostgreSQLToMariaDB("INTEGER", "INT"),
    "BIGINT": TypeMappingPostgreSQLToMariaDB("BIGINT", "BIGINT"),
    "SMALLINT": TypeMappingPostgreSQLToMariaDB("SMALLINT", "SMALLINT"),
    # ── Decimales y punto flotante ───────────────────────────────────────────────
    "NUMERIC": TypeMappingPostgreSQLToMariaDB("NUMERIC", "DECIMAL"),
    "DECIMAL": TypeMappingPostgreSQLToMariaDB("DECIMAL", "DECIMAL"),
    "REAL": TypeMappingPostgreSQLToMariaDB(
        "REAL",
        "FLOAT",
        warning_msg="REAL PostgreSQL (IEEE 754 single) mapeado a FLOAT MariaDB",
        severity="INFO",
    ),
    "DOUBLE PRECISION": TypeMappingPostgreSQLToMariaDB(
        "DOUBLE PRECISION",
        "DOUBLE",
        warning_msg="DOUBLE PRECISION PostgreSQL mapeado a DOUBLE MariaDB",
        severity="INFO",
    ),
    "MONEY": TypeMappingPostgreSQLToMariaDB(
        "MONEY",
        "DECIMAL(19,4)",
        warning_msg="MONEY PostgreSQL mapeado a DECIMAL(19,4) MariaDB; el símbolo de moneda se pierde",
        severity="WARNING",
        ddl_comment="-- AVISO: MONEY → DECIMAL(19,4); verificar formato de salida",
        requires_ddl_comment=True,
    ),
    # ── Strings ──────────────────────────────────────────────────────────────────
    # CHARACTER VARYING: char_length=None → LONGTEXT; <=65535 → VARCHAR(n)
    "CHARACTER VARYING": TypeMappingPostgreSQLToMariaDB("CHARACTER VARYING", "VARCHAR"),
    "CHARACTER": TypeMappingPostgreSQLToMariaDB("CHARACTER", "CHAR"),
    "TEXT": TypeMappingPostgreSQLToMariaDB("TEXT", "LONGTEXT"),
    # ── Booleano ─────────────────────────────────────────────────────────────────
    "BOOLEAN": TypeMappingPostgreSQLToMariaDB("BOOLEAN", "TINYINT(1)"),
    # ── Fecha y hora ─────────────────────────────────────────────────────────────
    "DATE": TypeMappingPostgreSQLToMariaDB("DATE", "DATE"),
    "TIME WITHOUT TIME ZONE": TypeMappingPostgreSQLToMariaDB("TIME WITHOUT TIME ZONE", "TIME(6)"),
    "TIME WITH TIME ZONE": TypeMappingPostgreSQLToMariaDB(
        "TIME WITH TIME ZONE",
        "VARCHAR(21)",
        warning_msg="TIME WITH TIME ZONE PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(21)",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMETZ → VARCHAR(21); sin soporte de zona horaria en TIME MariaDB",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP WITHOUT TIME ZONE": TypeMappingPostgreSQLToMariaDB("TIMESTAMP WITHOUT TIME ZONE", "DATETIME(6)"),
    "TIMESTAMP WITH TIME ZONE": TypeMappingPostgreSQLToMariaDB(
        "TIMESTAMP WITH TIME ZONE",
        "DATETIME(6)",
        warning_msg=(
            "TIMESTAMP WITH TIME ZONE PostgreSQL mapeado a DATETIME(6) MariaDB; "
            "la información de zona horaria se pierde — almacenar en UTC recomendado"
        ),
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMPTZ → DATETIME(6); zona horaria no preservada",
        requires_ddl_comment=True,
    ),
    "INTERVAL": TypeMappingPostgreSQLToMariaDB(
        "INTERVAL",
        "VARCHAR(30)",
        warning_msg="INTERVAL PostgreSQL sin equivalente directo en MariaDB; mapeado a VARCHAR(30)",
        severity="WARNING",
        ddl_comment="-- AVISO: INTERVAL → VARCHAR(30); revisar lógica de cálculo de intervalos",
        requires_ddl_comment=True,
    ),
    # ── UUID ──────────────────────────────────────────────────────────────────────
    "UUID": TypeMappingPostgreSQLToMariaDB(
        "UUID",
        "CHAR(36)",
        warning_msg="UUID PostgreSQL mapeado a CHAR(36) MariaDB (formato 8-4-4-4-12)",
        severity="INFO",
    ),
    # ── JSON ──────────────────────────────────────────────────────────────────────
    "JSON": TypeMappingPostgreSQLToMariaDB(
        "JSON",
        "LONGTEXT",
        warning_msg=(
            "JSON PostgreSQL mapeado a LONGTEXT MariaDB; "
            "MariaDB 10.2+ soporta tipo JSON nativo con validación (propuesta B)"
        ),
        severity="INFO",
        proposals=("LONGTEXT", "JSON -- MariaDB 10.2+"),
        ddl_comment="-- AVISO: JSON → LONGTEXT [A] | JSON nativo MariaDB 10.2+ [B]",
        requires_ddl_comment=True,
    ),
    "JSONB": TypeMappingPostgreSQLToMariaDB(
        "JSONB",
        "LONGTEXT",
        warning_msg="JSONB PostgreSQL (JSON binario) mapeado a LONGTEXT MariaDB; sin validación de estructura",
        severity="WARNING",
        ddl_comment="-- AVISO: JSONB → LONGTEXT; MariaDB no tiene JSONB nativo",
        requires_ddl_comment=True,
    ),
    # ── Binarios ─────────────────────────────────────────────────────────────────
    "BYTEA": TypeMappingPostgreSQLToMariaDB("BYTEA", "LONGBLOB"),
    # ── XML ───────────────────────────────────────────────────────────────────────
    "XML": TypeMappingPostgreSQLToMariaDB(
        "XML",
        "LONGTEXT",
        warning_msg="XML PostgreSQL mapeado a LONGTEXT MariaDB; sin validación de estructura XML",
        severity="WARNING",
        ddl_comment="-- AVISO: XML → LONGTEXT; MariaDB no tiene tipo XML nativo",
        requires_ddl_comment=True,
    ),
    # ── Red ───────────────────────────────────────────────────────────────────────
    "INET": TypeMappingPostgreSQLToMariaDB(
        "INET",
        "VARCHAR(45)",
        warning_msg="INET PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(45)",
        severity="WARNING",
        ddl_comment="-- AVISO: INET → VARCHAR(45); sin validación de formato IP en MariaDB",
        requires_ddl_comment=True,
    ),
    "CIDR": TypeMappingPostgreSQLToMariaDB(
        "CIDR",
        "VARCHAR(45)",
        warning_msg="CIDR PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(45)",
        severity="WARNING",
        ddl_comment="-- AVISO: CIDR → VARCHAR(45); sin validación de rango CIDR en MariaDB",
        requires_ddl_comment=True,
    ),
    "MACADDR": TypeMappingPostgreSQLToMariaDB(
        "MACADDR",
        "VARCHAR(17)",
        warning_msg="MACADDR PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(17)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR → VARCHAR(17)",
        requires_ddl_comment=True,
    ),
    "MACADDR8": TypeMappingPostgreSQLToMariaDB(
        "MACADDR8",
        "VARCHAR(23)",
        warning_msg="MACADDR8 PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(23)",
        severity="WARNING",
        ddl_comment="-- AVISO: MACADDR8 → VARCHAR(23)",
        requires_ddl_comment=True,
    ),
    # ── Bit strings ───────────────────────────────────────────────────────────────
    # MariaDB soporta tipo BIT(n) nativo
    "BIT": TypeMappingPostgreSQLToMariaDB(
        "BIT",
        "BIT",
        warning_msg="BIT(n) PostgreSQL mapeado a BIT(n) MariaDB; verificar semántica de comparaciones",
        severity="INFO",
    ),
    "BIT VARYING": TypeMappingPostgreSQLToMariaDB(
        "BIT VARYING",
        "VARBINARY",
        warning_msg="BIT VARYING PostgreSQL mapeado a VARBINARY(n) MariaDB; sin tipo BIT VARYING nativo",
        severity="WARNING",
        ddl_comment="-- AVISO: BIT VARYING → VARBINARY(n); almacena representación binaria",
        requires_ddl_comment=True,
    ),
    # ── OID ───────────────────────────────────────────────────────────────────────
    "OID": TypeMappingPostgreSQLToMariaDB(
        "OID",
        "INT UNSIGNED",
        warning_msg="OID PostgreSQL (object identifier interno) mapeado a INT UNSIGNED MariaDB; verificar uso",
        severity="WARNING",
        ddl_comment="-- AVISO: OID → INT UNSIGNED; OID es identificador interno de PostgreSQL",
        requires_ddl_comment=True,
    ),
    # ── Full-text search ─────────────────────────────────────────────────────────
    "TSVECTOR": TypeMappingPostgreSQLToMariaDB(
        "TSVECTOR",
        "LONGTEXT",
        warning_msg="TSVECTOR PostgreSQL sin equivalente en MariaDB; mapeado a LONGTEXT — revisar full-text search",
        severity="ERROR",
        ddl_comment="-- ERROR: TSVECTOR → LONGTEXT; implementar FULLTEXT INDEX MariaDB manualmente",
        requires_ddl_comment=True,
    ),
    "TSQUERY": TypeMappingPostgreSQLToMariaDB(
        "TSQUERY",
        "LONGTEXT",
        warning_msg="TSQUERY PostgreSQL sin equivalente en MariaDB; mapeado a LONGTEXT",
        severity="ERROR",
        ddl_comment="-- ERROR: TSQUERY → LONGTEXT; revisar implementación de búsqueda",
        requires_ddl_comment=True,
    ),
    # ── Tipos geométricos ────────────────────────────────────────────────────────
    "POINT": TypeMappingPostgreSQLToMariaDB(
        "POINT",
        "POINT",
        warning_msg="POINT PostgreSQL mapeado a POINT MariaDB (tipo espacial nativo disponible)",
        severity="INFO",
    ),
    "LINE": TypeMappingPostgreSQLToMariaDB(
        "LINE",
        _VARCHAR_100,
        warning_msg="LINE PostgreSQL sin equivalente directo en MariaDB; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LINE → VARCHAR(100); MariaDB no tiene tipo LINE",
        requires_ddl_comment=True,
    ),
    "LSEG": TypeMappingPostgreSQLToMariaDB(
        "LSEG",
        _VARCHAR_100,
        warning_msg="LSEG PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: LSEG → VARCHAR(100)",
        requires_ddl_comment=True,
    ),
    "BOX": TypeMappingPostgreSQLToMariaDB(
        "BOX",
        "POLYGON",
        warning_msg="BOX PostgreSQL mapeado a POLYGON MariaDB (aproximación espacial)",
        severity="WARNING",
        ddl_comment="-- AVISO: BOX → POLYGON MariaDB; verificar compatibilidad espacial",
        requires_ddl_comment=True,
    ),
    "PATH": TypeMappingPostgreSQLToMariaDB(
        "PATH",
        "LINESTRING",
        warning_msg="PATH PostgreSQL mapeado a LINESTRING MariaDB (aproximación espacial)",
        severity="WARNING",
        ddl_comment="-- AVISO: PATH → LINESTRING MariaDB",
        requires_ddl_comment=True,
    ),
    "POLYGON": TypeMappingPostgreSQLToMariaDB(
        "POLYGON",
        "POLYGON",
        warning_msg="POLYGON PostgreSQL mapeado a POLYGON MariaDB (tipo espacial nativo disponible)",
        severity="INFO",
    ),
    "CIRCLE": TypeMappingPostgreSQLToMariaDB(
        "CIRCLE",
        _VARCHAR_100,
        warning_msg="CIRCLE PostgreSQL sin equivalente en MariaDB; mapeado a VARCHAR(100)",
        severity="ERROR",
        ddl_comment="-- ERROR: CIRCLE → VARCHAR(100); MariaDB no tiene tipo CIRCLE",
        requires_ddl_comment=True,
    ),
    # ── Tipos especiales ─────────────────────────────────────────────────────────
    "ARRAY": TypeMappingPostgreSQLToMariaDB(
        "ARRAY",
        "LONGTEXT",
        warning_msg="Tipo ARRAY PostgreSQL sin equivalente en MariaDB; mapeado a LONGTEXT — revisar estructura",
        severity="ERROR",
        ddl_comment="-- ERROR: ARRAY → LONGTEXT; normalizar en tablas separadas (1FN)",
        requires_ddl_comment=True,
    ),
    "USER-DEFINED": TypeMappingPostgreSQLToMariaDB(
        "USER-DEFINED",
        "LONGTEXT",
        warning_msg="Tipo USER-DEFINED (enum/composite) PostgreSQL sin equivalente en MariaDB; mapeado a LONGTEXT",
        severity="ERROR",
        ddl_comment="-- ERROR: USER-DEFINED → LONGTEXT; revisar tipo personalizado",
        requires_ddl_comment=True,
    ),
}


def resolve_postgresql_type_mariadb(pg_type: str) -> TypeMappingPostgreSQLToMariaDB | None:
    """Busca el mapeo para un tipo PostgreSQL hacia MariaDB (sin parámetros).

    Args:
        pg_type: Tipo PostgreSQL en crudo (ej. "INTEGER", "CHARACTER VARYING",
                 "TIMESTAMP WITHOUT TIME ZONE").

    Returns:
        TypeMappingPostgreSQLToMariaDB si existe, None si el tipo es desconocido.
    """
    key = pg_type.strip().upper()
    return POSTGRESQL_TO_MARIADB.get(key)


__all__: list[str] = [
    "TypeMappingPostgreSQLToMariaDB",
    "POSTGRESQL_TO_MARIADB",
    "resolve_postgresql_type_mariadb",
]
