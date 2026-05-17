"""Mapeo exhaustivo de tipos Oracle → MariaDB.

Cubre 30+ tipos Oracle con sus equivalentes MariaDB, estrategia de transformación
y mensajes de aviso cuando la equivalencia no es exacta.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMapping:
    """Definición de mapeo para un tipo Oracle a MariaDB."""

    oracle_base: str
    mariadb_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico Oracle → MariaDB.
# La clave es el tipo Oracle en MAYÚSCULAS sin parámetros.
ORACLE_TO_MARIADB: dict[str, TypeMapping] = {
    # ── Strings ───────────────────────────────────────────────────────────────
    "VARCHAR2": TypeMapping("VARCHAR2", "VARCHAR"),
    "VARCHAR": TypeMapping("VARCHAR", "VARCHAR"),
    "NVARCHAR2": TypeMapping(
        "NVARCHAR2",
        "VARCHAR",
        warning_msg="NVARCHAR2 mapeado a VARCHAR CHARACTER SET utf8mb4",
        severity="INFO",
    ),
    "CHAR": TypeMapping("CHAR", "CHAR"),
    "NCHAR": TypeMapping("NCHAR", "CHAR"),
    # ── Números enteros y decimales (sin precisión: tratar separado) ──────────
    "INTEGER": TypeMapping("INTEGER", "INT"),
    "INT": TypeMapping("INT", "INT"),
    "SMALLINT": TypeMapping("SMALLINT", "SMALLINT"),
    # NUMBER se resuelve dinámicamente según precision/scale
    "NUMBER": TypeMapping(
        "NUMBER",
        "DOUBLE",
        warning_msg="NUMBER sin precisión explícita mapeado a DOUBLE",
        severity="WARNING",
        ddl_comment="-- AVISO: NUMBER sin precisión → DOUBLE (perda de exactitud posible)",
        requires_ddl_comment=True,
    ),
    "NUMERIC": TypeMapping("NUMERIC", "DECIMAL"),
    "DECIMAL": TypeMapping("DECIMAL", "DECIMAL"),
    # ── Punto flotante ────────────────────────────────────────────────────────
    "FLOAT": TypeMapping("FLOAT", "DOUBLE"),
    "REAL": TypeMapping("REAL", "FLOAT"),
    "DOUBLE PRECISION": TypeMapping("DOUBLE PRECISION", "DOUBLE"),
    "BINARY_FLOAT": TypeMapping(
        "BINARY_FLOAT",
        "FLOAT",
        warning_msg="BINARY_FLOAT (24 bits IEEE) mapeado a FLOAT; posible diferencia de precisión extrema",
        severity="INFO",
    ),
    "BINARY_DOUBLE": TypeMapping("BINARY_DOUBLE", "DOUBLE"),
    # ── Fecha y hora ──────────────────────────────────────────────────────────
    "DATE": TypeMapping(
        "DATE",
        "DATETIME",
        warning_msg="DATE Oracle incluye componente horario; mapeado a DATETIME en MariaDB",
        severity="WARNING",
        ddl_comment="-- AVISO: DATE Oracle contiene hora; usar DATETIME en MariaDB",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP": TypeMapping("TIMESTAMP", "DATETIME"),
    "TIMESTAMP WITH TIME ZONE": TypeMapping(
        "TIMESTAMP WITH TIME ZONE",
        "DATETIME(6)",
        warning_msg="TIMESTAMP WITH TIME ZONE: MariaDB no tiene tipo TZ nativo; información de zona perdida",
        severity="WARNING",
        proposals=("DATETIME(6)", "VARCHAR(35) -- guardar como ISO8601"),
        ddl_comment="-- AVISO: TIMESTAMP WITH TIME ZONE → DATETIME(6); zona horaria no preservada",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP WITH LOCAL TIME ZONE": TypeMapping(
        "TIMESTAMP WITH LOCAL TIME ZONE",
        "DATETIME(6)",
        warning_msg="TIMESTAMP WITH LOCAL TIME ZONE convertido a DATETIME(6); zona horaria no preservada",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMP WITH LOCAL TIME ZONE → DATETIME(6)",
        requires_ddl_comment=True,
    ),
    # ── Intervalos (sin equivalente directo) ─────────────────────────────────
    "INTERVAL YEAR TO MONTH": TypeMapping(
        "INTERVAL YEAR TO MONTH",
        "VARCHAR(30)",
        warning_msg="INTERVAL YEAR TO MONTH sin equivalente en MariaDB; mapeado a VARCHAR(30) (propuesta A)",
        severity="WARNING",
        proposals=("VARCHAR(30)", "INT -- meses totales"),
        ddl_comment="-- AVISO: INTERVAL YEAR TO MONTH → VARCHAR(30) [A] | INT meses [B]",
        requires_ddl_comment=True,
    ),
    "INTERVAL DAY TO SECOND": TypeMapping(
        "INTERVAL DAY TO SECOND",
        "BIGINT",
        warning_msg="INTERVAL DAY TO SECOND sin equivalente en MariaDB; mapeado a BIGINT (microsegundos, propuesta A)",
        severity="WARNING",
        proposals=("BIGINT -- microsegundos", "VARCHAR(30)"),
        ddl_comment="-- AVISO: INTERVAL DAY TO SECOND → BIGINT µs [A] | VARCHAR(30) [B]",
        requires_ddl_comment=True,
    ),
    # ── LOB ───────────────────────────────────────────────────────────────────
    "CLOB": TypeMapping("CLOB", "LONGTEXT"),
    "NCLOB": TypeMapping("NCLOB", "LONGTEXT"),
    "BLOB": TypeMapping("BLOB", "LONGBLOB"),
    "LONG": TypeMapping(
        "LONG",
        "LONGTEXT",
        warning_msg="LONG (deprecated en Oracle) mapeado a LONGTEXT",
        severity="INFO",
    ),
    "LONG RAW": TypeMapping("LONG RAW", "LONGBLOB"),
    "RAW": TypeMapping("RAW", "VARBINARY"),
    # ── Sin equivalente ───────────────────────────────────────────────────────
    "BFILE": TypeMapping(
        "BFILE",
        "VARCHAR(512)",
        warning_msg="BFILE sin equivalente en MariaDB; mapeado a VARCHAR(512) para ruta (propuesta A)",
        severity="WARNING",
        proposals=("VARCHAR(512) -- ruta de archivo",),
        ddl_comment="-- AVISO: BFILE → VARCHAR(512) ruta [A]; revisar lógica de aplicación",
        requires_ddl_comment=True,
    ),
    "XMLTYPE": TypeMapping(
        "XMLTYPE",
        "LONGTEXT",
        warning_msg="XMLType sin equivalente nativo; mapeado a LONGTEXT (propuesta A)",
        severity="WARNING",
        proposals=("LONGTEXT", "JSON -- MariaDB 10.2+"),
        ddl_comment="-- AVISO: XMLType → LONGTEXT [A] | JSON [B] (MariaDB 10.2+)",
        requires_ddl_comment=True,
    ),
    # ROWID/UROWID: columna omitida — sin equivalente semántico
    "ROWID": TypeMapping(
        "ROWID",
        "",
        warning_msg="ROWID sin equivalente semántico en MariaDB; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: ROWID omitido (sin equivalente en MariaDB)",
        requires_ddl_comment=True,
    ),
    "UROWID": TypeMapping(
        "UROWID",
        "",
        warning_msg="UROWID sin equivalente semántico en MariaDB; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: UROWID omitido (sin equivalente en MariaDB)",
        requires_ddl_comment=True,
    ),
}


def resolve_oracle_type(oracle_type: str) -> TypeMapping | None:
    """Busca el mapeo para un tipo Oracle (sin parámetros).

    Args:
        oracle_type: Tipo Oracle en crudo (ej. "VARCHAR2", "NUMBER", "TIMESTAMP WITH TIME ZONE")

    Returns:
        TypeMapping si existe, None si el tipo es desconocido.
    """
    key = oracle_type.strip().upper()
    return ORACLE_TO_MARIADB.get(key)


def resolve_number_type(
    precision: int | None,
    scale: int | None,
    fallback: str = "DOUBLE",
) -> tuple[str, str | None]:
    """Resuelve el tipo MariaDB para NUMBER Oracle según precision/scale.

    Args:
        precision: DATA_PRECISION de Oracle (puede ser None).
        scale: DATA_SCALE de Oracle (puede ser None).
        fallback: Tipo destino cuando no hay precision/scale ("DOUBLE" por defecto).

    Returns:
        (mariadb_type, optional_ddl_comment)
    """
    if precision is None:
        comment = f"-- AVISO: NUMBER sin precisión → {fallback} (perda de exactitud posible)"
        return fallback, comment

    effective_scale = scale if scale is not None else 0

    if effective_scale > 0:
        return f"DECIMAL({precision},{effective_scale})", None

    # scale == 0: tipo entero según precisión
    if precision <= 2:
        return "TINYINT", None
    if precision <= 4:
        return "SMALLINT", None
    if precision <= 9:
        return "INT", None
    if precision <= 18:
        return "BIGINT", None

    return f"DECIMAL({precision},0)", None


__all__: list[str] = [
    "TypeMapping",
    "ORACLE_TO_MARIADB",
    "resolve_oracle_type",
    "resolve_number_type",
]
