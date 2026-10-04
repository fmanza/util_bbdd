"""Helpers puros para metadata y DDL de tablas Oracle."""

from __future__ import annotations


#: Tipos Oracle sin mapeo genérico fiable (deprecados por Oracle desde 9i en favor de
#: CLOB/BLOB). MEO-05 (AUDIT_CODE 2026-09-22): antes se descartaban en silencio (la
#: columna desaparecía del resultado sin ningún indicio); ahora se conservan con un
#: marcador explícito en el comentario en vez de desaparecer sin avisar.
def fetch_identity_generation_sql(*, with_owner: bool) -> str:
    """SQL con el tipo de generación de una columna identity (``ALWAYS`` / ``BY DEFAULT``) y su ``DEFAULT_ON_NULL``.

    Lo usa ``PKSequenceSyncer`` para repetir el mismo tipo al modificar la identity (``ALTER TABLE … MODIFY … GENERATED
    … AS IDENTITY (START WITH n)``); la secuencia de una identity no admite ``ALTER SEQUENCE`` (ORA-32793).

    Args:
        with_owner: ``True`` consulta ``ALL_TAB_IDENTITY_COLS`` filtrando por ``:owner``; ``False``, las vistas
            ``USER_*``.

    Parámetros: ``:tbl``, ``:col`` y, con ``with_owner``, ``:owner``, con los nombres como en el catálogo.

    Returns:
        str: SQL para (generation_type, default_on_null).
    """
    if with_owner:
        return (
            "SELECT i.generation_type, c.default_on_null FROM all_tab_identity_cols i "
            "JOIN all_tab_columns c ON c.owner = i.owner AND c.table_name = i.table_name "
            "AND c.column_name = i.column_name "
            "WHERE i.owner = :owner AND i.table_name = :tbl AND i.column_name = :col"
        )
    return (
        "SELECT i.generation_type, c.default_on_null FROM user_tab_identity_cols i "
        "JOIN user_tab_columns c ON c.table_name = i.table_name AND c.column_name = i.column_name "
        "WHERE i.table_name = :tbl AND i.column_name = :col"
    )


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# Mismo SQL que las consultas por tabla de arriba (que siguen usando los adaptadores de metadatos), sin el filtro de
# tabla y con ``table_name`` como primera columna; filas ordenadas por tabla y después por el orden propio del objeto.
# 200 tablas: 823 consultas (7,3 s en el banco) → 8 (0,18 s). Sesión 2026-09-30-migrate-d1-extract-batching.


__all__: list[str] = [
    "fetch_identity_generation_sql",
]
