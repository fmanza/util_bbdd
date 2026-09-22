"""Mapeo exhaustivo de tipos Oracle → SQL Server.

Cubre 30+ tipos Oracle con sus equivalentes SQL Server, estrategia de
transformación y mensajes de aviso cuando la equivalencia no es exacta.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import WarningSeverity


@dataclass(frozen=True, slots=True)
class TypeMappingSQLServer:
    """Definición de mapeo para un tipo Oracle a SQL Server."""

    oracle_base: str
    sqlserver_type: str
    warning_msg: str | None = None
    proposals: tuple[str, ...] = ()
    requires_ddl_comment: bool = False
    ddl_comment: str | None = None
    severity: WarningSeverity = "INFO"


# Mapeo canónico Oracle → SQL Server.
# La clave es el tipo Oracle en MAYÚSCULAS sin parámetros.
ORACLE_TO_SQLSERVER: dict[str, TypeMappingSQLServer] = {
    # ── Strings ───────────────────────────────────────────────────────────────
    # SQL Server usa NVARCHAR/NCHAR como tipos Unicode nativos (equivalente a
    # NVARCHAR2/NCHAR de Oracle). VARCHAR2 se mapea a NVARCHAR para preservar
    # compatibilidad Unicode sin conversiones implícitas.
    "VARCHAR2": TypeMappingSQLServer(
        "VARCHAR2",
        "NVARCHAR",
        warning_msg="VARCHAR2 mapeado a NVARCHAR (Unicode nativo en SQL Server)",
        severity="INFO",
    ),
    "VARCHAR": TypeMappingSQLServer(
        "VARCHAR",
        "NVARCHAR",
        warning_msg="VARCHAR mapeado a NVARCHAR (Unicode nativo en SQL Server)",
        severity="INFO",
    ),
    "NVARCHAR2": TypeMappingSQLServer("NVARCHAR2", "NVARCHAR"),
    "CHAR": TypeMappingSQLServer(
        "CHAR",
        "NCHAR",
        warning_msg="CHAR mapeado a NCHAR (Unicode nativo en SQL Server)",
        severity="INFO",
    ),
    "NCHAR": TypeMappingSQLServer("NCHAR", "NCHAR"),
    # ── Números enteros y decimales (NUMBER se resuelve dinámicamente) ────────
    "INTEGER": TypeMappingSQLServer("INTEGER", "INT"),
    "INT": TypeMappingSQLServer("INT", "INT"),
    "SMALLINT": TypeMappingSQLServer("SMALLINT", "SMALLINT"),
    "NUMBER": TypeMappingSQLServer(
        "NUMBER",
        "FLOAT",
        warning_msg="NUMBER sin precisión explícita mapeado a FLOAT",
        severity="WARNING",
        ddl_comment="-- AVISO: NUMBER sin precisión → FLOAT (pérdida de exactitud posible)",
        requires_ddl_comment=True,
    ),
    "NUMERIC": TypeMappingSQLServer("NUMERIC", "NUMERIC"),
    "DECIMAL": TypeMappingSQLServer("DECIMAL", "DECIMAL"),
    # ── Punto flotante ────────────────────────────────────────────────────────
    "FLOAT": TypeMappingSQLServer("FLOAT", "FLOAT"),
    "REAL": TypeMappingSQLServer("REAL", "REAL"),
    "DOUBLE PRECISION": TypeMappingSQLServer("DOUBLE PRECISION", "FLOAT(53)"),
    "BINARY_FLOAT": TypeMappingSQLServer(
        "BINARY_FLOAT",
        "REAL",
        warning_msg="BINARY_FLOAT (24 bits IEEE) mapeado a REAL; posible diferencia de precisión extrema",
        severity="INFO",
    ),
    "BINARY_DOUBLE": TypeMappingSQLServer("BINARY_DOUBLE", "FLOAT(53)"),
    # ── Fecha y hora ──────────────────────────────────────────────────────────
    "DATE": TypeMappingSQLServer(
        "DATE",
        "DATETIME2",
        warning_msg="DATE Oracle incluye componente horario; mapeado a DATETIME2 en SQL Server",
        severity="WARNING",
        ddl_comment="-- AVISO: DATE Oracle contiene hora; usar DATETIME2",
        requires_ddl_comment=True,
    ),
    "TIMESTAMP": TypeMappingSQLServer("TIMESTAMP", "DATETIME2"),
    "TIMESTAMP WITH TIME ZONE": TypeMappingSQLServer(
        "TIMESTAMP WITH TIME ZONE",
        "DATETIMEOFFSET",
        warning_msg="TIMESTAMP WITH TIME ZONE mapeado a DATETIMEOFFSET; zona horaria preservada",
        severity="INFO",
    ),
    "TIMESTAMP WITH LOCAL TIME ZONE": TypeMappingSQLServer(
        "TIMESTAMP WITH LOCAL TIME ZONE",
        "DATETIME2",
        warning_msg="TIMESTAMP WITH LOCAL TIME ZONE convertido a DATETIME2; zona horaria no preservada",
        severity="WARNING",
        ddl_comment="-- AVISO: TIMESTAMP WITH LOCAL TIME ZONE → DATETIME2; zona horaria perdida",
        requires_ddl_comment=True,
    ),
    # ── Intervalos (sin equivalente directo) ─────────────────────────────────
    "INTERVAL YEAR TO MONTH": TypeMappingSQLServer(
        "INTERVAL YEAR TO MONTH",
        "VARCHAR(30)",
        warning_msg="INTERVAL YEAR TO MONTH sin equivalente en SQL Server; mapeado a VARCHAR(30) (propuesta A)",
        severity="WARNING",
        proposals=("VARCHAR(30)", "INT -- meses totales"),
        ddl_comment="-- AVISO: INTERVAL YEAR TO MONTH → VARCHAR(30) [A] | INT meses [B]",
        requires_ddl_comment=True,
    ),
    "INTERVAL DAY TO SECOND": TypeMappingSQLServer(
        "INTERVAL DAY TO SECOND",
        "BIGINT",
        warning_msg="INTERVAL DAY TO SECOND sin equivalente en SQL Server; mapeado a BIGINT (microsegundos, propuesta A)",
        severity="WARNING",
        proposals=("BIGINT -- microsegundos", "VARCHAR(30)"),
        ddl_comment="-- AVISO: INTERVAL DAY TO SECOND → BIGINT µs [A] | VARCHAR(30) [B]",
        requires_ddl_comment=True,
    ),
    # ── LOB ───────────────────────────────────────────────────────────────────
    "CLOB": TypeMappingSQLServer("CLOB", "NVARCHAR(MAX)"),
    "NCLOB": TypeMappingSQLServer("NCLOB", "NVARCHAR(MAX)"),
    "BLOB": TypeMappingSQLServer("BLOB", "VARBINARY(MAX)"),
    "LONG": TypeMappingSQLServer(
        "LONG",
        "NVARCHAR(MAX)",
        warning_msg="LONG (deprecated en Oracle) mapeado a NVARCHAR(MAX)",
        severity="INFO",
    ),
    "LONG RAW": TypeMappingSQLServer("LONG RAW", "VARBINARY(MAX)"),
    "RAW": TypeMappingSQLServer("RAW", "VARBINARY"),
    # ── Sin equivalente ───────────────────────────────────────────────────────
    "BFILE": TypeMappingSQLServer(
        "BFILE",
        "VARCHAR(512)",
        warning_msg="BFILE sin equivalente en SQL Server; mapeado a VARCHAR(512) para ruta (propuesta A)",
        severity="WARNING",
        proposals=("VARCHAR(512) -- ruta de archivo",),
        ddl_comment="-- AVISO: BFILE → VARCHAR(512) ruta [A]; revisar lógica de aplicación",
        requires_ddl_comment=True,
    ),
    "XMLTYPE": TypeMappingSQLServer(
        "XMLTYPE",
        "XML",
        warning_msg="XMLType mapeado a XML nativo de SQL Server (propuesta A)",
        severity="WARNING",
        proposals=("XML", "NVARCHAR(MAX)"),
        ddl_comment="-- AVISO: XMLType → XML [A] | NVARCHAR(MAX) [B]",
        requires_ddl_comment=True,
    ),
    # ROWID/UROWID: columna omitida — sin equivalente semántico
    "ROWID": TypeMappingSQLServer(
        "ROWID",
        "",
        warning_msg="ROWID sin equivalente semántico en SQL Server; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: ROWID omitido (sin equivalente en SQL Server)",
        requires_ddl_comment=True,
    ),
    "UROWID": TypeMappingSQLServer(
        "UROWID",
        "",
        warning_msg="UROWID sin equivalente semántico en SQL Server; columna omitida",
        severity="ERROR",
        ddl_comment="-- AVISO: UROWID omitido (sin equivalente en SQL Server)",
        requires_ddl_comment=True,
    ),
}


def resolve_oracle_type_sqlserver(oracle_type: str) -> TypeMappingSQLServer | None:
    """Busca el mapeo para un tipo Oracle hacia SQL Server (sin parámetros).

    Args:
        oracle_type: Tipo Oracle en crudo (ej. "VARCHAR2", "NUMBER", "TIMESTAMP WITH TIME ZONE")

    Returns:
        TypeMappingSQLServer si existe, None si el tipo es desconocido.
    """
    key = oracle_type.strip().upper()
    return ORACLE_TO_SQLSERVER.get(key)


def resolve_number_type_sqlserver(
    precision: int | None,
    scale: int | None,
    fallback: str = "FLOAT",
) -> tuple[str, str | None]:
    """Resuelve el tipo SQL Server para NUMBER Oracle según precision/scale.

    Args:
        precision: DATA_PRECISION de Oracle (puede ser None).
        scale: DATA_SCALE de Oracle (puede ser None).
        fallback: Tipo destino cuando no hay precision/scale ("FLOAT" por defecto).

    Returns:
        (sqlserver_type, optional_ddl_comment)
    """
    if precision is None:
        comment = f"-- AVISO: NUMBER sin precisión → {fallback} (pérdida de exactitud posible)"
        return fallback, comment

    effective_scale = scale if scale is not None else 0

    if effective_scale > 0:
        return f"NUMERIC({precision},{effective_scale})", None

    # scale == 0: tipo entero según precisión
    if precision <= 2:
        # NUMBER(1,0)/NUMBER(2,0) Oracle es con signo (rango con signo, p. ej. -99..99);
        # TINYINT de SQL Server es unsigned (0..255) — un valor negativo real desborda
        # silenciosamente sin este aviso (ver AUDIT_CODE CMP-01, 2026-09-22).
        comment = (
            f"-- AVISO: NUMBER({precision},0) Oracle con signo → TINYINT SQL Server "
            "unsigned (0-255); revisar valores negativos"
        )
        return "TINYINT", comment
    if precision <= 4:
        return "SMALLINT", None
    if precision <= 9:
        return "INT", None
    if precision <= 18:
        return "BIGINT", None

    return f"NUMERIC({precision},0)", None


__all__: list[str] = [
    "TypeMappingSQLServer",
    "ORACLE_TO_SQLSERVER",
    "resolve_oracle_type_sqlserver",
    "resolve_number_type_sqlserver",
]
