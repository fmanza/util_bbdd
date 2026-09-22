"""Transformer Oracle → PostgreSQL.

Responsabilidades:
  - Mapear tipos Oracle a sus equivalentes PostgreSQL usando type_map_postgresql.
  - Detectar columnas con DEFAULT SEQUENCE.NEXTVAL y marcarlas como SERIAL/BIGSERIAL.
  - Verificar longitud de identificadores (max 63 bytes en PostgreSQL).
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Poblar MigrationWarning por cada decisión no trivial.
"""

from __future__ import annotations

import re

from copy import deepcopy

from .._compat.identifier_rules import MAX_POSTGRESQL_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_oracle_to_postgresql import resolve_number_type_postgresql, resolve_oracle_type_postgresql
from ..ir.models import (
    CanonicalColumn,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer
from ._view_rewriter import rewrite_oracle_view

_NEXTVAL_RE = re.compile(r"\b(\w+)\.NEXTVAL\b", re.IGNORECASE)

# Tipos PG enteros que se convierten a SERIAL cuando auto_increment=True
_INT_TYPES_SERIAL = frozenset({"SMALLINT", "INTEGER", "BIGINT"})

# VARCHAR2 max sin desbordamiento en PG: 10485760 chars pero limit razonable
_VARCHAR_MAX_LENGTH: int = 10_485_760


class OracleToPostgreSQLTransformer(BaseTransformer):
    """Transforma IR Oracle a IR PostgreSQL.

    Args:
        number_fallback: Tipo destino cuando NUMBER no tiene precisión.
            Valores recomendados: "DOUBLE PRECISION", "NUMERIC(38,10)", "NUMERIC(18,4)".
    """

    MAX_IDENTIFIER_LENGTH = MAX_POSTGRESQL_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "PostgreSQL"

    def __init__(self, number_fallback: str = "DOUBLE PRECISION") -> None:
        self._number_fallback = number_fallback

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = rewrite_oracle_view(
            view,
            sysdate_fn="NOW()",
            systimestamp_fn="NOW()",
            user_fn="CURRENT_USER",
            schema=view.schema,
        )
        adapted_name, id_warn = check_identifier(view.name, self.MAX_IDENTIFIER_LENGTH)
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
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, self.MAX_IDENTIFIER_LENGTH)
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

        # Garantizar is_primary_key correcto en la copia antes de transformar.
        pk_set = {n.upper() for n in table.primary_key}
        for col in new_table.columns:
            if col.name.upper() in pk_set:
                col.is_primary_key = True

        new_table.columns = [self._transform_column(table.name, col) for col in new_table.columns]
        new_table.primary_key = self._adapt_identifiers(table.name, table.primary_key, new_table)
        new_table.indexes = [self._transform_index(table.name, idx, new_table) for idx in table.indexes]
        new_table.foreign_keys = [self._transform_fk(table.name, fk, new_table) for fk in table.foreign_keys]

        self._handle_sequence_columns(new_table)
        self._handle_pk_serial(new_table)

        return new_table

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

        oracle_base = col.oracle_type.upper().split("(")[0].strip()

        if oracle_base == "NUMBER":
            target_type, ddl_comment = resolve_number_type_postgresql(col.precision, col.scale, self._number_fallback)
            if col.is_primary_key and col.precision is None:
                # PK con NUMBER sin precisión: forzar INTEGER
                target_type = "INTEGER"
                ddl_comment = None
            new_col.target_type = target_type
            if ddl_comment:
                new_col.ddl_comment = ddl_comment
                new_col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.name,
                        oracle_type=col.oracle_type,
                        target_type=target_type,
                        message=f"NUMBER sin precisión → {self._number_fallback}",
                        severity="WARNING",
                    )
                )
            return new_col

        mapping = resolve_oracle_type_postgresql(oracle_base)

        if mapping is None:
            new_col.target_type = "TEXT"
            new_col.ddl_comment = f"-- AVISO: tipo Oracle '{col.oracle_type}' desconocido → TEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="TEXT",
                    message=f"Tipo Oracle '{col.oracle_type}' no reconocido; mapeado a TEXT",
                    severity="WARNING",
                )
            )
            return new_col

        # ROWID/UROWID: omitir columna
        if mapping.pg_type == "":
            new_col.omit = True
            new_col.target_type = ""
            new_col.ddl_comment = mapping.ddl_comment
            if mapping.warning_msg:
                new_col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.name,
                        oracle_type=col.oracle_type,
                        target_type="(omitido)",
                        message=mapping.warning_msg,
                        severity=mapping.severity,
                        proposals=mapping.proposals,
                    )
                )
            return new_col

        target_type = self._build_target_type(mapping.pg_type, oracle_base, col)
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

    def _build_target_type(self, pg_base: str, oracle_base: str, col: CanonicalColumn) -> str:
        """Construye el tipo PostgreSQL con parámetros según el tipo Oracle."""
        # VARCHAR2/VARCHAR/NVARCHAR2 → VARCHAR(n)
        if oracle_base in ("VARCHAR2", "VARCHAR", "NVARCHAR2"):
            length = col.char_length or 255
            return f"VARCHAR({length})"

        # CHAR/NCHAR → CHAR(n)
        if oracle_base in ("CHAR", "NCHAR"):
            length = col.char_length or 1
            return f"CHAR({length})"

        # DECIMAL/NUMERIC con precision/scale
        if oracle_base in ("NUMERIC", "DECIMAL"):
            p = col.precision or 18
            s = col.scale or 0
            return f"NUMERIC({p},{s})"

        # TIMESTAMP con precision (max 6 en PostgreSQL)
        if oracle_base == "TIMESTAMP":
            prec = min(col.scale, 6) if col.scale is not None else 6
            return f"TIMESTAMP({prec})"

        # Tipos fijos: retornar pg_type directamente
        return pg_base

    def _handle_pk_serial(self, table: CanonicalTable) -> None:
        """Marca la columna PK única como SERIAL/BIGSERIAL si es tipo entero."""
        if len(table.primary_key) != 1:
            return  # PK compuesta: SERIAL no aplica

        pk_col_name = table.primary_key[0]
        pk_col = next(
            (c for c in table.columns if c.name == pk_col_name and not c.omit),
            None,
        )
        if pk_col is None or pk_col.auto_increment:
            return  # Ya marcada (por NEXTVAL) o no encontrada

        base_type = pk_col.target_type.split("(")[0].upper().strip()
        if base_type not in _INT_TYPES_SERIAL:
            # NUMBER sin precisión en PK → resolver como INTEGER
            oracle_base = pk_col.oracle_type.upper().split("(")[0].strip()
            if oracle_base != "NUMBER" or pk_col.precision is not None:
                return
            pk_col.target_type = "INTEGER"
            pk_col.ddl_comment = None
            pk_col.warnings = [w for w in pk_col.warnings if w.severity != "WARNING"]

        pk_col.auto_increment = True
        pk_col.nullable = False
        table.warnings.append(
            MigrationWarning(
                table=table.name,
                column=pk_col_name,
                oracle_type=pk_col.oracle_type,
                target_type=pk_col.target_type,
                message=f"Columna PK '{pk_col_name}' marcada como SERIAL/BIGSERIAL",
                severity="INFO",
            )
        )

    def _handle_sequence_columns(self, table: CanonicalTable) -> None:
        """Detecta columnas con DEFAULT .NEXTVAL y las convierte a SERIAL/BIGSERIAL."""
        for col in table.columns:
            if col.omit:
                continue
            seq_name = _detect_sequence(col.default)
            if seq_name is None:
                continue

            col.auto_increment = True
            col.default = None

            if not col.is_primary_key and col.name not in table.primary_key:
                table.warnings.append(
                    MigrationWarning(
                        table=table.name,
                        column=col.name,
                        oracle_type=f"SEQUENCE({seq_name})",
                        target_type="SERIAL",
                        message=(
                            f"Columna '{col.name}' usa secuencia '{seq_name}' pero no es PK; "
                            "convertida a SERIAL en PostgreSQL"
                        ),
                        severity="WARNING",
                    )
                )
                col.is_primary_key = True
                if col.name not in table.primary_key:
                    table.primary_key.insert(0, col.name)
            else:
                table.warnings.append(
                    MigrationWarning(
                        table=table.name,
                        column=col.name,
                        oracle_type=f"SEQUENCE({seq_name})",
                        target_type="SERIAL",
                        message=f"Secuencia Oracle '{seq_name}' convertida a SERIAL/BIGSERIAL",
                        severity="INFO",
                    )
                )


def _detect_sequence(default: str | None) -> str | None:
    """Retorna el nombre de la secuencia si el default contiene .NEXTVAL."""
    if not default:
        return None
    m = _NEXTVAL_RE.search(default)
    return m.group(1) if m else None


__all__: list[str] = ["OracleToPostgreSQLTransformer"]
