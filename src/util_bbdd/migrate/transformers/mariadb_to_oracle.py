"""Transformer MariaDB → Oracle.

Responsabilidades:
  - Mapear tipos MariaDB a sus equivalentes Oracle usando type_map_mariadb_to_oracle.
  - Verificar longitud de identificadores (max 30 chars en Oracle 12.1 y anteriores).
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment para que OracleDDLEmitter genere SEQUENCE+TRIGGER.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

import math

from copy import deepcopy

from .._compat.identifier_rules import MAX_ORACLE_IDENTIFIER_LENGTH
from .._compat.type_map_mariadb_to_oracle import resolve_mariadb_type_oracle
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# VARCHAR2 limit en Oracle DDL (estándar, sin MAX_STRING_SIZE=EXTENDED)
_ORACLE_VARCHAR2_MAX: int = 4000
# RAW limit en Oracle
_ORACLE_RAW_MAX: int = 2000


class MariaDBToOracleTransformer(BaseTransformer):
    """Transforma IR MariaDB a IR Oracle.

    El campo ``CanonicalColumn.source_type`` contiene el tipo fuente MariaDB
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_ORACLE_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "Oracle"

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        from .._compat.identifier_rules import check_identifier

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

        # source_type contiene el MariaDB DATA_TYPE
        mariadb_base = col.source_type.upper().split("(")[0].strip()
        mapping = resolve_mariadb_type_oracle(mariadb_base)

        if mapping is None:
            new_col.target_type = "CLOB"
            new_col.ddl_comment = f"-- AVISO: tipo MariaDB '{col.source_type}' desconocido → CLOB"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="CLOB",
                    message=f"Tipo MariaDB '{col.source_type}' no reconocido; mapeado a CLOB",
                    severity="WARNING",
                )
            )
            return new_col

        # Tipos con parámetros dinámicos
        target_type = self._resolve_oracle_type(table_name, new_col, mariadb_base, mapping.oracle_type)

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

    def _resolve_oracle_type(
        self,
        table_name: str,
        col: CanonicalColumn,
        mariadb_base: str,
        oracle_base: str,
    ) -> str:
        """Construye el tipo Oracle con parámetros según el tipo MariaDB fuente."""
        if mariadb_base == "VARCHAR":
            return self._resolve_varchar_type(table_name, col)
        if mariadb_base == "CHAR":
            return f"CHAR({col.char_length or 1})"
        if mariadb_base == "TINYTEXT":
            return "VARCHAR2(255)"
        if mariadb_base == "BINARY":
            return f"RAW({col.char_length or 1})"
        if mariadb_base == "VARBINARY":
            return self._resolve_varbinary_type(table_name, col)
        if mariadb_base in ("DECIMAL", "NUMERIC"):
            return f"NUMBER({col.precision or 18},{col.scale or 0})"
        if mariadb_base == "BIT":
            return self._resolve_bit_type(col)
        if mariadb_base in ("ENUM", "SET"):
            return "VARCHAR2(255)"
        # Tipo fijo (oracle_base ya contiene el tipo Oracle completo, ej. "NUMBER(10,0)", "CLOB")
        return oracle_base

    def _resolve_varchar_type(self, table_name: str, col: CanonicalColumn) -> str:
        """Resuelve VARCHAR a VARCHAR2 o CLOB."""
        length = col.char_length or 255
        if length > _ORACLE_VARCHAR2_MAX:
            col.ddl_comment = (
                f"-- AVISO: VARCHAR({length}) → CLOB (supera límite VARCHAR2 Oracle {_ORACLE_VARCHAR2_MAX})"
            )
            col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.original_name,
                    category="TYPE",
                    source_type=f"VARCHAR({length})",
                    target_type="CLOB",
                    message=f"VARCHAR({length}) supera límite VARCHAR2 Oracle ({_ORACLE_VARCHAR2_MAX}); mapeado a CLOB",
                    severity="WARNING",
                )
            )
            return "CLOB"
        return f"VARCHAR2({length})"

    def _resolve_varbinary_type(self, table_name: str, col: CanonicalColumn) -> str:
        """Resuelve VARBINARY a RAW o BLOB."""
        length = col.char_length or 255
        if length > _ORACLE_RAW_MAX:
            col.ddl_comment = f"-- AVISO: VARBINARY({length}) → BLOB (supera límite RAW Oracle {_ORACLE_RAW_MAX})"
            col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.original_name,
                    category="TYPE",
                    source_type=f"VARBINARY({length})",
                    target_type="BLOB",
                    message=f"VARBINARY({length}) supera límite RAW Oracle ({_ORACLE_RAW_MAX}); mapeado a BLOB",
                    severity="WARNING",
                )
            )
            return "BLOB"
        return f"RAW({length})"

    def _resolve_bit_type(self, col: CanonicalColumn) -> str:
        """Resuelve BIT(n): NUMBER(1,0) para n=1, RAW(ceil(n/8)) para n>1."""
        n = col.precision or 1
        if n == 1:
            return "NUMBER(1,0)"
        return f"RAW({math.ceil(n / 8)})"

    def _extra_fk_warnings(self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable) -> None:
        if fk.on_update and fk.on_update.upper() not in ("NO ACTION", "RESTRICT", ""):
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    category="FOREIGN_KEY",
                    target_type="FK (ON UPDATE ignorado)",
                    message=(
                        f"FK '{fk.name}': ON UPDATE {fk.on_update} no soportado en Oracle; "
                        "la cláusula será omitida — Oracle solo soporta ON DELETE CASCADE/SET NULL"
                    ),
                    severity="WARNING",
                )
            )


__all__: list[str] = ["MariaDBToOracleTransformer"]
