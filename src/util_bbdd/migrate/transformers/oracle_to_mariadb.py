"""Transformer Oracle → MariaDB.

Responsabilidades:
  - Mapear tipos Oracle a sus equivalentes MariaDB usando type_map.
  - Detectar columnas con DEFAULT SEQUENCE.NEXTVAL y marcarlas como AUTO_INCREMENT.
  - Verificar longitud de identificadores (max 64 chars en MariaDB).
  - Marcar FKs externas (ref_table fuera del schema) con aviso.
  - Poblar MigrationWarning por cada decisión no trivial.
"""

from __future__ import annotations

import re

from copy import deepcopy

from .._compat.identifier_rules import MAX_MARIADB_IDENTIFIER_LENGTH, check_identifier
from .._compat.type_map_oracle_to_mariadb import resolve_number_type, resolve_oracle_type
from ..ir.models import (
    CanonicalColumn,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)
from ._base_transformer import BaseTransformer
from ._view_rewriter import rewrite_oracle_view

_NEXTVAL_RE = re.compile(r"\b(\w+)\.NEXTVAL\b", re.IGNORECASE)

_NVARCHAR_CHARSETS = {"NVARCHAR2", "NCHAR"}
_LOB_UTF8 = {"CLOB", "NCLOB"}


_INT_TYPES_AUTOINCREMENT = frozenset({"BIGINT", "INT", "INTEGER", "SMALLINT", "TINYINT", "MEDIUMINT"})


class OracleToMariaDBTransformer(BaseTransformer):
    """Transforma IR Oracle a IR MariaDB.

    Args:
        number_fallback: Tipo destino cuando NUMBER no tiene precisión.
            Valores aceptados: "DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)".
        charset: Charset MariaDB para columnas de texto.
        int_display_width: Display width para tipo INT (convenio MariaDB).
            11 por defecto; 0 deshabilita el display width (solo INT sin parámetro).
    """

    MAX_IDENTIFIER_LENGTH = MAX_MARIADB_IDENTIFIER_LENGTH
    _TARGET_DIALECT = "MariaDB"

    def __init__(
        self,
        number_fallback: str = "DOUBLE",
        charset: str = "utf8mb4",
        int_display_width: int = 11,
    ) -> None:
        self._number_fallback = number_fallback
        self._charset = charset
        self._int_display_width = int_display_width

    def _transform_view(self, view: CanonicalView) -> CanonicalView:
        result = rewrite_oracle_view(
            view,
            sysdate_fn="NOW()",
            systimestamp_fn="NOW()",
            user_fn="CURRENT_USER()",
            schema=view.schema,
        )
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
        return result

    def _transform_table(self, table: CanonicalTable) -> CanonicalTable:
        new_table = deepcopy(table)

        new_table.name, id_warn = check_identifier(table.name, self.MAX_IDENTIFIER_LENGTH)
        if id_warn:
            new_table.warnings.append(
                MigrationWarning(
                    table=table.name,
                    column=None,
                    category="IDENTIFIER",
                    target_type=new_table.name,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        # Garantizar is_primary_key correcto en la copia antes de transformar.
        # El flag puede estar a False si el IR se construyó sin pasar por OracleSchemaExtractor.
        pk_set = {n.upper() for n in table.primary_key}
        for col in new_table.columns:
            if col.name.upper() in pk_set:
                col.is_primary_key = True

        new_table.columns = [self._transform_column(table.name, col) for col in new_table.columns]

        new_table.primary_key = self._adapt_identifiers(table.name, table.primary_key, new_table)

        new_table.indexes = [self._transform_index(table.name, idx, new_table) for idx in table.indexes]

        new_table.foreign_keys = [self._transform_fk(table.name, fk, new_table) for fk in table.foreign_keys]

        self._handle_sequence_columns(new_table)
        self._handle_pk_auto_increment(new_table)

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
                    category="IDENTIFIER",
                    target_type=col_name_adapted,
                    message=id_warn,
                    severity="WARNING",
                )
            )

        oracle_base = col.source_type.upper().split("(")[0].strip()

        if oracle_base == "NUMBER":
            target_type, ddl_comment = resolve_number_type(col.precision, col.scale, self._number_fallback)
            if col.is_primary_key and col.precision is None:
                # PK con NUMBER sin precisión: forzar INT (is_primary_key garantizado por _transform_table)
                target_type = "INT"
                ddl_comment = None
            new_col.target_type = self._with_int_width(target_type)
            if ddl_comment:
                new_col.ddl_comment = ddl_comment
                new_col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.name,
                        category="TYPE",
                        source_type=col.source_type,
                        target_type=target_type,
                        message=f"NUMBER sin precisión → {self._number_fallback}",
                        severity="WARNING",
                    )
                )
            return new_col

        mapping = resolve_oracle_type(oracle_base)

        if mapping is None:
            new_col.target_type = "TEXT"
            new_col.ddl_comment = f"-- AVISO: tipo Oracle '{col.source_type}' desconocido → TEXT"
            new_col.warnings.append(
                MigrationWarning(
                    table=table_name,
                    column=col.name,
                    category="TYPE",
                    source_type=col.source_type,
                    target_type="TEXT",
                    message=f"Tipo Oracle '{col.source_type}' no reconocido; mapeado a TEXT",
                    severity="WARNING",
                )
            )
            return new_col

        # ROWID/UROWID: omitir columna
        if mapping.mariadb_type == "":
            new_col.omit = True
            new_col.target_type = ""
            new_col.ddl_comment = mapping.ddl_comment
            if mapping.warning_msg:
                new_col.warnings.append(
                    MigrationWarning(
                        table=table_name,
                        column=col.name,
                        category="TYPE",
                        source_type=col.source_type,
                        target_type="(omitido)",
                        message=mapping.warning_msg,
                        severity=mapping.severity,
                        proposals=mapping.proposals,
                    )
                )
            return new_col

        target_type = self._build_target_type(mapping.mariadb_type, oracle_base, col)
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

    def _build_target_type(self, mariadb_base: str, oracle_base: str, col: CanonicalColumn) -> str:
        """Construye el tipo MariaDB con parámetros según el tipo Oracle."""
        # Tipos con longitud de carácter
        if oracle_base in ("VARCHAR2", "VARCHAR", "NVARCHAR2", "CHAR", "NCHAR"):
            length = col.char_length or 255
            base = mariadb_base  # "VARCHAR" o "CHAR"
            if oracle_base in _NVARCHAR_CHARSETS:
                return f"{base}({length}) CHARACTER SET utf8mb4"
            return f"{base}({length})"

        # DECIMAL/NUMERIC con precision/scale
        if oracle_base in ("NUMERIC", "DECIMAL"):
            p = col.precision or 18
            s = col.scale or 0
            return f"{mariadb_base}({p},{s})"

        # RAW con longitud
        if oracle_base == "RAW":
            length = col.char_length or 255
            return f"VARBINARY({length})"

        # TIMESTAMP con precision (scale en Oracle): default Oracle = 6 dígitos fraccionarios
        if oracle_base == "TIMESTAMP":
            prec = min(col.scale, 6) if col.scale is not None else 6
            return f"DATETIME({prec})" if prec > 0 else "DATETIME"

        # CLOB/NCLOB con charset
        if oracle_base in _LOB_UTF8:
            return "LONGTEXT CHARACTER SET utf8mb4"

        # Tipos fijos: retornar el mariadb_type directamente
        return self._with_int_width(mariadb_base)

    def _with_int_width(self, type_str: str) -> str:
        """Aplica el display width configurado al tipo INT."""
        if type_str == "INT" and self._int_display_width > 0:
            return f"INT({self._int_display_width})"
        return type_str

    def _handle_pk_auto_increment(self, table: CanonicalTable) -> None:
        """Marca la columna PK única como AUTO_INCREMENT si es tipo entero."""
        if len(table.primary_key) != 1:
            return  # PK compuesta: AUTO_INCREMENT no aplica en MariaDB

        pk_col_name = table.primary_key[0]
        pk_col = next(
            (c for c in table.columns if c.name == pk_col_name and not c.omit),
            None,
        )
        if pk_col is None or pk_col.auto_increment:
            return  # Ya marcada (por NEXTVAL) o columna no encontrada

        base_type = pk_col.target_type.split("(")[0].upper().strip()
        if base_type not in _INT_TYPES_AUTOINCREMENT:
            # NUMBER sin precisión en PK → resolve_number_type devuelve DOUBLE; forzar INT aquí
            # usando table.primary_key como fuente canónica (col.is_primary_key puede no estar seteado)
            oracle_base = pk_col.source_type.upper().split("(")[0].strip()
            if oracle_base != "NUMBER" or pk_col.precision is not None:
                return
            pk_col.target_type = self._with_int_width("INT")
            pk_col.ddl_comment = None
            pk_col.warnings = [w for w in pk_col.warnings if w.severity != "WARNING"]

        pk_col.auto_increment = True
        pk_col.nullable = False  # AUTO_INCREMENT requiere NOT NULL
        table.warnings.append(
            MigrationWarning(
                table=table.name,
                column=pk_col_name,
                category="AUTO_INCREMENT",
                source_type=pk_col.source_type,
                target_type=pk_col.target_type,
                message=f"Columna PK '{pk_col_name}' marcada como AUTO_INCREMENT",
                severity="INFO",
            )
        )

    def _handle_sequence_columns(self, table: CanonicalTable) -> None:
        """Detecta columnas con DEFAULT .NEXTVAL y las convierte a AUTO_INCREMENT."""
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
                        category="AUTO_INCREMENT",
                        target_type="AUTO_INCREMENT",
                        message=(
                            f"Columna '{col.name}' usa secuencia '{seq_name}' pero no es PK; "
                            "AUTO_INCREMENT requiere PK en MariaDB — se añade como PK automáticamente"
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
                        category="AUTO_INCREMENT",
                        target_type="AUTO_INCREMENT",
                        message=f"Secuencia Oracle '{seq_name}' convertida a AUTO_INCREMENT",
                        severity="INFO",
                    )
                )


def _detect_sequence(default: str | None) -> str | None:
    """Retorna el nombre de la secuencia si el default contiene .NEXTVAL."""
    if not default:
        return None
    m = _NEXTVAL_RE.search(default)
    return m.group(1) if m else None


__all__: list[str] = ["OracleToMariaDBTransformer"]
