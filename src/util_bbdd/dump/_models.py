"""Tipos de datos públicos del módulo dump.

Separados en un módulo propio para romper la dependencia circular entre
``orchestrator`` y ``reporters``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import Engine


@dataclass
class ConstraintResult:
    """Resultado de rehabilitar una constraint individual en el destino."""

    table_name: str
    constraint_name: str
    dialect: str
    status: Literal["enabled", "failed", "unverified"]
    error_msg: str = ""


@dataclass
class DumpConfig:
    """Configuración de un volcado de datos de esquema/BD origen a destino.

    Args:
        source_engine: Engine SQLAlchemy del esquema origen (lectura).
        target_engine: Engine SQLAlchemy del esquema destino (escritura).
            **Recomendación para MariaDB/MySQL:** crear con ``pool_pre_ping=True`` y
            ``pool_recycle=3600`` para evitar ``InterfaceError: Server has gone away``
            cuando el pool reutiliza conexiones ociosas entre tablas::

                target_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)

        source_schema: Nombre del schema origen; ``None`` usa el default del engine.
        target_schema: Nombre del schema destino; ``None`` usa el default del engine.
        tables: Tablas a volcar. ``None`` = todas las tablas del origen.
        chunk_size: Filas por chunk. Se aplica en dos niveles: (1) lectura origen
            vía ``pd.read_sql(chunksize=chunk_size)`` y (2) inserción destino en
            ``BulkCrud(chunk_size=chunk_size)``. Ambos reciben el mismo valor.
        output_dir: Directorio donde guardar el informe Excel.
        truncate_target: ``True`` (default) = limpiar tablas destino antes de cargar.
            Recomendado para volcados completos. ``False`` = modo append.
        bulk_audit_path: Ruta del CSV de auditoría para los inserts en destino.
            ``None`` (default) = los inserts no se registran en auditoría.
    """

    source_engine: Engine
    target_engine: Engine
    source_schema: str | None = None
    target_schema: str | None = None
    tables: list[str] | None = None
    chunk_size: int = 5000
    output_dir: Path = field(default_factory=Path)
    truncate_target: bool = True
    bulk_audit_path: Path | None = None


@dataclass
class TableDumpResult:
    """Resultado del volcado de una tabla individual."""

    table_name: str
    source_rows: int
    target_rows_before: int
    target_rows_after: int
    status: Literal["success", "missing_target", "skipped", "error"]
    skipped_columns: list[str]
    load_order_position: int
    in_cycle: bool = False
    error_msg: str = ""


@dataclass
class DumpResult:
    """Resultado completo de un volcado.

    Attributes:
        table_results: Resultado por tabla volcada (o intentada).
        constraint_results: Resultado por constraint al rehabilitar.
        load_order: Orden topológico de carga aplicado.
        cycles_detected: Grupos de tablas con FK circular (cargadas al final).
        report: Ruta del informe Excel generado (3 hojas).
    """

    table_results: list[TableDumpResult]
    constraint_results: list[ConstraintResult]
    load_order: list[str]
    cycles_detected: list[list[str]]
    report: Path
