"""Transformer PostgreSQL → Oracle.

Responsabilidades:
  - Mapear tipos PostgreSQL a sus equivalentes Oracle usando type_map_postgresql_to_oracle.
  - Verificar longitud de identificadores (max 30 chars en Oracle 12.1 y anteriores).
  - Manejar CHARACTER VARYING sin límite (char_length=None) → CLOB.
  - Manejar CHARACTER VARYING > 4000 → CLOB con warning.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (SERIAL) para que OracleDDLEmitter genere SEQUENCE+TRIGGER.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_ORACLE_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_postgresql_to_oracle import resolve_postgresql_type_oracle
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# VARCHAR2 / NVARCHAR2 limit en Oracle DDL (sin MAX_STRING_SIZE=EXTENDED)
_ORACLE_VARCHAR2_MAX: int = 4000


class PostgreSQLToOracleTransformer(BaseTransformer):
    """Transforma IR PostgreSQL a IR Oracle.

    El campo ``CanonicalColumn.source_type`` contiene el tipo fuente PostgreSQL
    (DATA_TYPE de INFORMATION_SCHEMA en uppercase); el nombre del campo es histórico.
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
                    category="IDENTIFIER",
                    target_type=col_name_adapted,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        # source_type contiene el PostgreSQL DATA_TYPE en uppercase
        pg_base = col.source_type.upper().strip()
        mapping = resolve_postgresql_type_oracle(pg_base)

        if mapping is None:
            new_col.target_type = "CLOB"
            new_col.ddl_comment = f"-- AVISO: tipo PostgreSQL '{col.source_type}' desconocido → CLOB"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="CLOB",
                    message=f"Tipo PostgreSQL '{col.source_type}' no reconocido; mapeado a CLOB",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_oracle_type(table_name, new_col, pg_base, mapping.oracle_type)
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
        pg_base: str,
        oracle_base: str,
    ) -> str:
        """Construye el tipo Oracle con parámetros según el tipo PostgreSQL fuente."""
        if pg_base == "CHARACTER VARYING":
            # char_length=None indica sin límite explícito → CLOB
            if col.char_length is None:
                return "CLOB"
            if col.char_length > _ORACLE_VARCHAR2_MAX:
                col.ddl_comment = (
                    f"-- AVISO: CHARACTER VARYING({col.char_length}) → CLOB "
                    f"(supera límite Oracle {_ORACLE_VARCHAR2_MAX})"
                )
                col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.original_name,
                        category="TYPE",
                        source_type=f"CHARACTER VARYING({col.char_length})",
                        target_type="CLOB",
                        message=(
                            f"CHARACTER VARYING({col.char_length}) supera límite Oracle "
                            f"({_ORACLE_VARCHAR2_MAX}); mapeado a CLOB"
                        ),
                        severity="WARNING",
                    )
                )
                return "CLOB"
            return f"VARCHAR2({col.char_length})"

        if pg_base == "CHARACTER":
            length = col.char_length or 1
            return f"CHAR({length})"

        if pg_base in ("NUMERIC", "DECIMAL"):
            p = col.precision or 38
            s = col.scale if col.scale is not None else 10
            return f"NUMBER({p},{s})"

        if pg_base == "BIT":
            # char_length = número de bits → CHAR(n) almacena la cadena de bits
            length = col.char_length or 1
            return f"CHAR({length})"

        if pg_base == "BIT VARYING":
            length = col.char_length or 1
            return f"VARCHAR2({length})"

        # Tipos fijos (oracle_base ya contiene el tipo Oracle completo)
        return oracle_base

    def _extra_fk_warnings(self, table_name: str, fk: CanonicalFK, target_table: CanonicalTable) -> None:
        if fk.on_update and fk.on_update.upper() not in ("NO ACTION", "RESTRICT", ""):
            target_table.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=None,
                    category="FOREIGN_KEY",
                    target_type="FK (ON UPDATE ignorado)",
                    code="FK_ON_UPDATE_IGNORED",
                    message=(
                        f"FK '{fk.name}': ON UPDATE {fk.on_update} no soportado en Oracle; "
                        "la cláusula será omitida — Oracle solo soporta ON DELETE CASCADE/SET NULL"
                    ),
                    severity="WARNING",
                )
            )


__all__: list[str] = ["PostgreSQLToOracleTransformer"]
