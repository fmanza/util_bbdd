"""Helpers internos de persistencia para bulk_crud."""

from __future__ import annotations

import logging
import time

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .._audit.errors import AuditError
from .._audit.record import AuditRecord
from ..audit import AuditManager
from .sql_helpers import generate_sql_filename
from .validation import resolve_sql_output_path

# M-5 (audit-code de ParallelBulkLoader 2026-09-25): con ``commit_every_n_chunks`` lo ya confirmado se escribe por
# tandas y no en cada commit. Si el proceso muere de golpe, se pierden como mucho estos registros ya confirmados.
_CONFIRMED_FLUSH_RECORDS: int = 64
_CONFIRMED_FLUSH_SECONDS: float = 1.0


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

    Auditoría (M-1 y M-2 del audit-code de AuditManager; M-1, M-2, M-3 y M-5 del audit-code de ``ParallelBulkLoader``,
    ambos del 2026-09-25):

    - Fuera de ``BulkCrud.bulk_session`` cada operación se escribe al terminar, cuando su transacción ya se confirmó.
    - Dentro de la sesión se acumula y se escribe cuando un commit la confirma; si la sesión acaba en rollback se
      descarta con un WARNING. Las filas de SQL generado (``generar_sql=True``) no dependen de la transacción y se
      escriben al momento.
    - Con ``commit_every_n_chunks`` lo que confirman los commits periódicos se agrupa y se escribe por tandas (64
      registros o 1 s) y siempre al cerrar la sesión, con o sin error.
    - Si falla la escritura, con ``audit_strict=False`` (por defecto) se registra un ERROR con los datos perdidos, se
      suman a ``audit_failures`` y la operación sigue: ya se aplicó y relanzar invitaría a reintentarla y duplicarla.
      Con ``audit_strict=True`` se propaga; dentro de la sesión se escribe **antes** del commit para que el fallo la
      deshaga. Si lo que falla es ese commit, lo escrito queda en el CSV sin datos en la BD: se registra un ERROR y se
      cuenta en ``audit_uncommitted_records``.

    Contadores (acumulan durante toda la vida de la instancia):

    - ``audit_failures``: registros que no se pudieron escribir en el CSV.
    - ``audited_rows``: filas (``rowcount``) de los registros escritos en el CSV.
    - ``audit_uncommitted_records``: registros escritos antes de un commit que falló (solo con ``audit_strict``).
    - ``unaudited_committed_rows``: filas que un commit periódico confirmó pero que no constan en el CSV porque su
      operación falló o no llegó a confirmarse entera antes del fallo de la sesión.
    """

    engine_url: str
    logger: logging.Logger
    audit_manager: AuditManager
    db_info: str
    audit_strict: bool = False
    audit_failures: int = field(default=0, init=False)
    audited_rows: int = field(default=0, init=False)
    audit_uncommitted_records: int = field(default=0, init=False)
    unaudited_committed_rows: int = field(default=0, init=False)
    _session_connection: Any | None = field(default=None, init=False, repr=False)
    # Operaciones de la sesión aún sin confirmar.
    _pending: list[AuditRecord] = field(default_factory=list, init=False, repr=False)
    # Operaciones ya confirmadas que esperan a la siguiente tanda (solo sin audit_strict).
    _confirmed: list[AuditRecord] = field(default_factory=list, init=False, repr=False)
    _last_confirmed_write: float = field(default=0.0, init=False, repr=False)
    # Con audit_strict: registros escritos antes de un commit que todavía no ha terminado bien.
    _written_uncommitted: list[AuditRecord] = field(default_factory=list, init=False, repr=False)
    # Filas de INSERT/UPDATE confirmadas en la sesión; se comparan con rows_committed del ejecutor.
    _session_confirmed_rows: int = field(default=0, init=False, repr=False)

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
            if self.audit_manager.audit_csv_path is not None:
                self.audited_rows += rowcount
            return

        record = AuditRecord(table_name, self.db_info, operation, rowcount, elapsed, generated_sql)
        if self._session_connection.in_transaction():
            self._pending.append(record)
            return
        # commit_every_n_chunks: el último commit periódico ya confirmó la operación entera.
        self._session_confirmed_rows += _dml_rows([record])
        if self.audit_strict:
            self._write([record])
        else:
            self._confirmed.append(record)
            self._write_confirmed(force=False)

    def start_session_audit(self, connection: Any) -> None:
        """Empieza a acumular la auditoría de las operaciones que se ejecuten sobre ``connection``."""
        self._session_connection = connection
        self._pending = []
        self._confirmed = []
        self._written_uncommitted = []
        self._session_confirmed_rows = 0
        self._last_confirmed_write = time.monotonic()

    def commit(self, connection: Any) -> None:
        """Commit periódico de la sesión: confirma ``connection`` y da por confirmada la auditoría acumulada."""
        self.flush_audit_before_commit()
        connection.commit()
        self.flush_audit_after_commit(final=False)

    def flush_audit_before_commit(self) -> None:
        """Con ``audit_strict``, escribe la auditoría acumulada antes del commit: si falla, la sesión se deshace."""
        if not self.audit_strict or not self._pending:
            return
        pending, self._pending = self._pending, []
        self._write(pending)
        self._written_uncommitted.extend(pending)

    def flush_audit_after_commit(self, *, final: bool = True) -> None:
        """Llamar justo después de un commit correcto: da por confirmado lo acumulado.

        Sin ``audit_strict`` lo pasa a la tanda de confirmados, que se escribe entera si ``final`` (último commit de la
        sesión) o si llega al umbral. Con ``audit_strict`` ya se escribió antes del commit.
        """
        self._session_confirmed_rows += _dml_rows(self._written_uncommitted)
        self._written_uncommitted = []
        if self.audit_strict:
            return
        self._session_confirmed_rows += _dml_rows(self._pending)
        self._confirmed.extend(self._pending)
        self._pending = []
        self._write_confirmed(force=final)

    def end_session_audit(self, *, committed_rows: int | None = None) -> None:
        """Cierra la sesión: escribe lo confirmado y descarta lo que no llegó a confirmarse.

        Args:
            committed_rows: Solo cuando la sesión falla con ``commit_every_n_chunks``: filas que confirmaron sus
                commits periódicos (``rows_committed`` del ejecutor). Sirve para contar las que no constan en el CSV.
        """
        try:
            self._write_confirmed(force=True)
        finally:
            pending, self._pending = self._pending, []
            written_uncommitted, self._written_uncommitted = self._written_uncommitted, []
            confirmed_rows, self._session_confirmed_rows = self._session_confirmed_rows, 0
            self._session_connection = None
            self._report_written_uncommitted(written_uncommitted)
            unaudited = 0
            if committed_rows is not None and self.audit_manager.audit_csv_path is not None:
                unaudited = max(0, committed_rows - confirmed_rows)
                self.unaudited_committed_rows += unaudited
            self._report_discarded(pending, unaudited)

    def _report_written_uncommitted(self, registros: Sequence[AuditRecord]) -> None:
        """Strict: lo escrito antes de un commit que falló está en el CSV pero no en la BD."""
        if not registros:
            return
        self.audit_uncommitted_records += len(registros)
        self.logger.error(
            f"❌ Auditoría: {len(registros)} registros ({sum(r.rowcount for r in registros)} filas) se escribieron en "
            f"el CSV antes de un commit que falló; esas filas no están en la BD: {_describe(registros)}"
        )

    def _report_discarded(self, pending: Sequence[AuditRecord], unaudited: int) -> None:
        """WARNING de lo descartado en rollback y de las filas confirmadas que no constan en el CSV."""
        if pending:
            motivo = "sin confirmarlos (rollback)" if unaudited == 0 else "sin confirmarlos enteros (rollback)"
            self.logger.warning(
                f"⚠️ Auditoría: se descartan {len(pending)} registros ({sum(r.rowcount for r in pending)} filas) "
                f"porque la sesión terminó {motivo}."
            )
        if unaudited:
            self.logger.warning(
                f"⚠️ Auditoría: {unaudited} filas confirmadas por commits periódicos no constan en el CSV: su "
                "operación falló o no llegó a confirmarse entera. Ver rows_committed y unaudited_committed_rows."
            )

    def _write_confirmed(self, *, force: bool) -> None:
        """Escribe la tanda de confirmados si ``force`` o si llega al umbral de registros o de tiempo."""
        if not self._confirmed:
            return
        if (
            not force
            and len(self._confirmed) < _CONFIRMED_FLUSH_RECORDS
            and time.monotonic() - self._last_confirmed_write < _CONFIRMED_FLUSH_SECONDS
        ):
            return
        confirmed, self._confirmed = self._confirmed, []
        self._last_confirmed_write = time.monotonic()
        self._write(confirmed)

    def _write(self, registros: list[AuditRecord]) -> None:
        """Escribe ``registros`` con una sola apertura del CSV y aplica la política de fallo."""
        if not registros:
            return
        try:
            self.audit_manager._registrar_lote(registros)
        except (AuditError, OSError) as error:
            if self.audit_strict:
                self.logger.error(f"❌ Error escribiendo la auditoría de la sesión bulk: {error}")
                raise
            self._report_audit_failure(error, registros)
            return
        if self.audit_manager.audit_csv_path is not None:
            self.audited_rows += sum(r.rowcount for r in registros)

    def _report_audit_failure(self, error: Exception, registros: Sequence[AuditRecord]) -> None:
        """Fail-open: deja en el log lo que no pudo escribirse y lo cuenta en ``audit_failures``."""
        self.audit_failures += len(registros)
        self.logger.error(
            f"❌ No se pudo escribir la auditoría ({type(error).__name__}: {error}). La operación sí se aplicó. "
            f"Registros perdidos ({len(registros)}): {_describe(registros)}"
        )


def _describe(registros: Sequence[AuditRecord]) -> str:
    """Resumen legible de los registros para el log."""
    return "; ".join(
        f"{r.timestamp:%Y-%m-%d %H:%M:%S} {r.operacion} {r.tabla} filas={r.rowcount} "
        f"tiempo={r.elapsed:.3f}s sql={'Sí' if r.genero_sql else 'No'}"
        for r in registros
    )


def _dml_rows(registros: Sequence[AuditRecord]) -> int:
    """Filas de INSERT, UPDATE y DELETE: las mismas que cuenta ``rows_committed`` (desde v0.18.0 también el DELETE)."""
    return sum(r.rowcount for r in registros)


__all__: list[str] = ["BulkPersistenceManager"]
