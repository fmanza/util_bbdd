"""Transformer MariaDB → SQL Server.

Responsabilidades:
  - Mapear tipos MariaDB a sus equivalentes SQL Server usando type_map_mariadb_to_sqlserver.
  - Verificar longitud de identificadores (max 128 chars en SQL Server).
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment; SQLServerDDLEmitter emitirá IDENTITY(1,1).
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_SQLSERVER_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_mariadb_to_sqlserver import resolve_mariadb_type_sqlserver
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)

# NVARCHAR max en SQL Server sin (MAX): 4000 caracteres Unicode
_SS_NVARCHAR_MAX: int = 4000


class MariaDBToSQLServerTransformer:
    """Transforma IR MariaDB a IR SQL Server.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente MariaDB
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma todas las tablas aplicando mapeos MariaDB→SQL Server."""
        return [self._transform_table(t) for t in tables]

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma vistas MariaDB con pass-through v1 (sin reescritura SQL)."""
        return [self._transform_view(v) for v in views]

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = deepcopy(view)
        adapted_name, id_warn = check_identifier(view.name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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
                    "Vista MariaDB emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    "revisar manualmente funciones MariaDB (NOW, IFNULL, GROUP_CONCAT, etc.) "
                    "para compatibilidad SQL Server"
                ),
                severity="WARNING",
            )
        )
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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

        col_name_adapted, id_warn = check_identifier(col.name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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

        mariadb_base = col.oracle_type.upper().split("(")[0].strip()
        mapping = resolve_mariadb_type_sqlserver(mariadb_base)

        if mapping is None:
            new_col.target_type = "NVARCHAR(MAX)"
            new_col.ddl_comment = f"-- AVISO: tipo MariaDB '{col.oracle_type}' desconocido → NVARCHAR(MAX)"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="NVARCHAR(MAX)",
                    message=f"Tipo MariaDB '{col.oracle_type}' no reconocido; mapeado a NVARCHAR(MAX)",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_ss_type(mariadb_base, mapping.sqlserver_type, col)
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

    def _resolve_ss_type(self, mariadb_base: str, ss_base: str, col: CanonicalColumn) -> str:
        """Construye el tipo SQL Server con parámetros según el tipo MariaDB fuente."""
        if mariadb_base == "VARCHAR":
            length = col.char_length or 255
            if length > _SS_NVARCHAR_MAX:
                return "NVARCHAR(MAX)"
            return f"NVARCHAR({length})"

        if mariadb_base == "CHAR":
            return f"NCHAR({col.char_length or 1})"

        if mariadb_base == "BINARY":
            return f"BINARY({col.char_length or 1})"

        if mariadb_base == "VARBINARY":
            length = col.char_length or 255
            if length > 8000:
                return "VARBINARY(MAX)"
            return f"VARBINARY({length})"

        if mariadb_base in ("DECIMAL", "NUMERIC"):
            p = col.precision or 18
            s = col.scale or 0
            return f"{ss_base}({p},{s})"

        if mariadb_base == "ENUM":
            return "NVARCHAR(255)"

        # Tipos fijos o ya con parámetros en ss_base
        return ss_base

    def _adapt_identifiers(
        self, table_name: str, names: list[str], target_table: CanonicalTable
    ) -> list[str]:
        adapted: list[str] = []
        for name in names:
            new_name, warn = check_identifier(name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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
        new_idx.name, warn = check_identifier(idx.name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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
        new_fk.name, warn = check_identifier(fk.name, MAX_SQLSERVER_IDENTIFIER_LENGTH)
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


__all__: list[str] = ["MariaDBToSQLServerTransformer"]
