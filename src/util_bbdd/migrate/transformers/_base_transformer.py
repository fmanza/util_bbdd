"""Clase base para transformadores de esquemas entre motores de BD.

Centraliza la lógica compartida entre los 13 transformers:
  _transform_view, _transform_table, _adapt_identifiers, _transform_index, _transform_fk.

Cada subclase debe definir:
  MAX_IDENTIFIER_LENGTH  -- límite de caracteres para el motor destino
  _TARGET_DIALECT        -- nombre del motor destino para mensajes de warning en vistas
  _transform_column      -- mapeo de tipos específico del par origen→destino
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import check_identifier
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)


class BaseTransformer:
    """Lógica de transformación de IR compartida entre todos los transformers."""

    MAX_IDENTIFIER_LENGTH: int = 64
    _TARGET_DIALECT: str = "destino"

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma todas las tablas al esquema destino."""
        return [self._transform_table(t) for t in tables]

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma vistas con pass-through v1 (sin reescritura SQL)."""
        return [self._transform_view(v) for v in views]

    def transform_routines(self, routines: list[CanonicalRoutine]) -> list[CanonicalRoutine]:
        """Transforma rutinas con pass-through v1 (sin reescritura de body)."""
        return [self._transform_routine(r) for r in routines]

    def _transform_routine(self, routine: CanonicalRoutine) -> CanonicalRoutine:
        result = deepcopy(routine)
        adapted_name, id_warn = check_identifier(routine.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            result.name = adapted_name
            result.warnings.append(
                MigrationWarning(
                    table=routine.name,
                    column=None,
                    oracle_type="IDENTIFIER",
                    target_type=adapted_name,
                    message=id_warn,
                    severity="WARNING",
                )
            )
        result.warnings.append(
            MigrationWarning(
                table=routine.name,
                column=None,
                oracle_type=routine.routine_type,
                target_type=routine.routine_type,
                message=(
                    f"Rutina emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    f"revisar manualmente el body para compatibilidad {self._TARGET_DIALECT}"
                ),
                severity="WARNING",
            )
        )
        return result

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = deepcopy(view)
        adapted_name, id_warn = check_identifier(view.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            result.name = adapted_name
            result.warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    oracle_type="IDENTIFIER",
                    target_type=adapted_name,
                    message=id_warn,
                    severity="WARNING",
                )
            )
        result.warnings.append(
            MigrationWarning(
                table=view.name,
                column=None,
                oracle_type="VIEW",
                target_type="VIEW",
                message=(
                    f"Vista emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    f"revisar manualmente funciones del motor origen para compatibilidad {self._TARGET_DIALECT}"
                ),
                severity="WARNING",
            )
        )
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            new_table.warnings.append(
                MigrationWarning(
                    table=table.name,
                    column=None,
                    oracle_type="IDENTIFIER",
                    target_type=new_table.name,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        pk_set = {n.upper() for n in (table.primary_key or [])}
        for col in new_table.columns:
            if col.name.upper() in pk_set:
                col.is_primary_key = True

        new_table.columns = [self._transform_column(table.name, col) for col in new_table.columns]
        new_table.primary_key = self._adapt_identifiers(table.name, table.primary_key or [], new_table)
        new_table.indexes = [self._transform_index(table.name, idx, new_table) for idx in table.indexes]
        new_table.foreign_keys = [self._transform_fk(table.name, fk, new_table) for fk in table.foreign_keys]

        return new_table

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        raise NotImplementedError(f"{type(self).__name__} debe implementar _transform_column")

    def _adapt_identifiers(self, table_name: str, names: list[str], target_table: CanonicalTable) -> list[str]:
        adapted: list[str] = []
        for name in names:
            new_name, warn = check_identifier(name, self.MAX_IDENTIFIER_LENGTH)
            if warn:
                target_table.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=name,
                        oracle_type="IDENTIFIER",
                        target_type=new_name,
                        message=warn,
                        severity="WARNING",
                    )
                )
            adapted.append(new_name)
        return adapted

    def _transform_index(self, table_name: str, idx: CanonicalIndex, target_table: CanonicalTable) -> CanonicalIndex:
        new_idx = deepcopy(idx)
        new_idx.name, warn = check_identifier(idx.name, self.MAX_IDENTIFIER_LENGTH)
        if warn:
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    oracle_type="IDENTIFIER",
                    target_type=new_idx.name,
                    message=warn,
                    severity="WARNING",
                )
            )
        new_idx.columns = self._adapt_identifiers(table_name, idx.columns, target_table)
        return new_idx

    def _transform_fk(self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable) -> CanonicalFK:
        new_fk = deepcopy(fk)
        new_fk.name, warn = check_identifier(fk.name, self.MAX_IDENTIFIER_LENGTH)
        if warn:
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    oracle_type="IDENTIFIER",
                    target_type=new_fk.name,
                    message=warn,
                    severity="WARNING",
                )
            )

        # Hook para warnings adicionales específicos del motor destino (ej. ON UPDATE en Oracle)
        self._extra_fk_warnings(table_name, fk, target_table)

        if fk.is_external:
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    oracle_type="FOREIGN KEY",
                    target_type="ALTER TABLE (al final)",
                    message=(
                        f"FK '{fk.name}' referencia tabla '{fk.ref_table}' fuera del schema migrado; "
                        "emitida como ALTER TABLE al final del script — verificar que la tabla existe"
                    ),
                    severity="WARNING",
                )
            )
            new_fk.is_external = True

        return new_fk

    def _extra_fk_warnings(self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable) -> None:
        """Hook para warnings FK adicionales específicos del motor destino. No-op por defecto."""


__all__: list[str] = ["BaseTransformer"]
