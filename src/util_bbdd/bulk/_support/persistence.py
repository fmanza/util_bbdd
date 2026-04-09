"""Helpers internos de persistencia para bulk_crud."""

from __future__ import annotations

import logging

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..audit import AuditManager
from .sql_helpers import generate_sql_filename
from .validation import resolve_sql_output_path


@dataclass(slots=True)
class BulkPersistenceManager:
    """Orquesta persistencia de ficheros SQL y auditoría de operaciones bulk."""

    engine_url: str
    logger: logging.Logger
    audit_manager: AuditManager
    db_info: str

    def build_sql_filename(self, table: str, operation: str) -> Path:
        """Genera el nombre dinámico del fichero SQL para una operación bulk."""
        sql_filename = generate_sql_filename(engine_url=self.engine_url, table=table, operation=operation)
        self.logger.debug(f"🟢 Nombre SQL generado: {sql_filename}")
        return sql_filename

    def resolve_sql_output_path(self, path_sql: Path | None, table_name: str, operation: str) -> Path:
        """Resuelve la ruta completa de salida para el fichero SQL generado."""
        output_path = resolve_sql_output_path(
            path_sql,
            table_name=table_name,
            operation=operation,
            generate_name=self.build_sql_filename,
        )
        self.logger.debug(f"📄 Path SQL generado: {output_path}")
        return output_path

    def persist_sql(self, sql_lines: Sequence[str], file_path: Path | None) -> None:
        """Persiste las sentencias SQL en fichero o las emite al log."""
        sql_output: str = "\n".join(sql_lines)
        if file_path is not None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(sql_output, encoding="utf-8")
            self.logger.info(f"💾 SQL guardada en: {file_path}")
            return

        self.logger.info(sql_output)
        self.logger.info("📄 SQL generada en log.")

    def register_operation(
        self,
        *,
        table_name: str,
        operation: str,
        rowcount: int,
        elapsed: float,
        generated_sql: bool,
    ) -> None:
        """Registra el resultado de una operación bulk en el subsistema de auditoría."""
        self.audit_manager.registrar_operacion(
            table_name,
            self.db_info,
            operation,
            rowcount,
            elapsed,
            generated_sql,
        )


__all__: list[str] = ["BulkPersistenceManager"]
