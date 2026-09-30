"""Comentarios de tabla y columna recortados al límite del motor destino (C1, auditoría 0.21.0).

Un comentario más largo de lo que admite el destino rompía el DDL: en MySQL/MariaDB el ``CREATE TABLE`` entero
(error 1629), en Oracle el ``COMMENT ON`` (ORA-01704) y en SQL Server la sentencia con todos los ``MS_Description``
(15097). Se recorta al límite y se deja un aviso ``COMMENT`` en la tabla o la columna. PostgreSQL no tiene un límite práctico.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ir.models import MigrationWarning


@dataclass(frozen=True, slots=True)
class CommentLimit:
    """Límite de un comentario en el destino; se aplican todos los que no sean None.

    Attributes:
        chars: Caracteres (MySQL/MariaDB).
        utf8_bytes: Bytes en UTF-8 (Oracle).
        utf16_units: Unidades UTF-16 (SQL Server: ``nvarchar`` en un ``sql_variant`` de 7 500 bytes).
        description: Texto del límite para el aviso.
    """

    description: str
    chars: int | None = None
    utf8_bytes: int | None = None
    utf16_units: int | None = None


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def fit_comment(
    warnings: list[MigrationWarning],
    table: str,
    column: str | None,
    text: str,
    limit: CommentLimit,
    target_label: str,
) -> str:
    """Devuelve ``text`` recortado a ``limit`` (sin partir caracteres); si lo recorta, añade un aviso a ``warnings``.

    ``warnings`` es ``table.warnings`` para el comentario de la tabla y ``col.warnings`` para el de una columna (los
    avisos de emisión de ambas listas se incorporan al plan).
    """
    fitted = text
    if limit.chars is not None and len(fitted) > limit.chars:
        fitted = fitted[: limit.chars]
    if limit.utf8_bytes is not None and len(fitted.encode("utf-8")) > limit.utf8_bytes:
        fitted = fitted.encode("utf-8")[: limit.utf8_bytes].decode("utf-8", errors="ignore")
    if limit.utf16_units is not None:
        while _utf16_units(fitted) > limit.utf16_units:
            fitted = fitted[: -max(1, (_utf16_units(fitted) - limit.utf16_units) // 2)]
    if fitted == text:
        return text
    target = f"{table}.{column}" if column else table
    warning = MigrationWarning(
        table=table,
        column=column,
        category="COMMENT",
        target_type=f"{len(fitted)} caracteres",
        code="COMMENT_TRUNCATED",
        message=(
            f"Comentario de '{target}' recortado de {len(text)} a {len(fitted)} caracteres: {target_label} admite "
            f"como máximo {limit.description}"
        ),
        severity="WARNING",
    )
    if warning not in warnings:
        warnings.append(warning)
    return fitted


# Límites por destino y tipo de objeto
MYSQL_TABLE_COMMENT = CommentLimit("2048 caracteres en el comentario de una tabla", chars=2048)
MYSQL_COLUMN_COMMENT = CommentLimit("1024 caracteres en el comentario de una columna", chars=1024)
ORACLE_COMMENT = CommentLimit("4000 bytes por comentario", utf8_bytes=4000)
SQLSERVER_COMMENT = CommentLimit("7500 bytes por MS_Description (3750 caracteres UTF-16)", utf16_units=3750)

__all__: list[str] = [
    "MYSQL_COLUMN_COMMENT",
    "MYSQL_TABLE_COMMENT",
    "ORACLE_COMMENT",
    "SQLSERVER_COMMENT",
    "CommentLimit",
    "fit_comment",
]
