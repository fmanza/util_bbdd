"""Transformer SQL Server → PostgreSQL.

Responsabilidades:
  - Mapear tipos SQL Server a sus equivalentes PostgreSQL usando type_map_sqlserver_to_postgresql.
  - Verificar longitud de identificadores (max 63 chars en PostgreSQL).
  - Detectar char_length=-1 (MAX en SQL Server) y mapear a TEXT/BYTEA.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (IDENTITY); PostgreSQLDDLEmitter emitirá SERIAL/BIGSERIAL.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_POSTGRESQL_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_sqlserver_to_postgresql import resolve_sqlserver_type_postgresql
from ..ir.models import (
    CanonicalColumn,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# char_length sentinel de SQL Server para tipos MAX
_SS_MAX_SENTINEL: int = -1


class SQLServerToPostgreSQLTransformer(BaseTransformer):
    """Transforma IR SQL Server a IR PostgreSQL.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente SQL Server
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_POSTGRESQL_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "PostgreSQL"

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        new_col = deepcopy(col)

        col_name_adapted, id_warn = check_identifier(col.name, self.MAX_IDENTIFIER_LENGTH)
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
        mapping = resolve_sqlserver_type_postgresql(ss_base)

        if mapping is None:
            new_col.target_type = "TEXT"
            new_col.ddl_comment = f"-- AVISO: tipo SQL Server '{col.oracle_type}' desconocido → TEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="TEXT",
                    message=f"Tipo SQL Server '{col.oracle_type}' no reconocido; mapeado a TEXT",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_pg_type(ss_base, mapping.pg_type, col)
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

    def _resolve_pg_type(self, ss_base: str, pg_base: str, col: CanonicalColumn) -> str:
        """Construye el tipo PostgreSQL con parámetros según el tipo SQL Server fuente."""
        is_max = col.char_length == _SS_MAX_SENTINEL

        if ss_base in ("VARCHAR", "NVARCHAR"):
            if is_max:
                return "TEXT"
            return f"VARCHAR({col.char_length or 255})"

        if ss_base in ("CHAR", "NCHAR"):
            return f"CHAR({col.char_length or 1})"

        if ss_base in ("BINARY", "VARBINARY"):
            # BYTEA en PostgreSQL no lleva parámetros de longitud
            return "BYTEA"

        if ss_base in ("DECIMAL", "NUMERIC"):
            p = col.precision or 18
            s = col.scale if col.scale is not None else 0
            return f"NUMERIC({p},{s})"

        # Tipos fijos (TEXT, DATE, TIMESTAMP, BOOLEAN, BYTEA, UUID, XML, etc.)
        return pg_base


__all__: list[str] = ["SQLServerToPostgreSQLTransformer"]
