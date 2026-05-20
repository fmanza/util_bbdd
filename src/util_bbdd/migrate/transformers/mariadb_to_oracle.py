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

from .._compat.identifier_rules import MAX_ORACLE_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_mariadb_to_oracle import resolve_mariadb_type_oracle
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)

# VARCHAR2 limit en Oracle DDL (estándar, sin MAX_STRING_SIZE=EXTENDED)
_ORACLE_VARCHAR2_MAX: int = 4000
# RAW limit en Oracle
_ORACLE_RAW_MAX: int = 2000


class MariaDBToOracleTransformer:
    """Transforma IR MariaDB a IR Oracle.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente MariaDB
    (DATA_TYPE de INFORMATION_SCHEMA); el nombre del campo es histórico.
    """

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma todas las tablas aplicando mapeos MariaDB→Oracle."""
        return [self._transform_table(t) for t in tables]

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma vistas MariaDB con pass-through v1 (sin reescritura SQL).

        Cada vista recibe un MigrationWarning indicando que el SQL MariaDB-dialect
        requiere revisión manual antes de ejecutar en Oracle.
        """
        return [self._transform_view(v) for v in views]

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = deepcopy(view)
        adapted_name, id_warn = check_identifier(view.name, MAX_ORACLE_IDENTIFIER_LENGTH)
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
                    "para compatibilidad Oracle"
                ),
                severity="WARNING",
            )
        )
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, MAX_ORACLE_IDENTIFIER_LENGTH)
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

        # Garantizar is_primary_key correcto antes de transformar columnas
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

        col_name_adapted, id_warn = check_identifier(col.name, MAX_ORACLE_IDENTIFIER_LENGTH)
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

        # oracle_type contiene el MariaDB DATA_TYPE (nombre histórico del campo)
        mariadb_base = col.oracle_type.upper().split("(")[0].strip()
        mapping = resolve_mariadb_type_oracle(mariadb_base)

        if mapping is None:
            new_col.target_type = "CLOB"
            new_col.ddl_comment = f"-- AVISO: tipo MariaDB '{col.oracle_type}' desconocido → CLOB"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="CLOB",
                    message=f"Tipo MariaDB '{col.oracle_type}' no reconocido; mapeado a CLOB",
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
        mariadb_base: str,
        oracle_base: str,
    ) -> str:
        """Construye el tipo Oracle con parámetros según el tipo MariaDB fuente."""
        if mariadb_base == "VARCHAR":
            length = col.char_length or 255
            if length > _ORACLE_VARCHAR2_MAX:
                col.ddl_comment = f"-- AVISO: VARCHAR({length}) → CLOB (supera límite VARCHAR2 Oracle {_ORACLE_VARCHAR2_MAX})"
                col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.original_name,
                        oracle_type=f"VARCHAR({length})",
                        target_type="CLOB",
                        message=f"VARCHAR({length}) supera límite VARCHAR2 Oracle ({_ORACLE_VARCHAR2_MAX}); mapeado a CLOB",
                        severity="WARNING",
                    )
                )
                return "CLOB"
            return f"VARCHAR2({length})"

        if mariadb_base == "CHAR":
            return f"CHAR({col.char_length or 1})"

        if mariadb_base == "TINYTEXT":
            return "VARCHAR2(255)"

        if mariadb_base == "BINARY":
            return f"RAW({col.char_length or 1})"

        if mariadb_base == "VARBINARY":
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

        if mariadb_base in ("DECIMAL", "NUMERIC"):
            p = col.precision or 18
            s = col.scale or 0
            return f"NUMBER({p},{s})"

        if mariadb_base == "BIT":
            n = col.precision or 1
            if n == 1:
                return "NUMBER(1,0)"
            return f"RAW({math.ceil(n / 8)})"

        if mariadb_base in ("ENUM", "SET"):
            return "VARCHAR2(255)"

        # Tipo fijo (oracle_base ya contiene el tipo Oracle completo, ej. "NUMBER(10,0)", "CLOB")
        return oracle_base

    def _adapt_identifiers(
        self, table_name: str, names: list[str], target_table: CanonicalTable
    ) -> list[str]:
        adapted: list[str] = []
        for name in names:
            new_name, warn = check_identifier(name, MAX_ORACLE_IDENTIFIER_LENGTH)
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
        new_idx.name, warn = check_identifier(idx.name, MAX_ORACLE_IDENTIFIER_LENGTH)
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
        new_fk.name, warn = check_identifier(fk.name, MAX_ORACLE_IDENTIFIER_LENGTH)
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


__all__: list[str] = ["MariaDBToOracleTransformer"]
