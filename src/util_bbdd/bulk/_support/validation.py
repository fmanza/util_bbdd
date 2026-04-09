"""Helpers internos de validación y preparación para bulk_crud."""

from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sqlalchemy import Engine, Table


@dataclass(frozen=True)
class UpdatePlan:
    """Estructura con las columnas válidas para un UPDATE en lote."""

    pk_cols: list[str]
    update_cols: list[str]
    pk_param_map: dict[str, str]


def validate_engine(engine: Engine | None) -> Engine:
    """Valida que exista un engine SQLAlchemy inicializado."""
    if engine is None:
        raise ValueError("❌ 'engine' no puede ser None")
    return engine


def resolve_sql_output_path(
    path_sql: Path | None,
    *,
    table_name: str,
    operation: str,
    generate_name: Callable[[str, str], Path],
) -> Path:
    """Valida el directorio de salida y le añade el nombre SQL generado."""
    if path_sql is None:
        raise ValueError("❌ path_sql es obligatorio cuando generar_sql=True")
    if not isinstance(path_sql, Path):
        raise ValueError(f"❌ path_sql debe ser una instancia de Path, se recibió {type(path_sql).__name__}")
    return path_sql / generate_name(table_name, operation)


def normalize_dataframe_columns(df: pd.DataFrame, dialect_name: str, logger: logging.Logger) -> None:
    """Normaliza el casing de columnas de entrada según el dialecto."""
    if dialect_name in ("oracle", "postgresql", "sqlite"):
        df.columns = df.columns.str.lower()
    elif dialect_name in ("mysql", "mariadb", "mssql", "hsqldb"):
        df.columns = df.columns.str.upper()
    else:
        logger.warning(f"⚠️ Dialecto no reconocido: {dialect_name}")


def get_insert_columns(df_columns: Sequence[str], table: Table) -> list[str]:
    """Obtiene columnas del DataFrame que existen en la tabla destino."""
    table_columns: set[str] = {column.name for column in table.columns}
    return [column for column in df_columns if column in table_columns]


def get_pk_columns(table: Table, df_columns: Sequence[str]) -> list[str]:
    """Devuelve las claves primarias presentes en el DataFrame."""
    pk_cols: list[str] = [column.name for column in table.primary_key.columns if column.name in df_columns]
    if not pk_cols:
        raise ValueError("❌ La tabla no tiene claves primarias presentes en el DataFrame.")
    return pk_cols


def build_update_plan(table: Table, df_columns: Sequence[str], table_name: str) -> UpdatePlan:
    """Valida y prepara las columnas necesarias para un UPDATE en lote."""
    table_columns: set[str] = {column.name for column in table.columns}
    pk_cols: list[str] = [column.name for column in table.primary_key.columns if column.name in df_columns]
    if not pk_cols:
        raise ValueError(f"❌ La tabla '{table_name}' no tiene claves primarias presentes en el DataFrame.")

    update_cols: list[str] = [column for column in df_columns if column in table_columns and column not in pk_cols]
    if not update_cols:
        raise ValueError("❌ No hay columnas actualizables válidas.")

    return UpdatePlan(
        pk_cols=pk_cols,
        update_cols=update_cols,
        pk_param_map={column: f"pk_{column}" for column in pk_cols},
    )


__all__: list[str] = [
    "UpdatePlan",
    "build_update_plan",
    "get_insert_columns",
    "get_pk_columns",
    "normalize_dataframe_columns",
    "resolve_sql_output_path",
    "validate_engine",
]
