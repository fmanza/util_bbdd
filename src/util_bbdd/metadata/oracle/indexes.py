"""Helpers para índices de Oracle."""

from __future__ import annotations


def fetch_secondary_nonunique_indexes_sql(*, with_owner: bool) -> str:
    """SQL con los índices NORMAL no únicos de una tabla que no respaldan una constraint.

    Lo usa ``dump.IndexManager`` para marcarlos ``UNUSABLE`` antes de la carga y reconstruirlos después.

    Args:
        with_owner: ``True`` consulta ``ALL_INDEXES`` filtrando por ``:owner``; ``False``, ``USER_INDEXES``.

    Parámetros: ``:tbl`` y, con ``with_owner``, ``:owner`` (ambos se comparan en mayúsculas).

    Returns:
        str: SQL para (index_name).
    """
    if with_owner:
        return (
            "SELECT ai.index_name FROM all_indexes ai "
            "WHERE ai.table_name = UPPER(:tbl) AND ai.owner = UPPER(:owner) "
            "  AND ai.index_type = 'NORMAL' AND ai.uniqueness = 'NONUNIQUE' "
            "  AND NOT EXISTS (SELECT 1 FROM all_constraints ac "
            "                  WHERE ac.owner = ai.owner AND ac.index_name = ai.index_name)"
        )
    return (
        "SELECT ui.index_name FROM user_indexes ui "
        "WHERE ui.table_name = UPPER(:tbl) "
        "  AND ui.index_type = 'NORMAL' AND ui.uniqueness = 'NONUNIQUE' "
        "  AND NOT EXISTS (SELECT 1 FROM user_constraints uc "
        "                  WHERE uc.index_name = ui.index_name)"
    )


__all__: list[str] = [
    "fetch_secondary_nonunique_indexes_sql",
]
