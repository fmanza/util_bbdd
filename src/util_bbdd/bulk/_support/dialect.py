"""Constantes de dialecto compartidas por ``bulk`` y ``dump``."""

from __future__ import annotations

# Dialectos de SQLAlchemy de la familia MySQL: comparten SQL de sesión (FOREIGN_KEY_CHECKS), casing de identificadores
# y estrategias de carga.
MYSQL_FAMILY: frozenset[str] = frozenset({"mysql", "mariadb"})

__all__: list[str] = ["MYSQL_FAMILY"]
