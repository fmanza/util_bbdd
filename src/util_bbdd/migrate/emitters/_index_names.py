"""Nombres de índice únicos por schema para los destinos que lo exigen (A3, hotfix 2026-09-29).

MySQL, MariaDB y SQL Server admiten el mismo nombre de índice en tablas distintas (MySQL y MariaDB llaman a un índice
sin nombre como su primera columna); PostgreSQL y Oracle no: el nombre es único en el schema. Al emitir hacia estos, el
primer índice conserva su nombre y los siguientes que chocan pasan a ``<tabla>_<índice>`` (truncado al límite del
motor; ``_2``, ``_3``... si aún chocara), con un aviso en la tabla.
"""

from __future__ import annotations

from collections.abc import Callable

from .._compat.identifier_rules import truncate_identifier
from ..ir.models import CanonicalIndex, CanonicalTable, MigrationWarning


def claim_index_name(
    table: CanonicalTable,
    index: CanonicalIndex,
    taken: set[str],
    *,
    max_length: int,
    fold: Callable[[str], str],
    target_label: str,
) -> str:
    """Devuelve el nombre con el que emitir ``index`` y lo reserva en ``taken`` (claves ya plegadas con ``fold``)."""
    name = index.name
    if fold(name) not in taken:
        taken.add(fold(name))
        return name
    base = f"{table.name}_{index.name}"
    candidate = truncate_identifier(base, max_length)[0]
    suffix = 2
    while fold(candidate) in taken:
        candidate = truncate_identifier(f"{base}_{suffix}", max_length)[0]
        suffix += 1
    taken.add(fold(candidate))
    warning = MigrationWarning(
        table=table.name,
        column=None,
        oracle_type="INDEX",
        target_type=candidate,
        message=(
            f"Índice '{name}' de la tabla '{table.name}' renombrado a '{candidate}': en {target_label} el nombre de "
            "índice es único en el schema y ya lo usa otro objeto"
        ),
        severity="WARNING",
    )
    if warning not in table.warnings:
        table.warnings.append(warning)
    return candidate


__all__: list[str] = ["claim_index_name"]
