"""Parser de charset/collation y normalización de DDL (patrón: Strategy + Transformer)."""

from __future__ import annotations

import logging
import re

from typing import Any

ColumnCharsetCollationRow = tuple[str, str | None, str | None]


class DDLNormalizer:
    """Normalizador de DDL Oracle y helpers genéricos (patrón: Transformer).

    Encapsula la lógica de detección y lectura de LOB, extracción de DDL
    y normalización de resultados heterogéneos de consultas DDL.
    """

    @staticmethod
    def is_lob(value: Any) -> bool:
        """Indica si el valor expone API de lectura tipo LOB.

        Args:
            value: Valor a verificar

        Returns:
            bool: True si tiene método `read()` callable
        """
        return hasattr(value, "read") and callable(value.read)

    @staticmethod
    def read_lob(value: Any) -> str:
        """Lee de forma segura un valor tipo LOB.

        Args:
            value: Valor LOB a leer

        Returns:
            str: Contenido leído o string del valor
        """
        try:
            return str(value.read())
        except Exception:
            return str(value)

    @staticmethod
    def contains_create(text: str) -> bool:
        """Indica si el texto contiene una sentencia CREATE.

        Args:
            text: Texto a verificar

        Returns:
            bool: True si contiene "CREATE"
        """
        return "CREATE " in text.upper()

    @staticmethod
    def _extract_preferred_ddl_candidate(value: Any) -> str:
        """Extrae DDL preferida de un valor (interno).

        Busca en orden: CREATE statement, texto anidado, string del valor.

        Args:
            value: Valor de candidato

        Returns:
            str: DDL encontrada o string vacío
        """
        if value is None:
            return ""

        if DDLNormalizer.is_lob(value):
            value = DDLNormalizer.read_lob(value)

        if isinstance(value, (tuple, list)):
            nested_text = DDLNormalizer.normalize_result(value)
            if DDLNormalizer.contains_create(nested_text):
                return nested_text
            if nested_text.strip():
                return nested_text
            return ""

        text = str(value)
        if DDLNormalizer.contains_create(text):
            return text

        return ""

    @staticmethod
    def _extract_any_text(value: Any) -> str:
        """Extrae texto de cualquier tipo de valor (interno).

        Args:
            value: Valor a extraer

        Returns:
            str: Texto extraído o string vacío
        """
        if value is None:
            return ""

        if DDLNormalizer.is_lob(value):
            return DDLNormalizer.read_lob(value)

        if isinstance(value, (tuple, list)):
            return DDLNormalizer.normalize_result(value)

        text = str(value)
        return text if text.strip() else ""

    @staticmethod
    def normalize_result(ddl: Any) -> str:
        """Normaliza resultados heterogéneos de consultas DDL a texto.

        Busca en orden: LOB, CREATE statement en posiciones prioritarias (2, 1, 0),
        primer texto no vacío.

        Args:
            ddl: Resultado de consulta DDL (string, LOB, tuple, list, etc.)

        Returns:
            str: DDL normalizado o string vacío
        """
        if ddl is None:
            return ""

        if isinstance(ddl, str):
            return ddl

        if DDLNormalizer.is_lob(ddl):
            return DDLNormalizer.read_lob(ddl)

        if not isinstance(ddl, (tuple, list)):
            return str(ddl)

        # Buscar en posiciones prioritarias (2, 1, 0)
        for pos in (2, 1, 0):
            if len(ddl) <= pos:
                continue
            candidate: str = DDLNormalizer._extract_preferred_ddl_candidate(ddl[pos])
            if candidate:
                return candidate

        # Fallback: primer texto no vacío
        for value in ddl:
            text: str = DDLNormalizer._extract_any_text(value)
            if text:
                return text

        return ""


class CharsetCollationParser:
    """Parser de charset/collation por tipo de BD (patrón: Strategy).

    Centraliza la lógica de parsing de charset/collation que varía por motor,
    con logging consistente para auditoría.
    """

    def __init__(self, logger: logging.Logger):
        """Inicializa el parser con logger.

        Args:
            logger: Logger para auditoría de parsing
        """
        self.logger: logging.Logger = logger
        self._db_charset_parsers = {
            "oracle": self._parse_db_charset_oracle,
            "postgresql": self._parse_db_charset_postgresql,
            "mariadb": self._parse_db_charset_mariadb,
            "mysql": self._parse_db_charset_mariadb,
            "sqlserver": lambda row: self._parse_db_charset_single_field(row, "collation"),
            "hsqldb": lambda row: self._parse_db_charset_single_field(row, "collation"),
            "sqlite": lambda row: self._parse_db_charset_single_field(row, "encoding"),
        }
        self._column_charset_parsers = {
            "oracle": self._parse_column_charset_collation_collation_only,
            "postgresql": self._parse_column_charset_collation_collation_only,
            "sqlserver": self._parse_column_charset_collation_collation_only,
            "hsqldb": self._parse_column_charset_collation_collation_only,
            "sqlite": self._parse_column_charset_collation_empty,
            "mariadb": self._parse_column_charset_collation_mariadb,
            "mysql": self._parse_column_charset_collation_mariadb,
        }

    def parse_db_charset(self, db_type: str, result: tuple[Any, ...] | None) -> dict[str, Any]:
        """Parsea resultado de charset/collation de base de datos según motor.

        Args:
            db_type: Tipo de base de datos
            result: Tupla con resultado de charset

        Returns:
            dict[str, Any]: Diccionario de charset/collation o {}
        """
        if not result:
            self.logger.debug(f"[{db_type}] Empty charset result")
            return {}

        parser = self._db_charset_parsers.get(db_type)
        if not parser:
            self.logger.warning(f"[{db_type}] No charset parser found, returning empty dict")
            return {}

        try:
            parsed = parser(result)
            self.logger.debug(f"[{db_type}] Parsed charset: {parsed}")
            return parsed
        except Exception as error:
            self.logger.error(f"[{db_type}] Error parsing charset: {error}", exc_info=True)
            return {}

    def parse_column_charset_collation(self, db_type: str, row: tuple[Any, ...]) -> ColumnCharsetCollationRow:
        """Parsea una fila de charset/collation por columna según motor.

        Args:
            db_type: Tipo de base de datos
            row: Tupla con fila de resultado

        Returns:
            ColumnCharsetCollationRow: (column_name, charset, collation)
        """
        column_name: str = str(row[0]) if len(row) > 0 else ""

        parser = self._column_charset_parsers.get(db_type)
        if not parser:
            self.logger.debug(f"[{db_type}] No column charset parser, returning empty")
            return (column_name, None, None)

        try:
            parsed = parser(row, column_name)
            self.logger.debug(f"[{db_type}] Parsed column charset: {parsed}")
            return parsed
        except Exception as error:
            self.logger.error(f"[{db_type}] Error parsing column charset: {error}", exc_info=True)
            return (column_name, None, None)

    def supports_charset_collation(self, db_type: str, oracle_version_text: str | None = None) -> bool:
        """Indica si el motor soporta metadata fiable de charset/collation por columna.

        Args:
            db_type: Tipo de base de datos
            oracle_version_text: Texto de versión de Oracle (si aplica)

        Returns:
            bool: True si soporta
        """
        if db_type == "oracle":
            result: bool
            if not oracle_version_text:
                result = False
            else:
                result = self._oracle_supports_columns_charset_collation(oracle_version_text)
            self.logger.debug(f"[oracle] supports_charset_collation: {result}")
            return result

        result = db_type != "sqlite"
        self.logger.debug(f"[{db_type}] supports_charset_collation: {result}")
        return result

    # Internal parsers (static, no logging needed)
    @staticmethod
    def _parse_db_charset_oracle(result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea charset de Oracle."""
        if not result:
            return {}
        charset: str = str(result[0])
        if len(result) > 1:
            return {"charset": charset, "nchar_charset": str(result[1])}
        return {"charset": charset}

    @staticmethod
    def _parse_db_charset_postgresql(result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea charset de PostgreSQL."""
        if len(result) > 2:
            return {"encoding": str(result[0]), "collate": str(result[1]), "ctype": str(result[2])}
        if len(result) > 0:
            return {"encoding": str(result[0])}
        return {}

    @staticmethod
    def _parse_db_charset_mariadb(result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea charset de MariaDB (delegado a módulo específico)."""
        from ..metadata.mariadb import parse_mariadb_db_charset

        return parse_mariadb_db_charset(result)

    @staticmethod
    def _parse_db_charset_single_field(result: tuple[Any, ...], field_name: str) -> dict[str, Any]:
        """Parsea charset de un único campo."""
        if len(result) == 0:
            return {}
        return {field_name: str(result[0])}

    @staticmethod
    def _parse_column_charset_collation_collation_only(
        row: tuple[Any, ...], column_name: str
    ) -> ColumnCharsetCollationRow:
        """Parsea columna con solo collation (Oracle, PostgreSQL, SQL Server, HSQLDB)."""
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, None, collation)

    @staticmethod
    def _parse_column_charset_collation_empty(_row: tuple[Any, ...], column_name: str) -> ColumnCharsetCollationRow:
        """Parsea columna sin soporte de charset/collation (SQLite)."""
        return (column_name, None, None)

    @staticmethod
    def _parse_column_charset_collation_mariadb(row: tuple[Any, ...], column_name: str) -> ColumnCharsetCollationRow:
        """Parsea columna MariaDB que expone charset (col 1) y collation (col 2)."""
        charset: str | None = str(row[1]) if len(row) > 1 else None
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, charset, collation)

    @staticmethod
    def _oracle_supports_columns_charset_collation(version_text: str) -> bool:
        """Evalúa si una versión Oracle soporta collation por columna."""
        version_match: re.Match[str] | None = re.search(r"Release\s+(\d+)\.(\d+)", version_text)
        if version_match is None:
            return False
        major = int(version_match.group(1))
        minor = int(version_match.group(2))
        return (major, minor) >= (12, 2)


__all__: list[str] = [
    "DDLNormalizer",
    "CharsetCollationParser",
    "ColumnCharsetCollationRow",
]
