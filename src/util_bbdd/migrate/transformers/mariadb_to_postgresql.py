"""Transformer MariaDB → PostgreSQL.

Responsabilidades:
  - Mapear tipos MariaDB a sus equivalentes PostgreSQL usando type_map_mariadb_to_postgresql.
  - Verificar longitud de identificadores (max 63 chars en PostgreSQL).
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment; PostgreSQLDDLEmitter emitirá SERIAL/BIGSERIAL/SMALLSERIAL.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_POSTGRESQL_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_mariadb_to_postgresql import resolve_mariadb_type_postgresql
from ..ir.models import (
    CanonicalColumn,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer


class MariaDBToPostgreSQLTransformer(BaseTransformer):
    """Transforma IR MariaDB a IR PostgreSQL.

    El campo ``CanonicalColumn.oracle_type`` contiene el tipo fuente MariaDB
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

        mariadb_base = col.oracle_type.upper().split("(")[0].strip()
        mapping = resolve_mariadb_type_postgresql(mariadb_base)

        if mapping is None:
            new_col.target_type = "TEXT"
            new_col.ddl_comment = f"-- AVISO: tipo MariaDB '{col.oracle_type}' desconocido → TEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type=col.oracle_type,
                    target_type="TEXT",
                    message=f"Tipo MariaDB '{col.oracle_type}' no reconocido; mapeado a TEXT",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_pg_type(mariadb_base, mapping.pg_type, col)
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

    def _resolve_pg_type(self, mariadb_base: str, pg_base: str, col: CanonicalColumn) -> str:
        """Construye el tipo PostgreSQL con parámetros según el tipo MariaDB fuente."""
        if mariadb_base == "VARCHAR":
            return f"VARCHAR({col.char_length or 255})"

        if mariadb_base == "CHAR":
            return f"CHAR({col.char_length or 1})"

        if mariadb_base == "BIT":
            n = col.precision or 1
            return f"BIT({n})"

        if mariadb_base in ("DECIMAL", "NUMERIC"):
            p = col.precision or 18
            s = col.scale or 0
            return f"NUMERIC({p},{s})"

        if mariadb_base == "ENUM":
            return "TEXT"

        # Tipos fijos (TEXT, BYTEA, DATE, TIMESTAMP, BOOLEAN, etc.)
        return pg_base



__all__: list[str] = ["MariaDBToPostgreSQLTransformer"]
