"""Transformer PostgreSQL → MariaDB.

Responsabilidades:
  - Mapear tipos PostgreSQL a sus equivalentes MariaDB usando type_map_postgresql_to_mariadb.
  - Verificar longitud de identificadores (max 64 chars en MariaDB).
  - Manejar CHARACTER VARYING sin límite (char_length=None) → LONGTEXT.
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Preservar la flag auto_increment (SERIAL); MariaDBDDLEmitter emitirá AUTO_INCREMENT.
  - Poblar MigrationWarning por cada decisión no trivial.
  - Vistas: pass-through v1 (sin reescritura SQL); warning indicando revisión manual.
"""

from __future__ import annotations

from copy import deepcopy

from .._compat.identifier_rules import MAX_MARIADB_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_postgresql_to_mariadb import resolve_postgresql_type_mariadb
from ..ir.models import (
    CanonicalColumn,
    CanonicalView,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer

# VARCHAR máximo práctico en MariaDB (limitado por row size de 65535 bytes)
_MARIADB_VARCHAR_MAX: int = 65535


class PostgreSQLToMariaDBTransformer(BaseTransformer):
    """Transforma IR PostgreSQL a IR MariaDB.

    El campo ``CanonicalColumn.source_type`` contiene el tipo fuente PostgreSQL
    (DATA_TYPE de INFORMATION_SCHEMA en uppercase); el nombre del campo es histórico.
    """

    MAX_IDENTIFIER_LENGTH = MAX_MARIADB_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "MariaDB"

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = deepcopy(view)
        adapted_name, id_warn = check_identifier(view.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            result.name = adapted_name
            result.warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    category="IDENTIFIER",
                    target_type=adapted_name,
                    message=id_warn,
                    severity="WARNING",
                )
            )
        result.warnings.append(
            MigrationWarning(
                table=view.name,
                column=None,
                category="VIEW",
                target_type="VIEW",
                message=(
                    "Vista PostgreSQL emitida sin reescritura de SQL dialect-específico (v1 pass-through); "
                    "revisar manualmente funciones PostgreSQL (NOW(), CURRENT_TIMESTAMP, "
                    "COALESCE, EXTRACT, GENERATE_SERIES, etc.) para compatibilidad MariaDB"
                ),
                severity="WARNING",
            )
        )
        return result

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

        pg_base = col.source_type.upper().strip()
        mapping = resolve_postgresql_type_mariadb(pg_base)

        if mapping is None:
            new_col.target_type = "LONGTEXT"
            new_col.ddl_comment = f"-- AVISO: tipo PostgreSQL '{col.source_type}' desconocido → LONGTEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="LONGTEXT",
                    message=f"Tipo PostgreSQL '{col.source_type}' no reconocido; mapeado a LONGTEXT",
                    severity="WARNING",
                )
            )
            return new_col

        target_type = self._resolve_mariadb_type(pg_base, mapping.mariadb_type, col)
        new_col.target_type = target_type

        if pg_base == "CHARACTER VARYING" and col.char_length is not None and col.char_length > _MARIADB_VARCHAR_MAX:
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="LONGTEXT",
                    message=(
                        f"CHARACTER VARYING({col.char_length}) supera el límite MariaDB de "
                        f"{_MARIADB_VARCHAR_MAX} bytes por fila; mapeado a LONGTEXT"
                    ),
                    severity="WARNING",
                )
            )

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
        pg_base: str,
        mariadb_base: str,
        col: CanonicalColumn,
    ) -> str:
        """Construye el tipo MariaDB con parámetros según el tipo PostgreSQL fuente."""
        if pg_base == "CHARACTER VARYING":
            # char_length=None indica sin límite → LONGTEXT
            if col.char_length is None:
                return "LONGTEXT"
            # Supera el límite práctico de fila MariaDB (65535 bytes) → LONGTEXT
            if col.char_length > _MARIADB_VARCHAR_MAX:
                return "LONGTEXT"
            return f"VARCHAR({col.char_length})"

        if pg_base == "CHARACTER":
            return f"CHAR({col.char_length or 1})"

        if pg_base in ("NUMERIC", "DECIMAL"):
            p = col.precision or 38
            s = col.scale if col.scale is not None else 10
            return f"DECIMAL({p},{s})"

        if pg_base == "BIT":
            # char_length = número de bits (MariaDB BIT(n) nativo)
            length = col.char_length or 1
            return f"BIT({length})"

        if pg_base == "BIT VARYING":
            # Almacenar como VARBINARY(ceil(n/8)); mínimo 1 byte
            length = col.char_length or 1
            byte_len = max(1, (length + 7) // 8)
            return f"VARBINARY({byte_len})"

        # Tipos fijos (mariadb_base ya contiene el tipo completo, ej. "TINYINT(1)", "DATETIME(6)")
        return mariadb_base


__all__: list[str] = ["PostgreSQLToMariaDBTransformer"]
