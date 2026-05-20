"""Transformer PostgreSQL → MariaDB.

Responsabilidades:
  - Mapear tipos PostgreSQL a sus equivalentes MariaDB usando type_map_postgresql_to_mariadb.
  - Verificar longitud de identificadores (max 64 chars en MariaDB).
  - Manejar CHARACTER VARYING sin límite (char_length=None) → LONGTEXT.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (SERIAL); MariaDBDDLEmitter emitirá AUTO_INCREMENT.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_MARIADB_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_postgresql_to_mariadb import resolve_postgresql_type_mariadb
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)

# VARCHAR máximo práctico en MariaDB (limitado por row size de 65535 bytes)
_MARIADB_VARCHAR_MAX: int = 65535


class PostgreSQLToMariaDBTransformer:
    """Transforma IR PostgreSQL a IR MariaDB.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente PostgreSQL
    (DATA_TYPE de INFORMATION_SCHEMA en uppercase); el nombre del campo es histórico.
    """

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma todas las tablas aplicando mapeos PostgreSQL→MariaDB."""
        return [self._transform_table(t) for t in tables]

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma vistas PostgreSQL con pass-through v1 (sin reescritura SQL)."""
        return [self._transform_view(v) for v in views]

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = deepcopy(view)
        adapted_name, id_warn = check_identifier(view.name, MAX_MARIADB_IDENTIFIER_LENGTH)
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
                    "Vista PostgreSQL emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    "revisar manualmente funciones PostgreSQL (NOW(), CURRENT_TIMESTAMP, "
                    "COALESCE, EXTRACT, GENERATE_SERIES, etc.) para compatibilidad MariaDB"
                ),
                severity="WARNING",
            )
        )
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, MAX_MARIADB_IDENTIFIER_LENGTH)
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

        pk_set = {n.upper() for n in table.primary_key}
        for col in new_table.columns:
            if col.name.upper() in pk_set:
                col.is_primary_key = True

        new_table.columns = [self._transform_column(table.name, col) for col in new_table.columns]
        new_table.primary_key = self._adapt_identifiers(table.name, table.primary_key, new_table)
        new_table.indexes = [self._transform_index(table.name, idx, new_table) for idx in table.indexes]
        new_table.foreign_keys = [self._transform_fk(table.name, fk, new_table) for fk in table.foreign_keys]

        return new_table

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        new_col = deepcopy(col)

        col_name_adapted, id_warn = check_identifier(col.name, MAX_MARIADB_IDENTIFIER_LENGTH)
        if id_warn:
            new_col.name = col_name_adapted
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type="IDENTIFIER",
                    target_type=col_name_adapted,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        pg_base = col.oracle_type.upper().strip()
        mapping = resolve_postgresql_type_mariadb(pg_base)

        if mapping is None:
            new_col.target_type = "LONGTEXT"
            new_col.ddl_comment = f"-- AVISO: tipo PostgreSQL '{col.oracle_type}' desconocido → LONGTEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="LONGTEXT",
                    message=f"Tipo PostgreSQL '{col.oracle_type}' no reconocido; mapeado a LONGTEXT",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_mariadb_type(pg_base, mapping.mariadb_type, col)
        new_col.target_type = target_type

        if mapping.requires_ddl_comment and mapping.ddl_comment:
            new_col.ddl_comment = mapping.ddl_comment

        if mapping.warning_msg:
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type=target_type,
                    message=mapping.warning_msg,
                    severity=mapping.severity,
                    proposals=mapping.proposals,
                )
            )

        return new_col

    def _resolve_mariadb_type(
        self,
        pg_base: str,
        mariadb_base: str,
        col: CanonicalColumn,
    ) -> str:
        """Construye el tipo MariaDB con parámetros según el tipo PostgreSQL fuente."""
        if pg_base == "CHARACTER VARYING":
            # char_length=None indica sin límite → LONGTEXT
            if col.char_length is None:
                return "LONGTEXT"
            return f"VARCHAR({col.char_length})"

        if pg_base == "CHARACTER":
            return f"CHAR({col.char_length or 1})"

        if pg_base in ("NUMERIC", "DECIMAL"):
            p = col.precision or 38
            s = col.scale if col.scale is not None else 10
            return f"DECIMAL({p},{s})"

        if pg_base == "BIT":
            # char_length = número de bits (MariaDB BIT(n) nativo)
            length = col.char_length or 1
            return f"BIT({length})"

        if pg_base == "BIT VARYING":
            # Almacenar como VARBINARY(ceil(n/8)); mínimo 1 byte
            length = col.char_length or 1
            byte_len = max(1, (length + 7) // 8)
            return f"VARBINARY({byte_len})"

        # Tipos fijos (mariadb_base ya contiene el tipo completo, ej. "TINYINT(1)", "DATETIME(6)")
        return mariadb_base

    def _adapt_identifiers(
        self, table_name: str, names: list[str], target_table: CanonicalTable
    ) -> list[str]:
        adapted: list[str] = []
        for name in names:
            new_name, warn = check_identifier(name, MAX_MARIADB_IDENTIFIER_LENGTH)
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

    def _transform_index(
        self, table_name: str, idx: CanonicalIndex, target_table: CanonicalTable
    ) -> CanonicalIndex:
        new_idx = deepcopy(idx)
        new_idx.name, warn = check_identifier(idx.name, MAX_MARIADB_IDENTIFIER_LENGTH)
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

    def _transform_fk(
        self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable
    ) -> CanonicalFK:
        new_fk = deepcopy(fk)
        new_fk.name, warn = check_identifier(fk.name, MAX_MARIADB_IDENTIFIER_LENGTH)
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


__all__: list[str] = ["PostgreSQLToMariaDBTransformer"]
