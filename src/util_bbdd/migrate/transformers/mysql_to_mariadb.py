"""Transformer MySQL → MariaDB.

Responsabilidades:
  - Conservar el tipo completo de MySQL (``COLUMN_TYPE``); MariaDB comparte su sintaxis de tipos (``JSON`` es un
    alias de ``LONGTEXT`` con validación en MariaDB).
  - Verificar identificadores (máximo 64 caracteres en ambos motores).
  - Vistas y rutinas: pass-through v1 con aviso de revisión manual.
"""

from __future__ import annotations

from typing import ClassVar

from ._mysql_family import MySQLFamilyTransformer


class MySQLToMariaDBTransformer(MySQLFamilyTransformer):
    """Transforma IR MySQL (extraído con tipo completo) a IR MariaDB."""

    _TARGET_DIALECT = "MariaDB"
    _SOURCE_DIALECT: ClassVar[str] = "MySQL"


__all__: list[str] = ["MySQLToMariaDBTransformer"]
