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
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# NVARCHAR max en SQL Server sin (MAX): 4000 caracteres Unicode
_SS_NVARCHAR_MAX: int = 4000


class MariaDBToSQLServerTransformer(BaseTransformer):
    """Transforma IR MariaDB a IR SQL Server.

    El campo ``CanonicalColumn.source_type`` contiene el tipo fuente MariaDB
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_SQLSERVER_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "SQL Server"

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        new_col = deepcopy(col)

        col_name_adapted, id_warn = check_identifier(col.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            new_col.name = col_name_adapted
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="IDENTIFIER",
                    target_type=col_name_adapted,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        mariadb_base = col.source_type.upper().split("(")[0].strip()
        mapping = resolve_mariadb_type_sqlserver(mariadb_base)

        if mapping is None:
            new_col.target_type = "NVARCHAR(MAX)"
            new_col.ddl_comment = f"-- AVISO: tipo MariaDB '{col.source_type}' desconocido → NVARCHAR(MAX)"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="NVARCHAR(MAX)",
                    message=f"Tipo MariaDB '{col.source_type}' no reconocido; mapeado a NVARCHAR(MAX)",
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
                    category="TYPE",
                    source_type=col.source_type,
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


__all__: list[str] = ["MariaDBToSQLServerTransformer"]
