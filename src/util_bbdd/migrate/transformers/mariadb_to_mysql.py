"""Transformer MariaDB → MySQL.

Responsabilidades:
  - Conservar el tipo completo de MariaDB (``COLUMN_TYPE``); MySQL 8 comparte su sintaxis de tipos.
  - Sustituir los tipos exclusivos de MariaDB: ``UUID`` → ``CHAR(36)``, ``INET4`` → ``VARCHAR(15)``,
    ``INET6`` → ``VARCHAR(39)`` (con ``MigrationWarning``).
  - Verificar identificadores (máximo 64 caracteres en ambos motores).
  - Vistas y rutinas: pass-through v1 con aviso de revisión manual.
"""

from __future__ import annotations

from typing import ClassVar

from ._mysql_family import MySQLFamilyTransformer


class MariaDBToMySQLTransformer(MySQLFamilyTransformer):
    """Transforma IR MariaDB (extraído con tipo completo) a IR MySQL."""

    _TARGET_DIALECT = "MySQL"
    _SOURCE_DIALECT: ClassVar[str] = "MariaDB"
    _TYPE_OVERRIDES: ClassVar[dict[str, str]] = {
        "UUID": "CHAR(36)",
        "INET4": "VARCHAR(15)",
        "INET6": "VARCHAR(39)",
    }


__all__: list[str] = ["MariaDBToMySQLTransformer"]
