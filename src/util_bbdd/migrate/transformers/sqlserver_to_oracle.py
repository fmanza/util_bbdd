"""Transformer SQL Server → Oracle.

Responsabilidades:
  - Mapear tipos SQL Server a sus equivalentes Oracle usando type_map_sqlserver_to_oracle.
  - Verificar longitud de identificadores (max 30 chars en Oracle 12.1 y anteriores).
  - Detectar char_length=-1 (MAX en SQL Server) y mapear a CLOB/BLOB según tipo.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (IDENTITY) para que OracleDDLEmitter genere SEQUENCE+TRIGGER.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_ORACLE_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_sqlserver_to_oracle import resolve_sqlserver_type_oracle
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# VARCHAR2 / NVARCHAR2 limit en Oracle DDL (sin MAX_STRING_SIZE=EXTENDED)
_ORACLE_VARCHAR2_MAX: int = 4000
# RAW limit en Oracle
_ORACLE_RAW_MAX: int = 2000
# char_length sentinel de SQL Server para tipos MAX
_SS_MAX_SENTINEL: int = -1


class SQLServerToOracleTransformer(BaseTransformer):
    """Transforma IR SQL Server a IR Oracle.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente SQL Server
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_ORACLE_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "Oracle"

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

        # oracle_type contiene el SQL Server DATA_TYPE (nombre histórico del campo)
        ss_base = col.oracle_type.upper().split("(")[0].strip()
        mapping = resolve_sqlserver_type_oracle(ss_base)

        if mapping is None:
            new_col.target_type = "CLOB"
            new_col.ddl_comment = f"-- AVISO: tipo SQL Server '{col.oracle_type}' desconocido → CLOB"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="CLOB",
                    message=f"Tipo SQL Server '{col.oracle_type}' no reconocido; mapeado a CLOB",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_oracle_type(table_name, new_col, ss_base, mapping.oracle_type)
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

    def _resolve_oracle_type(
        self,
        table_name: str,
        col: CanonicalColumn,
        ss_base: str,
        oracle_base: str,
    ) -> str:
        """Construye el tipo Oracle con parámetros según el tipo SQL Server fuente."""
        if ss_base in ("VARCHAR", "NVARCHAR"):
            return self._resolve_varchar_type(table_name, col, ss_base)
        if ss_base in ("CHAR", "NCHAR"):
            base = "NCHAR" if ss_base == "NCHAR" else "CHAR"
            return f"{base}({col.char_length or 1})"
        if ss_base == "BINARY":
            return f"RAW({col.char_length or 1})"
        if ss_base == "VARBINARY":
            return self._resolve_varbinary_type(table_name, col)
        if ss_base in ("DECIMAL", "NUMERIC"):
            s = col.scale if col.scale is not None else 0
            return f"NUMBER({col.precision or 18},{s})"
        # Tipos fijos (oracle_base ya contiene el tipo Oracle completo)
        return oracle_base

    def _resolve_varchar_type(self, table_name: str, col: CanonicalColumn, ss_base: str) -> str:
        """Resuelve VARCHAR/NVARCHAR a VARCHAR2/NVARCHAR2 o CLOB."""
        if col.char_length == _SS_MAX_SENTINEL:
            return "CLOB"
        length = col.char_length or 255
        if length > _ORACLE_VARCHAR2_MAX:
            col.ddl_comment = f"-- AVISO: {ss_base}({length}) → CLOB (supera límite Oracle {_ORACLE_VARCHAR2_MAX})"
            col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.original_name,
                    oracle_type=f"{ss_base}({length})",
                    target_type="CLOB",
                    message=f"{ss_base}({length}) supera límite Oracle ({_ORACLE_VARCHAR2_MAX}); mapeado a CLOB",
                    severity="WARNING",
                )
            )
            return "CLOB"
        base = "NVARCHAR2" if ss_base == "NVARCHAR" else "VARCHAR2"
        return f"{base}({length})"

    def _resolve_varbinary_type(self, table_name: str, col: CanonicalColumn) -> str:
        """Resuelve VARBINARY a RAW o BLOB."""
        if col.char_length == _SS_MAX_SENTINEL:
            return "BLOB"
        length = col.char_length or 255
        if length > _ORACLE_RAW_MAX:
            col.ddl_comment = f"-- AVISO: VARBINARY({length}) → BLOB (supera límite RAW Oracle {_ORACLE_RAW_MAX})"
            col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.original_name,
                    oracle_type=f"VARBINARY({length})",
                    target_type="BLOB",
                    message=f"VARBINARY({length}) supera límite RAW Oracle ({_ORACLE_RAW_MAX}); mapeado a BLOB",
                    severity="WARNING",
                )
            )
            return "BLOB"
        return f"RAW({length})"

    def _extra_fk_warnings(self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable) -> None:
        if fk.on_update and fk.on_update.upper() not in ("NO ACTION", "RESTRICT", ""):
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    oracle_type="FOREIGN KEY",
                    target_type="FK (ON UPDATE ignorado)",
                    message=(
                        f"FK '{fk.name}': ON UPDATE {fk.on_update} no soportado en Oracle; "
                        "la cláusula será omitida — Oracle solo soporta ON DELETE CASCADE/SET NULL"
                    ),
                    severity="WARNING",
                )
            )


__all__: list[str] = ["SQLServerToOracleTransformer"]
