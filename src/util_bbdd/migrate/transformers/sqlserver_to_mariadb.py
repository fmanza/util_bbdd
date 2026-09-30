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
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# NVARCHAR max en MariaDB VARCHAR (sin LONGTEXT): 65535 bytes / charset factor
_MARIADB_VARCHAR_MAX: int = 65535
# char_length sentinel de SQL Server para tipos MAX
_SS_MAX_SENTINEL: int = -1


class SQLServerToMariaDBTransformer(BaseTransformer):
    """Transforma IR SQL Server a IR MariaDB.

    El campo ``CanonicalColumn.source_type`` contiene el tipo fuente SQL Server
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_MARIADB_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "MariaDB"

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

        ss_base = col.source_type.upper().split("(")[0].strip()
        mapping = resolve_sqlserver_type_mariadb(ss_base)

        if mapping is None:
            new_col.target_type = "LONGTEXT"
            new_col.ddl_comment = f"-- AVISO: tipo SQL Server '{col.source_type}' desconocido → LONGTEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="LONGTEXT",
                    message=f"Tipo SQL Server '{col.source_type}' no reconocido; mapeado a LONGTEXT",
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
                    category="TYPE",
                    source_type=col.source_type,
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


__all__: list[str] = ["SQLServerToMariaDBTransformer"]
