"""Helpers para índices de Oracle."""

from __future__ import annotations

from ...results import Rows


def decode_oracle_index_rows(rows: Rows) -> Rows:
    """Decodifica filas de índices Oracle.

    Args:
        rows: Filas desde query fetch_indexes_sql

    Returns:
        Rows: (index_name, column_name, order_direction, uniqueness, ordinal_position)
    """
    decoded: Rows = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 5:
            continue

        try:
            decoded.append(
                (
                    str(row[0]).strip() if row[0] else "",  # index_name
                    str(row[1]).strip() if row[1] else "",  # column_name
                    str(row[2]).strip().upper() if row[2] else "ASC",  # order_direction
                    str(row[3]).strip().upper() if row[3] else "NONUNIQUE",  # uniqueness
                    int(row[4]) if row[4] is not None else 0,  # ordinal_position
                )
            )
        except (ValueError, TypeError):
            continue

    return decoded


__all__: list[str] = [
    "decode_oracle_index_rows",
]
