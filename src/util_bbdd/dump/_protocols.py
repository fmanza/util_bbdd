"""Protocolos estructurales del módulo dump.

Definen los contratos mínimos que deben satisfacer los colaboradores externos
sin acoplar el módulo a implementaciones concretas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:
    from pathlib import Path


@runtime_checkable
class BulkInserter(Protocol):
    """Contrato mínimo de inserción en lote requerido por ``DumpOrchestrator``.

    Cualquier objeto que exponga ``bulk_insert_from_df`` con esta firma puede
    usarse como colaborador de inserción, sin necesidad de heredar de ``BulkCrud``.
    """

    def bulk_insert_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> None: ...
