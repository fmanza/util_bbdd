"""Modelos de datos internos para SQLite.

Dataclasses para representar resultados de PRAGMA queries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SqlitePragmaResult:
    """Resultado de PRAGMA table_info(table_name).

    Atributos:
        cid: Column ID (ordinal position)
        name: Nombre de la columna
        type_name: Tipo de dato de la columna
        notnull: 1 si NOT NULL, 0 si nullable
        default_value: Valor default (NULL si no especificado)
        pk: 1 si forma parte de PRIMARY KEY, 0 en otro caso
    """

    cid: int
    name: str
    type_name: str
    notnull: int
    default_value: str | None
    pk: int
