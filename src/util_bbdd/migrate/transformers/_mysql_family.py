"""Base de los transformers dentro de la familia MySQL/MariaDB (MariaDB → MySQL y MySQL → MariaDB).

Ambos motores comparten sintaxis de tipos, así que el tipo destino es el ``COLUMN_TYPE`` completo del origen
(``oracle_type``, extraído con ``full_column_types=True``). Cada subclase declara en ``_TYPE_OVERRIDES`` los tipos
del origen que el destino no tiene, con su sustituto; el aviso va a ``plan.warnings`` (no como comentario en línea:
``MariaDBDDLEmitter`` lo escribe antes de la coma que separa columnas y el ``CREATE TABLE`` resultante no es válido).
"""

from __future__ import annotations

from copy import deepcopy
from typing import ClassVar

from .._compat.identifier_rules import MAX_MARIADB_IDENTIFIER_LENGTH, check_identifier
from ..ir.models import CanonicalColumn, MigrationWarning
from ._base_transformer import BaseTransformer


class MySQLFamilyTransformer(BaseTransformer):
    """Transformer entre MySQL y MariaDB: tipo completo del origen, salvo ``_TYPE_OVERRIDES``."""

    MAX_IDENTIFIER_LENGTH = MAX_MARIADB_IDENTIFIER_LENGTH  # 64 en ambos motores
    _SOURCE_DIALECT: ClassVar[str] = "origen"
    #: Tipo base del origen (en mayúsculas) → tipo destino, para tipos que el destino no tiene.
    _TYPE_OVERRIDES: ClassVar[dict[str, str]] = {}

    def _transform_column(self, table_name: str, col: CanonicalColumn) -> CanonicalColumn:
        new_col = deepcopy(col)

        adapted_name, id_warn = check_identifier(col.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            new_col.name = adapted_name
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    oracle_type="IDENTIFIER",
                    target_type=adapted_name,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        source_type: str = col.oracle_type.strip()
        base: str = source_type.split("(")[0].split(" ")[0].strip().upper()
        override: str | None = self._TYPE_OVERRIDES.get(base)
        if override is None:
            new_col.target_type = source_type
            return new_col

        new_col.target_type = override
        new_col.warnings.append(
            MigrationWarning(
                table=table_name,
                column=col.name,
                oracle_type=source_type,
                target_type=override,
                message=(
                    f"Tipo {base} de {self._SOURCE_DIALECT} sin equivalente en {self._TARGET_DIALECT}; "
                    f"mapeado a {override}"
                ),
                severity="WARNING",
            )
        )
        return new_col


__all__: list[str] = ["MySQLFamilyTransformer"]
