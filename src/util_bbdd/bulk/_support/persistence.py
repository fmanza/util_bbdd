"""Helpers internos de persistencia para bulk_crud."""

from __future__ import annotations

import logging

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .._audit.errors import AuditError
from .._audit.record import AuditRecord
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
    """Orquesta persistencia de ficheros SQL y auditoría de operaciones bulk.

    Auditoría (M-1 y M-2, audit-code de AuditManager 2026-09-25):

    - Fuera de ``BulkCrud.bulk_session`` cada operación se escribe al terminar, cuando su transacción ya se confirmó.
    - Dentro de la sesión se acumula y se escribe cuando un commit la confirma; si la sesión acaba en rollback se
      descarta con un WARNING. Las filas de SQL generado (``generar_sql=True``) no dependen de la transacción y se
      escriben al momento.
    - Si falla la escritura, con ``audit_strict=False`` (por defecto) se registra un ERROR con los datos perdidos, se
      suman a ``audit_failures`` y la operación sigue: ya se aplicó y relanzar invitaría a reintentarla y duplicarla.
      Con ``audit_strict=True`` se propaga; dentro de la sesión se escribe **antes** del commit para que el fallo la
      deshaga.
    """

    engine_url: str
    logger: logging.Logger
    audit_manager: AuditManager
    db_info: str
    audit_strict: bool = False
    audit_failures: int = field(default=0, init=False)
    _session_connection: Any | None = field(default=None, init=False, repr=False)
    _pending: list[AuditRecord] = field(default_factory=list, init=False, repr=False)

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
        if self._session_connection is None or generated_sql or self.audit_manager.audit_csv_path is None:
            try:
                self.audit_manager.registrar_operacion(
                    table_name,
                    self.db_info,
                    operation,
                    rowcount,
                    elapsed,
                    generated_sql,
                )
            except (AuditError, OSError) as error:
                if self.audit_strict:
                    raise
                self._report_audit_failure(
                    error,
                    [AuditRecord(table_name, self.db_info, operation, rowcount, elapsed, generated_sql)],
                )
            return

        self._pending.append(AuditRecord(table_name, self.db_info, operation, rowcount, elapsed, generated_sql))
        if not self._session_connection.in_transaction():
            # commit_every_n_chunks: el último commit periódico ya confirmó la operación entera.
            self._flush_audit()

    def start_session_audit(self, connection: Any) -> None:
        """Empieza a acumular la auditoría de las operaciones que se ejecuten sobre ``connection``."""
        self._session_connection = connection
        self._pending = []

    def commit(self, connection: Any) -> None:
        """Confirma ``connection`` y escribe la auditoría que ese commit confirma."""
        self.flush_audit_before_commit()
        connection.commit()
        self.flush_audit_after_commit()

    def flush_audit_before_commit(self) -> None:
        """Con ``audit_strict``, escribe la auditoría acumulada antes del commit: si falla, la sesión se deshace."""
        if self.audit_strict:
            self._flush_audit()

    def flush_audit_after_commit(self) -> None:
        """Sin ``audit_strict``, escribe la auditoría acumulada una vez confirmada la transacción."""
        if not self.audit_strict:
            self._flush_audit()

    def end_session_audit(self) -> None:
        """Cierra la sesión; lo que siga pendiente no llegó a confirmarse y se descarta."""
        pending, self._pending = self._pending, []
        self._session_connection = None
        if pending:
            self.logger.warning(
                f"⚠️ Auditoría: se descartan {len(pending)} registros ({sum(r.rowcount for r in pending)} filas) "
                "porque la sesión terminó sin confirmarlos (rollback)."
            )

    def _flush_audit(self) -> None:
        """Escribe los registros pendientes con una sola apertura del CSV."""
        if not self._pending:
            return
        pending, self._pending = self._pending, []
        try:
            self.audit_manager._registrar_lote(pending)
        except (AuditError, OSError) as error:
            if self.audit_strict:
                self.logger.error(f"❌ Error escribiendo la auditoría de la sesión bulk: {error}")
                raise
            self._report_audit_failure(error, pending)

    def _report_audit_failure(self, error: Exception, registros: Sequence[AuditRecord]) -> None:
        """Fail-open: deja en el log lo que no pudo escribirse y lo cuenta en ``audit_failures``."""
        self.audit_failures += len(registros)
        detalle = "; ".join(
            f"{r.timestamp:%Y-%m-%d %H:%M:%S} {r.operacion} {r.tabla} filas={r.rowcount} "
            f"tiempo={r.elapsed:.3f}s sql={'Sí' if r.genero_sql else 'No'}"
            for r in registros
        )
        self.logger.error(
            f"❌ No se pudo escribir la auditoría ({type(error).__name__}: {error}). La operación sí se aplicó. "
            f"Registros perdidos ({len(registros)}): {detalle}"
        )


__all__: list[str] = ["BulkPersistenceManager"]
