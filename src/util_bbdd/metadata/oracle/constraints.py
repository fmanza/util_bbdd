"""Helpers para constraints (PK/FK) de Oracle.

Nota: Los módulos constraints.py e indexes.py son opcionales en el contexto
de este adaptador; su contenido puede consolidarse en _adapter_helpers.py
o tables.py. Se crean para mantener parity estructural con PostgreSQL.
"""

from __future__ import annotations

from typing import ClassVar

from ...results import Rows


class OracleConstraintDefaults:
    """Constantes y helpers para normalización de constraints Oracle."""

    NO_ACTION: ClassVar[str] = "NO ACTION"

    @staticmethod
    def normalize_delete_rule(delete_rule: str | None) -> str:
        """Normaliza la regla de borrado de Oracle a estándar.

        Args:
            delete_rule: DELETE_RULE de all_constraints (CASCADE, NO ACTION, RESTRICT, SET NULL)

        Returns:
            str: Acción normalizada
        """
        if not delete_rule:
            return OracleConstraintDefaults.NO_ACTION

        rule_upper = str(delete_rule).strip().upper()

        if rule_upper == "CASCADE":
            return "CASCADE"
        if rule_upper == "SET NULL":
            return "SET NULL"
        if rule_upper == "RESTRICT":
            return "RESTRICT"
        if rule_upper == OracleConstraintDefaults.NO_ACTION:
            return OracleConstraintDefaults.NO_ACTION

        return OracleConstraintDefaults.NO_ACTION

    @staticmethod
    def decode_pk_rows(rows: Rows) -> Rows:
        """Decodifica filas de primary keys Oracle.

        Args:
            rows: Filas desde query fetch_pk_constraint_sql

        Returns:
            Rows: (constraint_name, column_name, ordinal_position)
        """
        decoded: Rows = []
        for row in rows:
            if not isinstance(row, (tuple, list)) or len(row) < 3:
                continue

            try:
                decoded.append(
                    (
                        str(row[0]).strip() if row[0] else "",
                        str(row[1]).strip() if row[1] else "",
                        int(row[2]) if row[2] is not None else 0,
                    )
                )
            except (ValueError, TypeError):
                continue

        return decoded

    @staticmethod
    def _process_fk_row(row: tuple | list) -> tuple | None:
        """Procesa y valida una fila FK individual (CC isolated).

        Extrae la lógica de validación/normalización de decode_fk_rows para
        reducir complejidad cognitiva del método principal.

        Args:
            row: Fila cruda de all_constraints

        Returns:
            Tupla normalizada (constraint_name, column_name, ref_owner, ref_table,
            ref_column, on_delete_action, on_update_action, ordinal_position) o None si hay error
        """
        if not isinstance(row, (tuple, list)) or len(row) < 8:
            return None

        try:
            return (
                str(row[0]).strip() if row[0] else "",
                str(row[1]).strip() if row[1] else "",
                str(row[2]).strip() if row[2] else "",
                str(row[3]).strip() if row[3] else "",
                str(row[4]).strip() if row[4] else "",
                OracleConstraintDefaults.normalize_delete_rule(row[5]),
                OracleConstraintDefaults.normalize_delete_rule(row[6])
                if row[6]
                else OracleConstraintDefaults.NO_ACTION,
                int(row[7]) if row[7] is not None else 0,
            )
        except (ValueError, TypeError):
            return None

    @staticmethod
    def decode_fk_rows(rows: Rows) -> Rows:
        """Decodifica filas de foreign keys Oracle.

        Args:
            rows: Filas desde query fetch_fk_constraint_sql

        Returns:
            Rows: (constraint_name, column_name, ref_owner, ref_table, ref_column,
                    on_delete_action, on_update_action, ordinal_position)
        """
        decoded: Rows = []
        for row in rows:
            processed_row = OracleConstraintDefaults._process_fk_row(row)
            if processed_row is not None:
                decoded.append(processed_row)
        return decoded


__all__: list[str] = [
    "OracleConstraintDefaults",
]
