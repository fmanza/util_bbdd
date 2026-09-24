"""Helpers internos de persistencia para bulk_crud."""

from __future__ import annotations

import logging

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ..audit import AuditManager
from .sql_helpers import generate_sql_filename
from .validation import resolve_sql_output_path


def _joined_lines(lines: Iterable[str]) -> Iterator[str]:
    """Las líneas separadas por ``\\n`` y sin salto final, como ``"\\n".join(lines)``, sin construir la cadena."""
    separator = ""
    for line in lines:
        yield separator
        yield line
        separator = "\n"


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

    def persist_sql(self, sql_lines: Iterable[str], file_path: Path | None) -> None:
        """Persiste las sentencias SQL en fichero o las emite al log.

        P-07 (performance-audit de bulk): el fichero se escribe a medida que se generan las líneas, sin unirlas antes en
        memoria, en un temporal que se renombra al terminar: si la generación falla no queda un fichero a medias. El
        contenido es el mismo que ``"\\n".join(sql_lines)`` escrito en modo texto.
        """
        if file_path is None:
            self.logger.info("\n".join(sql_lines))
            self.logger.info("📄 SQL generada en log.")
            return

        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path = file_path.with_name(f"{file_path.name}.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                handle.writelines(_joined_lines(sql_lines))
            tmp_path.replace(file_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        self.logger.info(f"💾 SQL guardada en: {file_path}")

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
