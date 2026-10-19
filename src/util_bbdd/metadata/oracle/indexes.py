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


def fetch_unique_constraint_columns_sql() -> str:
    """SQL con las PK y UNIQUE **activas** de una tabla y sus columnas en orden (``disable_indexes="all"``, v3.3.0).

    Excluye la PK de una tabla organizada por índice (IOT): es la tabla. Solo las ``ENABLED``: una UNIQUE que ya
    desactivó la ruta de constraints (``maintenance_scope``/``dump``) no se vuelve a tocar.

    Parámetros: ``:tbl`` y ``:owner`` (``None`` = ``USER``; ambos se comparan en mayúsculas).

    Returns:
        str: SQL para (constraint_name, constraint_type, column_name), ordenado por constraint y posición.
    """
    return (
        "SELECT c.constraint_name, c.constraint_type, cc.column_name "
        "FROM all_constraints c "
        "JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name "
        "JOIN all_tables t ON t.owner = c.owner AND t.table_name = c.table_name "
        "WHERE c.owner = NVL(UPPER(:owner), USER) AND c.table_name = UPPER(:tbl) "
        "  AND c.constraint_type IN ('P', 'U') AND c.status = 'ENABLED' "
        "  AND NOT (c.constraint_type = 'P' AND t.iot_type IS NOT NULL) "
        "ORDER BY c.constraint_name, cc.position"
    )


def fetch_inbound_foreign_keys_sql() -> str:
    """SQL con las FK **activas** de otras tablas (o de la misma) que referencian una PK/UNIQUE de la tabla.

    ``DISABLE CONSTRAINT … CASCADE`` las desactiva con la PK/UNIQUE; se reactivan al restaurar.

    Parámetros: ``:tbl`` y ``:owner`` (``None`` = ``USER``).

    Returns:
        str: SQL para (referenced_constraint, owner, table_name, constraint_name, validated).
    """
    return (
        "SELECT p.constraint_name, c.owner, c.table_name, c.constraint_name, c.validated "
        "FROM all_constraints c "
        "JOIN all_constraints p ON p.owner = c.r_owner AND p.constraint_name = c.r_constraint_name "
        "WHERE c.constraint_type = 'R' AND c.status = 'ENABLED' "
        "  AND p.owner = NVL(UPPER(:owner), USER) AND p.table_name = UPPER(:tbl) "
        "ORDER BY c.owner, c.table_name, c.constraint_name"
    )


__all__: list[str] = [
    "fetch_inbound_foreign_keys_sql",
    "fetch_secondary_nonunique_indexes_sql",
    "fetch_unique_constraint_columns_sql",
]
