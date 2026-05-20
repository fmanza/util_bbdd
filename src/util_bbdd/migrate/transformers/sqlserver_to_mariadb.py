"""Transformer SQL Server → MariaDB.

Responsabilidades:
  - Mapear tipos SQL Server a sus equivalentes MariaDB usando type_map_sqlserver_to_mariadb.
  - Verificar longitud de identificadores (max 64 chars en MariaDB).
  - Detectar char_length=-1 (MAX en SQL Server) y mapear a TEXT/LONGTEXT/LONGBLOB.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (IDENTITY); MariaDBDDLEmitter emitirá AUTO_INCREMENT.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_MARIADB_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_sqlserver_to_mariadb import resolve_sqlserver_type_mariadb
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)

# NVARCHAR max en MariaDB VARCHAR (sin LONGTEXT): 65535 bytes / charset factor
_MARIADB_VARCHAR_MAX: int = 65535
# char_length sentinel de SQL Server para tipos MAX
_SS_MAX_SENTINEL: int = -1


class SQLServerToMariaDBTransformer:
    """Transforma IR SQL Server a IR MariaDB.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente SQL Server
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma todas las tablas aplicando mapeos SQL Server→MariaDB."""
        return [self._transform_table(t) for t in tables]

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma vistas SQL Server con pass-through v1 (sin reescritura SQL)."""
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
                    "Vista SQL Server emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    "revisar manualmente funciones T-SQL (GETDATE, ISNULL, TOP, etc.) "
                    "para compatibilidad MariaDB"
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

        ss_base = col.oracle_type.upper().split("(")[0].strip()
        mapping = resolve_sqlserver_type_mariadb(ss_base)

        if mapping is None:
            new_col.target_type = "LONGTEXT"
            new_col.ddl_comment = f"-- AVISO: tipo SQL Server '{col.oracle_type}' desconocido → LONGTEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="LONGTEXT",
                    message=f"Tipo SQL Server '{col.oracle_type}' no reconocido; mapeado a LONGTEXT",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_mariadb_type(table_name, new_col, ss_base, mapping.mariadb_type)
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
        table_name: str,
        col: CanonicalColumn,
        ss_base: str,
        mariadb_base: str,
    ) -> str:
        """Construye el tipo MariaDB con parámetros según el tipo SQL Server fuente."""
        is_max = col.char_length == _SS_MAX_SENTINEL

        if ss_base in ("VARCHAR", "NVARCHAR"):
            if is_max:
                return "LONGTEXT"
            length = col.char_length or 255
            return f"VARCHAR({length})"

        if ss_base in ("CHAR", "NCHAR"):
            return f"CHAR({col.char_length or 1})"

        if ss_base == "BINARY":
            return f"BINARY({col.char_length or 1})"

        if ss_base == "VARBINARY":
            if is_max:
                return "LONGBLOB"
            length = col.char_length or 255
            return f"VARBINARY({length})"

        if ss_base in ("DECIMAL", "NUMERIC"):
            p = col.precision or 18
            s = col.scale if col.scale is not None else 0
            return f"DECIMAL({p},{s})"

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


__all__: list[str] = ["SQLServerToMariaDBTransformer"]
