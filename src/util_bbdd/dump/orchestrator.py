"""Orquestador de volcado de datos entre esquemas/bases de datos.

Punto de entrada público: ``DumpOrchestrator(config).run() → DumpResult``.

Flujo (5 fases):
  1. Análisis: orden de carga topológico (FK), tablas y columnas faltantes.
  2. Desactivación de constraints en destino.
  3. Limpieza del destino (si ``truncate_target=True``).
  4. Carga de datos (best-effort, continúa ante errores).
  5. Rehabilitación de constraints + sincronización PK + informe Excel.

Nota de rendimiento: el volcado **no** ejecuta una comparación de esquemas
(``SchemaComparator``). La introspección se limita a lo imprescindible para la
carga (tablas, columnas y FKs de origen); las columnas presentes en origen y
ausentes en destino se derivan durante la carga (``TableDumpResult.skipped_columns``)
y alimentan directamente el informe Excel, evitando la cascada N+1 de comparar
índices, FKs de destino, comentarios y vistas que no intervienen en el volcado.
"""

from __future__ import annotations

import logging
import math
import threading

from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from sqlalchemy import Engine, Inspector, Integer, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader, ParallelLoadResult
from util_bbdd.bulk.audit import AuditError, AuditManager

from .._core.exceptions import DumpError
from ._constraints import ConstraintManager, ConstraintResult
from ._indexes import IndexManager
from ._models import DumpAuditSummary, DumpConfig, DumpResult, IndexActionResult, PKSyncResult, TableDumpResult
from ._sql_utils import quote_identifier, quote_table
from .reporters import DumpReporter

_log = logging.getLogger(__name__)


def _read_chunks(conn: Any, sql: str, chunk_size: int, params: dict[str, Any] | None = None) -> Iterator[pd.DataFrame]:
    """Lee ``sql`` en DataFrames de hasta ``chunk_size`` filas con ``dtype=object``: cada valor tal como lo da el driver.

    PD-05 (performance-audit de dump 2026-09-25): ``pd.read_sql`` alteraba datos sin avisar. Los enteros de una columna
    con algún NULL pasaban a ``float64`` (BIGINT > 2^53 perdía precisión) y ``coerce_float=True`` (por defecto)
    convertía ``Decimal`` en ``float`` (DECIMAL de más de 15 dígitos). Ninguna opción de ``read_sql`` lo evita del todo:
    ``dtype_backend`` conserva los enteros pero entrega los ``Decimal`` como texto.
    """
    result = conn.execute(text(sql), params or {})
    keys = list(result.keys())
    while rows := result.fetchmany(chunk_size):
        yield pd.DataFrame(rows, columns=keys, dtype=object)


@dataclass(frozen=True)
class _AuditCounters:
    """Contadores de auditoría del volcado; ``BulkCrud`` y ``ParallelLoadResult`` exponen los mismos nombres."""

    audit_failures: int = 0
    audited_rows: int = 0
    unaudited_committed_rows: int = 0
    audit_uncommitted_records: int = 0

    @classmethod
    def of(cls, source: BulkCrud | ParallelLoadResult) -> _AuditCounters:
        return cls(
            audit_failures=source.audit_failures,
            audited_rows=source.audited_rows,
            unaudited_committed_rows=source.unaudited_committed_rows,
            audit_uncommitted_records=source.audit_uncommitted_records,
        )

    def __add__(self, other: _AuditCounters) -> _AuditCounters:
        return _AuditCounters(
            audit_failures=self.audit_failures + other.audit_failures,
            audited_rows=self.audited_rows + other.audited_rows,
            unaudited_committed_rows=self.unaudited_committed_rows + other.unaudited_committed_rows,
            audit_uncommitted_records=self.audit_uncommitted_records + other.audit_uncommitted_records,
        )


# Re-exportaciones para compatibilidad con importadores que usan orchestrator directamente
__all__: list[str] = ["DumpConfig", "DumpOrchestrator", "DumpResult", "TableDumpResult"]


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------


class DumpOrchestrator:
    """Orquesta el volcado de datos de un esquema/base de datos a otro.

    Ejemplo::

        from sqlalchemy import create_engine
        from util_bbdd.dump import DumpConfig, DumpOrchestrator

        config = DumpConfig(
            source_engine=create_engine("postgresql+psycopg2://..."),
            target_engine=create_engine("mssql+pymssql://..."),
            source_schema="public",
            target_schema="dbo",
            output_dir=Path("reports"),
        )
        result = DumpOrchestrator(config).run()
        print(result.report)
    """

    # Contadores de auditoría de los ParallelBulkLoader del volcado (se reinician en _reset_audit_tracking).
    _loader_audit: _AuditCounters

    def __init__(self, config: DumpConfig) -> None:
        self._cfg = config
        self._src_insp: Inspector = inspect(config.source_engine)
        self._dst_insp: Inspector = inspect(config.target_engine)
        self._warn_pool_config(config.target_engine)
        self._warn_chunk_size(config.target_engine, config.chunk_size)
        self._warn_sqlite_source(config.source_engine, config.target_engine)
        self._reset_audit_tracking()

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def run(self) -> DumpResult:
        """Ejecuta el volcado completo y retorna el resultado con el informe.

        Raises:
            DumpError: Si falla el análisis inicial de carga (introspección de tablas
                de origen/destino) — un fallo no recuperable de orquestación, a
                diferencia de los fallos por tabla individual durante la carga
                (best-effort, reflejados en ``TableDumpResult.error_msg``).
        """
        cfg = self._cfg
        dump_inicio = datetime.now()
        self._reset_audit_tracking()
        if cfg.bulk_audit_path is None:
            # M-4 (audit-code de ParallelBulkLoader 2026-09-25): un aviso por volcado, no uno por BulkCrud creada.
            _log.info("Auditoría bulk deshabilitada en el volcado (bulk_audit_path=None).")

        # FASE 1: Análisis de carga
        try:
            src_tables = self._get_source_tables()
            _dst_names = self._dst_insp.get_table_names(schema=cfg.target_schema)
        except SQLAlchemyError as exc:
            raise DumpError(f"Error analizando tablas de origen/destino para el volcado: {exc}") from exc
        # Comparación case-insensitive: motores distintos pueden devolver distinto case
        dst_lower: dict[str, str] = {}
        for _t in _dst_names:
            _key = _t.lower()
            if _key in dst_lower:
                _log.warning(
                    "Colisión de nombre en destino (case): '%s' y '%s' colisionan al normalizar; se usará '%s'.",
                    dst_lower[_key],
                    _t,
                    dst_lower[_key],
                )
            else:
                dst_lower[_key] = _t

        # src_to_dst: nombre_origen → nombre_canonical_destino
        src_to_dst: dict[str, str] = {t: dst_lower[t.lower()] for t in src_tables if t.lower() in dst_lower}
        missing_in_dst: list[str] = [t for t in src_tables if t.lower() not in dst_lower]

        load_order, cycles = DumpOrchestrator._topological_sort(src_tables, self._src_insp, cfg.source_schema)
        # Orden topológico filtrado a tablas presentes en destino
        effective_src_order: list[str] = [t for t in load_order if t in src_to_dst]
        effective_dst_order: list[str] = [src_to_dst[t] for t in effective_src_order]

        _log.info(
            "Volcado: %d tablas origen, %d en destino, %d faltantes, %d ciclos FK.",
            len(src_tables),
            len(effective_src_order),
            len(missing_in_dst),
            len(cycles),
        )

        # Fases 2-5: dentro del ConstraintManager (enable_all garantizado en __exit__)
        table_results: list[TableDumpResult] = []
        constraint_mgr = ConstraintManager(cfg.target_engine, cfg.target_schema)
        index_mgr: IndexManager | None = None

        with constraint_mgr:
            # FASE 2: Deshabilitar constraints (usando nombres canónicos del destino)
            constraint_mgr.disable_all(tables=effective_dst_order)

            # FASE 2b: Deshabilitar índices secundarios (opt-in). El IndexManager se anida
            # dentro del ConstraintManager para que su rebuild (__exit__) se ejecute ANTES
            # de la rehabilitación de constraints, que se beneficia de índices presentes.
            with ExitStack() as index_stack:
                if cfg.manage_indexes:
                    index_mgr = index_stack.enter_context(IndexManager(cfg.target_engine, cfg.target_schema))
                    index_mgr.disable_all(tables=effective_dst_order)

                # FASE 3: Limpieza del destino (usando nombres canónicos del destino)
                if cfg.truncate_target:
                    self._cleanup(list(reversed(effective_dst_order)), skip=set(missing_in_dst))

                # FASE 4: Carga (best-effort)
                cycle_set = {t for group in cycles for t in group}
                # Concurrencia efectiva: tablas en paralelo y rangos de PK por tabla,
                # ambos acotados a la capacidad real del pool (tablas * rangos <= capacidad).
                table_workers = self._resolve_max_workers(cfg.max_parallel_tables)
                self._effective_pk_ranges = self._resolve_range_count(cfg.parallel_pk_ranges, table_workers)
                crud = self._make_worker_crud()
                if cfg.max_parallel_tables > 1:
                    table_results.extend(self._load_parallel(effective_src_order, src_to_dst, cycle_set, table_workers))
                    # Reflejar tablas cargadas en la crud compartida para la Fase 5a (PK sync)
                    self._reflect_loaded_tables(crud, table_results, src_to_dst)
                else:
                    for position, src_t in enumerate(effective_src_order):
                        dst_t = src_to_dst[src_t]
                        result = self._process_table(src_t, dst_t, position, src_t in cycle_set, crud)
                        table_results.append(result)
                        _log.info(
                            "  [%d/%d] %s → %s (%d filas)",
                            position + 1,
                            len(effective_src_order),
                            src_t,
                            result.status,
                            result.target_rows_after,
                        )

        # Añadir tablas faltantes al resultado (informativo)
        table_results.extend(
            TableDumpResult(
                table_name=table,
                source_rows=self._safe_count(cfg.source_engine, table, cfg.source_schema),
                target_rows_before=0,
                target_rows_after=0,
                status="missing_target",
                skipped_columns=[],
                load_order_position=-1,
            )
            for table in missing_in_dst
        )

        constraint_results: list[ConstraintResult] = constraint_mgr.constraint_results
        index_results: list[IndexActionResult] | None = index_mgr.index_results if index_mgr is not None else None

        # FASE 5a: Resincronizar contadores PK en destino (si está habilitado)
        pk_sync_results: list[PKSyncResult] | None = self._sync_pk_sequences(
            crud=crud,
            effective_dst_order=effective_dst_order,
        )

        # Resumen de auditoría antes del informe, que lo incluye en la hoja "Auditoría Bulk". Las cargas y sus
        # sesiones de auditoría ya han terminado; la sincronización de PK no audita.
        audit_summary = self._summarize_audit(cfg.bulk_audit_path, dump_inicio)

        # FASE 5b: Generar informe Excel (la hoja "Columnas Inexistentes" se deriva
        # de TableDumpResult.skipped_columns; no requiere comparación de esquemas)
        report_path = DumpReporter(cfg.output_dir).generate(
            table_results=table_results,
            missing_tables=missing_in_dst,
            constraint_results=constraint_results,
            cycles=cycles,
            index_results=index_results,
            audit_summary=audit_summary,
            pk_sync_results=pk_sync_results,
        )

        return DumpResult(
            table_results=table_results,
            constraint_results=constraint_results,
            load_order=load_order,
            cycles_detected=cycles,
            report=report_path,
            audit_summary=audit_summary,
            pk_sync_results=pk_sync_results,
            index_results=index_results,
        )

    # ------------------------------------------------------------------
    # Fase 3: Limpieza del destino
    # ------------------------------------------------------------------

    def _cleanup(self, reversed_order: list[str], skip: set[str]) -> None:
        """Borra o trunca las tablas destino antes de cargar.

        Para SQL Server: TRUNCATE TABLE en tablas sin FK entrantes (instantáneo)
        y DELETE FROM en las referenciadas. Si TRUNCATE falla (FK de esquema
        externo no detectada), reintenta con DELETE via ``_cleanup_table``.
        Para SQLite: DELETE FROM siempre (no tiene TRUNCATE; un DELETE sin WHERE es su equivalente).
        Para PostgreSQL: un único TRUNCATE con todas las tablas (rechaza truncar una tabla referenciada por FK salvo
        que las que la referencian vayan en la misma sentencia); si falla, tabla a tabla.
        Para otros motores: TRUNCATE TABLE siempre.
        """
        cfg = self._cfg
        dialect = cfg.target_engine.dialect.name
        mssql_referenced: frozenset[str] = (
            self._get_dst_fk_referenced_tables(cfg.target_schema) if dialect == "mssql" else frozenset()
        )
        tables = [t for t in reversed_order if t not in skip]
        with cfg.target_engine.connect() as conn:
            if dialect == "postgresql" and len(tables) > 1 and self._truncate_together(conn, tables):
                return
            for table in tables:
                # SQLite no tiene TRUNCATE TABLE: fallaba con un WARNING, el destino no se limpiaba y la carga chocaba
                # con las PK existentes (o duplicaba filas en tablas sin PK).
                use_delete = dialect == "sqlite" or (dialect == "mssql" and table.lower() in mssql_referenced)
                self._cleanup_table(conn, table, cfg.target_schema, use_delete, dialect)

    def _truncate_together(self, conn: Any, tables: list[str]) -> bool:
        """PostgreSQL: ``TRUNCATE TABLE t1, t2, …`` en una sentencia. Devuelve ``False`` (con rollback) si falla.

        PD-03 (performance-audit de dump 2026-09-25): tabla a tabla, PostgreSQL rechaza truncar las tablas referenciadas
        por FK aunque la hija esté vacía y con los triggers desactivados; el destino conservaba sus filas y la carga
        chocaba con la PK. Sin CASCADE: una FK desde una tabla ajena al volcado hace fallar la sentencia en lugar de
        vaciar esa tabla, y entonces se vuelve a la limpieza tabla a tabla.
        """
        target = self._cfg.target_engine
        quoted = ", ".join(quote_table(t, self._cfg.target_schema, target) for t in tables)
        try:
            conn.execute(text(f"TRUNCATE TABLE {quoted}"))
            conn.commit()
            _log.debug("Limpiadas %d tablas con un único TRUNCATE.", len(tables))
            return True
        except SQLAlchemyError as exc:
            conn.rollback()
            _log.warning("TRUNCATE conjunto falló (%s); se limpia tabla a tabla.", exc)
            return False

    def _cleanup_table(
        self,
        conn: Any,
        table: str,
        schema: str | None,
        use_delete: bool,
        dialect: str,
    ) -> None:
        """Ejecuta DELETE o TRUNCATE en una tabla; reintenta con DELETE si TRUNCATE falla en mssql."""
        quoted = quote_table(table, schema, self._cfg.target_engine)
        sql = f"DELETE FROM {quoted}" if use_delete else f"TRUNCATE TABLE {quoted}"
        try:
            conn.execute(text(sql))
            conn.commit()
            _log.debug("Limpiada tabla '%s' (%s).", table, "DELETE" if use_delete else "TRUNCATE")
        except SQLAlchemyError as exc:
            conn.rollback()
            if not use_delete and dialect == "mssql":
                self._cleanup_table_delete_fallback(conn, table, quoted)
            else:
                _log.warning("Error limpiando tabla '%s': %s", table, exc)

    def _cleanup_table_delete_fallback(self, conn: Any, table: str, quoted: str) -> None:
        """Retry DELETE tras TRUNCATE fallido en SQL Server (FK de esquema externo)."""
        try:
            conn.execute(text(f"DELETE FROM {quoted}"))
            conn.commit()
            _log.debug("Limpiada tabla '%s' (DELETE fallback).", table)
        except SQLAlchemyError as exc:
            conn.rollback()
            _log.warning("Error limpiando tabla '%s': %s", table, exc)

    def _get_dst_fk_referenced_tables(self, schema: str | None) -> frozenset[str]:
        """Devuelve el conjunto (lowercase) de tablas destino con FK entrantes.

        Sólo se invoca para SQL Server. Permite usar TRUNCATE TABLE en tablas
        sin referencias FK entrantes. Si falla, devuelve frozenset vacío y el
        retry DELETE en _cleanup actúa como safety net.
        """
        try:
            referenced: set[str] = set()
            for table in self._dst_insp.get_table_names(schema=schema):
                for fk in self._dst_insp.get_foreign_keys(table, schema=schema):
                    ref: str = fk.get("referred_table", "")
                    if ref:
                        referenced.add(ref.lower())
            return frozenset(referenced)
        except SQLAlchemyError:
            _log.warning(
                "No se pudo determinar tablas con FK entrantes en destino SQL Server; "
                "se intentará TRUNCATE y se aplicará fallback DELETE en caso de error."
            )
            return frozenset()

    # ------------------------------------------------------------------
    # Fase 4: Carga de tabla individual
    # ------------------------------------------------------------------

    def _process_table(
        self, src_table: str, dst_table: str, position: int, in_cycle: bool, crud: BulkCrud
    ) -> TableDumpResult:
        common_cols, skipped_cols, col_name_map = self._common_columns(src_table, dst_table)
        pk_range_col = self._detect_pk_range_col(src_table, common_cols) if self._cfg.parallel_pk_ranges > 1 else None
        return self._process_table_with_columns(
            src_table, dst_table, position, in_cycle, crud, common_cols, skipped_cols, col_name_map, pk_range_col
        )

    def _process_table_with_columns(
        self,
        src_table: str,
        dst_table: str,
        position: int,
        in_cycle: bool,
        crud: BulkCrud,
        common_cols: list[str],
        skipped_cols: list[str],
        col_name_map: dict[str, str],
        pk_range_col: str | None = None,
    ) -> TableDumpResult:
        """Carga una tabla con sus columnas comunes ya resueltas.

        La introspección (``_common_columns``, ``pk_range_col``, vía Inspector no
        thread-safe) se calcula fuera de este método para poder precomputarla en serie
        antes de paralelizar. Este método solo abre conexiones propias (origen/destino),
        por lo que es seguro de ejecutar en un hilo dedicado con su propia instancia ``crud``.

        Si ``pk_range_col`` está presente y ``_effective_pk_ranges > 1``, la carga se
        particiona por rangos de esa PK entera y se ejecuta en paralelo (Incremento 3b).
        """
        cfg = self._cfg

        if not common_cols:
            if cfg.collect_row_counts:
                src_count = self._safe_count(cfg.source_engine, src_table, cfg.source_schema)
                tgt_count = self._safe_count(cfg.target_engine, dst_table, cfg.target_schema)
            else:
                src_count = tgt_count = -1
            return TableDumpResult(
                table_name=src_table,
                source_rows=src_count,
                target_rows_before=tgt_count,
                target_rows_after=tgt_count,
                status="skipped",
                skipped_columns=skipped_cols,
                load_order_position=position,
                in_cycle=in_cycle,
            )

        if cfg.collect_row_counts:
            source_rows = self._safe_count(cfg.source_engine, src_table, cfg.source_schema)
            target_rows_before = self._safe_count(cfg.target_engine, dst_table, cfg.target_schema)
        else:
            source_rows = target_rows_before = -1

        # bulk_insert_from_df → reflect_table espera nombre lógico sin quoting de dialecto
        # (schema.tabla o solo tabla). quote_table genera backticks/corchetes que reflect_table
        # no puede procesar, pues los pasa literalmente a SQLAlchemy Table().
        dest_table_logical = f"{cfg.target_schema}.{dst_table}" if cfg.target_schema else dst_table

        n_ranges: int = getattr(self, "_effective_pk_ranges", 1)
        if pk_range_col is not None and n_ranges > 1:
            error_msgs = self._load_in_pk_ranges(
                src_table, common_cols, col_name_map, pk_range_col, dest_table_logical, n_ranges
            )
        else:
            error_msgs = self._load_whole_table(src_table, common_cols, col_name_map, dest_table_logical, crud)

        target_rows_after = (
            self._safe_count(cfg.target_engine, dst_table, cfg.target_schema) if cfg.collect_row_counts else -1
        )
        status: Literal["success", "error"] = "error" if error_msgs else "success"

        return TableDumpResult(
            table_name=src_table,
            source_rows=source_rows,
            target_rows_before=target_rows_before,
            target_rows_after=target_rows_after,
            status=status,
            skipped_columns=skipped_cols,
            load_order_position=position,
            in_cycle=in_cycle,
            error_msg="; ".join(error_msgs),
        )

    def _load_whole_table(
        self,
        src_table: str,
        common_cols: list[str],
        col_name_map: dict[str, str],
        dest_table_logical: str,
        crud: BulkCrud,
    ) -> list[str]:
        """Lee la tabla origen completa y la inserta por chunks. Devuelve mensajes de error.

        Delega en ``bulk_insert_from_chunks``, que resuelve columnas de inserción y
        estrategia de identidad **una sola vez** para toda la tabla (en lugar de
        re-resolverlas por chunk como haría un bucle de ``bulk_insert_from_df``) y
        gestiona su propia ``bulk_session`` atómica. El renombrado de columnas se
        aplica de forma perezosa por chunk mediante un generador, manteniendo el
        streaming desde el origen sin materializar la tabla completa.
        """
        cfg = self._cfg
        cols_quoted = ", ".join(quote_identifier(c, cfg.source_engine) for c in common_cols)
        table_quoted = quote_table(src_table, cfg.source_schema, cfg.source_engine)
        sql = f"SELECT {cols_quoted} FROM {table_quoted}"
        error_msgs: list[str] = []
        try:
            with cfg.source_engine.connect() as conn:
                chunks = _read_chunks(conn, sql, cfg.chunk_size)
                renamed = (chunk[common_cols].rename(columns=col_name_map) for chunk in chunks)
                try:
                    crud.bulk_insert_from_chunks(renamed, dest_table_logical)
                except (SQLAlchemyError, ValueError, AuditError, OSError) as exc:
                    # AuditError/OSError: con bulk_audit_strict un fallo al escribir la auditoría deshace la tabla;
                    # queda como error de esa tabla, como cualquier otro fallo de carga, y el volcado sigue.
                    error_msgs.append(str(exc))
        except (SQLAlchemyError, ValueError, pd.errors.DatabaseError) as exc:
            error_msgs.append(f"Error leyendo origen: {exc}")
        return error_msgs

    # ------------------------------------------------------------------
    # Fase 4 (paralela): carga por rangos de PK (Incremento 3b)
    # ------------------------------------------------------------------

    def _load_in_pk_ranges(
        self,
        src_table: str,
        common_cols: list[str],
        col_name_map: dict[str, str],
        pk_col: str,
        dest_table_logical: str,
        n_ranges: int,
    ) -> list[str]:
        """Particiona la tabla por rangos contiguos de ``pk_col`` y los carga en paralelo.

        Responsabilidad de ``dump`` (política): calcular los rangos a partir del origen
        (MIN/MAX + bounds) y construir un *lector* por rango. El mecanismo de inserción
        paralela (un hilo y una ``BulkCrud`` por partición) lo aporta
        ``bulk.ParallelBulkLoader``. Los rangos son disjuntos por PK ⇒ sin colisión.
        """
        cfg = self._cfg
        pk_q = quote_identifier(pk_col, cfg.source_engine)
        table_quoted = quote_table(src_table, cfg.source_schema, cfg.source_engine)

        try:
            with cfg.source_engine.connect() as conn:
                row = conn.execute(text(f"SELECT MIN({pk_q}), MAX({pk_q}) FROM {table_quoted}")).one()
        except (SQLAlchemyError, ValueError) as exc:
            return [f"Error calculando rango PK: {exc}"]

        if row[0] is None or row[1] is None:
            return []  # tabla vacía

        bounds = DumpOrchestrator._compute_range_bounds(int(row[0]), int(row[1]), n_ranges)
        cols_quoted = ", ".join(quote_identifier(c, cfg.source_engine) for c in common_cols)

        def _make_reader(low: int, high: int, is_last: bool) -> Callable[[], Iterator[pd.DataFrame]]:
            op = "<=" if is_last else "<"
            sql = f"SELECT {cols_quoted} FROM {table_quoted} WHERE {pk_q} >= :lo AND {pk_q} {op} :hi"

            def _reader() -> Iterator[pd.DataFrame]:
                with cfg.source_engine.connect() as conn:
                    for chunk in _read_chunks(conn, sql, cfg.chunk_size, {"lo": low, "hi": high}):
                        yield chunk[common_cols].rename(columns=col_name_map)

            return _reader

        loader = ParallelBulkLoader(
            cfg.target_engine,
            chunk_size=cfg.chunk_size,
            max_workers=n_ranges,
            commit_every_n_chunks=cfg.commit_every_n_chunks,
            audit_csv_path=cfg.bulk_audit_path,
            audit_strict=cfg.bulk_audit_strict,
            strip_strings=False,  # PD-05: copia fiel del origen
        )
        readers = [_make_reader(lo, hi, last) for lo, hi, last in bounds]
        result = loader.load(dest_table_logical, readers)
        with self._audit_lock:
            self._loader_audit = self._loader_audit + _AuditCounters.of(result)
        return result.partition_errors

    @staticmethod
    def _compute_range_bounds(lo: int, hi: int, n: int) -> list[tuple[int, int, bool]]:
        """Divide [lo, hi] en hasta ``n`` rangos contiguos ``(low, high, is_last)``.

        Para rangos no finales: ``pk >= low AND pk < high`` (high exclusivo). Para el
        último: ``pk >= low AND pk <= hi`` (inclusivo). Sin solapes ni huecos.
        """
        if hi < lo:
            return []
        n = max(1, n)
        span = hi - lo + 1
        step = max(1, math.ceil(span / n))
        bounds: list[tuple[int, int, bool]] = []
        start = lo
        while start <= hi:
            end_excl = start + step
            if end_excl > hi:
                bounds.append((start, hi, True))
            else:
                bounds.append((start, end_excl, False))
            start = end_excl
        return bounds

    def _detect_pk_range_col(self, src_table: str, common_cols: list[str]) -> str | None:
        """Devuelve el nombre de la PK si es una única columna entera presente en ``common_cols``.

        Usa el Inspector de origen (no thread-safe): debe invocarse en serie, nunca en hilos.
        ``None`` si no hay PK de columna única entera o no está en las columnas comunes.
        """
        schema = self._cfg.source_schema
        try:
            pk = self._src_insp.get_pk_constraint(src_table, schema=schema)
        except SQLAlchemyError:
            return None
        cols = pk.get("constrained_columns") or []
        if len(cols) != 1 or cols[0] not in common_cols:
            return None
        pk_col = cols[0]
        try:
            for column in self._src_insp.get_columns(src_table, schema=schema):
                if column["name"] == pk_col:
                    return pk_col if isinstance(column.get("type"), Integer) else None
        except SQLAlchemyError:
            return None
        return None

    def _resolve_range_count(self, requested: int, table_workers: int) -> int:
        """Clampa el nº de rangos para que ``table_workers * rangos`` no exceda el pool (1 con destino SQLite)."""
        if requested <= 1:
            return 1
        if self._single_writer_target("parallel_pk_ranges", requested):
            return 1
        capacities = [
            DumpOrchestrator._pool_capacity(self._cfg.source_engine),
            DumpOrchestrator._pool_capacity(self._cfg.target_engine),
        ]
        known = [c for c in capacities if c is not None and c > 0]
        if known:
            cap = min(known)
            allowed = max(1, cap // max(table_workers, 1))
            if requested > allowed:
                _log.warning(
                    "parallel_pk_ranges=%d con %d tablas en paralelo excede la capacidad del pool (%d); "
                    "se degrada a %d rangos.",
                    requested,
                    table_workers,
                    cap,
                    allowed,
                )
                return allowed
        return requested

    # ------------------------------------------------------------------
    # Fase 4 (paralela): carga por niveles topológicos
    # ------------------------------------------------------------------

    def _load_parallel(
        self,
        effective_src_order: list[str],
        src_to_dst: dict[str, str],
        cycle_set: set[str],
        workers: int,
    ) -> list[TableDumpResult]:
        """Carga las tablas en paralelo por nivel topológico FK.

        Tablas de un mismo nivel (sin dependencia FK mutua) se cargan concurrentemente
        (hasta ``workers`` a la vez), cada una con su propia ``BulkCrud`` (no thread-safe).
        Las tablas en ciclos FK se cargan secuencialmente al final. Las columnas comunes y
        la PK de rango se precomputan en serie (Inspector no thread-safe). Resultados
        ordenados por posición de carga.
        """
        cfg = self._cfg
        position_of: dict[str, int] = {t: i for i, t in enumerate(effective_src_order)}

        noncycle = [t for t in effective_src_order if t not in cycle_set]
        cycle_tables = [t for t in effective_src_order if t in cycle_set]
        levels = DumpOrchestrator._topological_levels(noncycle, self._src_insp, cfg.source_schema)

        results: list[TableDumpResult] = []

        for level in levels:
            # Precomputar columnas y PK de rango en serie (Inspector no es thread-safe)
            precomputed = {src_t: self._precompute_table_meta(src_t, src_to_dst[src_t]) for src_t in level}
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        self._load_one_table,
                        src_t,
                        src_to_dst[src_t],
                        position_of[src_t],
                        False,
                        precomputed[src_t],
                    ): src_t
                    for src_t in level
                }
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    _log.info("  (par) %s → %s (%d filas)", futures[future], result.status, result.target_rows_after)

        # Ciclos FK: secuencial con una única crud
        if cycle_tables:
            cycle_crud = self._make_worker_crud()
            for src_t in cycle_tables:
                dst_t = src_to_dst[src_t]
                common_cols, skipped_cols, col_name_map, pk_col = self._precompute_table_meta(src_t, dst_t)
                result = self._process_table_with_columns(
                    src_t, dst_t, position_of[src_t], True, cycle_crud, common_cols, skipped_cols, col_name_map, pk_col
                )
                results.append(result)
                _log.info("  (ciclo) %s → %s (%d filas)", src_t, result.status, result.target_rows_after)

        results.sort(key=lambda r: r.load_order_position)
        return results

    def _precompute_table_meta(
        self, src_table: str, dst_table: str
    ) -> tuple[list[str], list[str], dict[str, str], str | None]:
        """Calcula en serie (Inspector no thread-safe) columnas comunes + PK de rango."""
        common_cols, skipped_cols, col_name_map = self._common_columns(src_table, dst_table)
        pk_col = self._detect_pk_range_col(src_table, common_cols) if self._cfg.parallel_pk_ranges > 1 else None
        return common_cols, skipped_cols, col_name_map, pk_col

    def _load_one_table(
        self,
        src_table: str,
        dst_table: str,
        position: int,
        in_cycle: bool,
        meta: tuple[list[str], list[str], dict[str, str], str | None],
    ) -> TableDumpResult:
        """Tarea de hilo: carga una tabla con su propia ``BulkCrud`` y metadatos precomputados."""
        crud = self._make_worker_crud()
        common_cols, skipped_cols, col_name_map, pk_col = meta
        return self._process_table_with_columns(
            src_table, dst_table, position, in_cycle, crud, common_cols, skipped_cols, col_name_map, pk_col
        )

    def _reflect_loaded_tables(
        self,
        crud: BulkCrud,
        table_results: list[TableDumpResult],
        src_to_dst: dict[str, str],
    ) -> None:
        """Refleja en ``crud`` las tablas efectivamente cargadas (para la Fase 5a PK sync).

        Bajo carga paralela las ``BulkCrud`` por hilo no pueblan la caché de ``crud``.
        Se reflejan aquí las tablas con carga intentada (``success``/``error``), usando la
        misma convención de nombre lógico que la ruta secuencial, para que
        ``_sync_pk_sequences`` opere sin cambios.
        """
        schema = self._cfg.target_schema
        for res in table_results:
            if res.status not in ("success", "error"):
                continue
            dst = src_to_dst.get(res.table_name)
            if dst is None:
                continue
            dest_logical = f"{schema}.{dst}" if schema else dst
            try:
                crud.reflect_table(dest_logical)
            except SQLAlchemyError as exc:
                _log.debug("No se pudo reflejar '%s' para PK sync: %s", dest_logical, exc)

    def _make_worker_crud(self) -> BulkCrud:
        """Crea una ``BulkCrud`` del volcado (la principal o una dedicada por hilo).

        La auditoría es concurrente-segura: ``AuditCsvRepository`` serializa las
        escrituras al mismo CSV mediante un lock por-ruta, por lo que cada worker
        puede registrar inserts en ``bulk_audit_path`` sin intercalar filas. La instancia
        queda registrada para sumar sus contadores de auditoría al resumen del volcado.
        """
        cfg = self._cfg
        crud = BulkCrud(
            cfg.target_engine,
            chunk_size=cfg.chunk_size,
            audit_csv_path=cfg.bulk_audit_path,
            commit_every_n_chunks=cfg.commit_every_n_chunks,
            audit_strict=cfg.bulk_audit_strict,
            warn_if_audit_disabled=False,  # run() avisa una vez por volcado
            strip_strings=False,  # PD-05: copia fiel del origen
        )
        with self._audit_lock:
            self._audit_cruds.append(crud)
        return crud

    def _reset_audit_tracking(self) -> None:
        """Reinicia los contadores de auditoría del volcado (``BulkCrud`` creadas y loaders paralelos)."""
        self._audit_lock = threading.Lock()
        self._audit_cruds: list[BulkCrud] = []
        self._loader_audit = _AuditCounters()

    def _audit_counters(self) -> _AuditCounters:
        """Contadores de auditoría del volcado: los de cada ``BulkCrud`` y los de los loaders paralelos.

        Las ``BulkCrud`` internas de ``ParallelBulkLoader`` no están en ``_audit_cruds``: llegan solo por su resultado.
        """
        with self._audit_lock:
            total = self._loader_audit
            for crud in self._audit_cruds:
                total = total + _AuditCounters.of(crud)
            return total

    def _summarize_audit(self, audit_path: Path | None, desde: datetime) -> DumpAuditSummary | None:
        """``_build_audit_summary`` con los contadores acumulados durante el volcado."""
        counters = self._audit_counters()
        return DumpOrchestrator._build_audit_summary(
            audit_path,
            desde,
            audit_failures=counters.audit_failures,
            audited_rows=counters.audited_rows,
            unaudited_committed_rows=counters.unaudited_committed_rows,
            audit_uncommitted_records=counters.audit_uncommitted_records,
        )

    def _resolve_max_workers(self, requested: int) -> int:
        """Clampa los workers a la capacidad real de pool de ambos engines.

        Devuelve ``min(requested, capacidad_origen, capacidad_destino)``; degrada con
        warning si el pool no alcanza ``requested``. Si la capacidad no es determinable
        (pool sin ``size()``), respeta ``requested``. Con destino SQLite devuelve siempre 1.
        """
        if requested <= 1:
            return 1
        if self._single_writer_target("max_parallel_tables", requested):
            return 1
        capacities = [
            DumpOrchestrator._pool_capacity(self._cfg.source_engine),
            DumpOrchestrator._pool_capacity(self._cfg.target_engine),
        ]
        known = [c for c in capacities if c is not None and c > 0]
        if known:
            cap = min(known)
            if requested > cap:
                _log.warning(
                    "max_parallel_tables=%d excede la capacidad del pool (%d); se degrada a %d. "
                    "Aumenta pool_size/max_overflow para mayor paralelismo.",
                    requested,
                    cap,
                    cap,
                )
                return cap
        return requested

    def _single_writer_target(self, option: str, requested: int) -> bool:
        """``True`` (con WARNING) si el destino admite un solo escritor a la vez (SQLite) y se pidió paralelismo.

        PD-06 (performance-audit de dump 2026-09-25): con destino SQLite, las particiones o tablas en paralelo chocaban
        con ``database is locked``; la tabla quedaba en ``error`` y a medio cargar (1,5M de 2M filas con 4 rangos).
        """
        if self._cfg.target_engine.dialect.name != "sqlite":
            return False
        _log.warning(
            "%s=%d no se aplica con destino SQLite (admite un solo escritor a la vez); se carga sin paralelismo.",
            option,
            requested,
        )
        return True

    @staticmethod
    def _pool_capacity(engine: Engine) -> int | None:
        """Capacidad del pool (``size + max_overflow``) o ``None`` si no es determinable."""
        pool = engine.pool
        size_fn = getattr(pool, "size", None)
        if not callable(size_fn):
            return None
        try:
            size_result = size_fn()
            base = int(size_result) if isinstance(size_result, (int, str, float)) else int(str(size_result))
            overflow_raw: Any = getattr(pool, "_max_overflow", 0) or 0
            overflow = int(overflow_raw)
        except (TypeError, ValueError):
            return None
        return base + max(overflow, 0)

    # ------------------------------------------------------------------
    # Fase 5a: Resincronización de contadores PK
    # ------------------------------------------------------------------

    def _sync_pk_sequences(
        self,
        crud: BulkCrud,
        effective_dst_order: list[str],
    ) -> list[PKSyncResult] | None:
        """Resincroniza los contadores PK en el destino tras la carga masiva.

        Usa las tablas ya reflejadas en ``crud._table_cache`` para evitar una segunda
        ronda de introspección. Si ``DumpConfig.sync_pk_sequences=False``, retorna ``None``.
        Los errores por tabla se capturan en ``PKSyncResult.status="error"`` y no
        interrumpen el volcado.
        """
        if not self._cfg.sync_pk_sequences:
            return None

        # PD-02 (performance-audit de dump 2026-09-25): la caché usa el nombre lógico de la carga ("esquema.tabla" con
        # target_schema); filtrar con el nombre sin esquema no encontraba nada y la Fase 5a no sincronizaba ninguna tabla.
        schema = self._cfg.target_schema
        logical_names = [f"{schema}.{t}" if schema else t for t in effective_dst_order]
        tables = [t for t in logical_names if t in crud._table_cache]
        if not tables:
            _log.debug("PK sync: no hay tablas en caché para sincronizar (load vacío).")
            return None

        results = crud.sync_pk_sequences(tables)

        synced = sum(1 for r in results if r.status == "synced")
        no_rows = sum(1 for r in results if r.status == "no_rows")
        skipped = sum(1 for r in results if r.status == "skipped")
        unsupported = sum(1 for r in results if r.status == "unsupported")
        errors = sum(1 for r in results if r.status == "error")

        _log.info(
            "Fase 5a (PK sync): synced=%d, no_rows=%d, skipped=%d, unsupported=%d, errors=%d",
            synced,
            no_rows,
            skipped,
            unsupported,
            errors,
        )
        for r in results:
            if r.status == "error":
                _log.warning("  PK sync error %s.%s: %s", r.table_name, r.column_name, r.error_msg)

        return results or None

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _get_source_tables(self) -> list[str]:
        if self._cfg.tables is not None:
            return sorted(self._cfg.tables)
        return self._src_insp.get_table_names(schema=self._cfg.source_schema)

    def _common_columns(self, src_table: str, dst_table: str) -> tuple[list[str], list[str], dict[str, str]]:
        """Retorna (columnas_comunes_origen, columnas_omitidas, mapa_origen→destino).

        El mapa permite renombrar el DataFrame antes del INSERT cuando la BD
        destino tiene el mismo nombre de columna en distinto case (p.ej. origen
        ``UserID`` → destino ``userid`` en una BD case-sensitive).
        Acepta nombres distintos para origen (``src_table``) y destino (``dst_table``)
        para soportar motores con diferente sensibilidad a mayúsculas.
        """
        src = [c["name"] for c in self._src_insp.get_columns(src_table, schema=self._cfg.source_schema)]
        dst_by_lower = {
            c["name"].lower(): c["name"] for c in self._dst_insp.get_columns(dst_table, schema=self._cfg.target_schema)
        }
        common = [name for name in src if name.lower() in dst_by_lower]
        skipped = [name for name in src if name.lower() not in dst_by_lower]
        name_map = {name: dst_by_lower[name.lower()] for name in common}
        return common, skipped, name_map

    def _safe_count(self, engine: Engine, table: str, schema: str | None) -> int:
        try:
            return DumpOrchestrator._count_rows(engine, table, schema)
        except SQLAlchemyError:
            return -1

    # ------------------------------------------------------------------
    # Helpers estáticos: conteo, grafo FK y orden topológico
    # ------------------------------------------------------------------

    @staticmethod
    def _count_rows(engine: Engine, table: str, schema: str | None) -> int:
        """Cuenta filas de una tabla usando una conexión del engine dado."""
        quoted = quote_table(table, schema, engine)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
            val = result.scalar_one()
            return int(val) if val is not None else 0

    @staticmethod
    def _build_fk_graph(
        tables: list[str],
        inspector: Inspector,
        schema: str | None,
    ) -> tuple[dict[str, set[str]], dict[str, int]]:
        """Construye el grafo de dependencias FK entre las tablas dadas."""
        tables_set = set(tables)
        # dependents[A] = {B} → B depende de A (A debe cargarse antes que B)
        dependents: dict[str, set[str]] = {t: set() for t in tables}
        in_degree: dict[str, int] = dict.fromkeys(tables, 0)

        for table in tables:
            try:
                fks = inspector.get_foreign_keys(table, schema=schema)
            except SQLAlchemyError:
                continue
            for fk in fks:
                referred = fk.get("referred_table", "")
                if referred and referred != table and referred in tables_set and table not in dependents[referred]:
                    dependents[referred].add(table)
                    in_degree[table] += 1

        return dependents, in_degree

    @staticmethod
    def _topological_levels(
        tables: list[str],
        inspector: Inspector,
        schema: str | None,
    ) -> list[list[str]]:
        """Agrupa las tablas en niveles topológicos FK (Kahn por profundidad).

        Cada nivel contiene tablas mutuamente independientes (sin FK entre ellas),
        cargables concurrentemente. Las tablas en ciclos FK se excluyen (no aparecen
        en ningún nivel). Dentro de cada nivel el orden es alfabético (determinista).
        """
        dependents, in_degree = DumpOrchestrator._build_fk_graph(tables, inspector, schema)
        levels: list[list[str]] = []
        seen: set[str] = set()
        current: list[str] = sorted(t for t in tables if in_degree[t] == 0)

        while current:
            levels.append(current)
            seen.update(current)
            nxt: set[str] = set()
            for node in current:
                for dep in dependents[node]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        nxt.add(dep)
            current = sorted(nxt)

        return levels

    @staticmethod
    def _topological_sort(
        tables: list[str],
        inspector: Inspector,
        schema: str | None,
    ) -> tuple[list[str], list[list[str]]]:
        """Ordena tablas respetando dependencias FK usando el algoritmo de Kahn.

        Returns:
            (ordered_tables, cycles) — las tablas en ciclos se añaden al final
            de ``ordered_tables`` y se listan en ``cycles``.
        """
        dependents, in_degree = DumpOrchestrator._build_fk_graph(tables, inspector, schema)

        queue: deque[str] = deque(t for t in tables if in_degree[t] == 0)
        ordered: list[str] = []

        while queue:
            node = queue.popleft()
            ordered.append(node)
            for dep in sorted(dependents[node]):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        cycle_tables = [t for t in tables if t not in set(ordered)]
        if not cycle_tables:
            return ordered, []

        cycles = DumpOrchestrator._find_cycle_components(cycle_tables, dependents)
        return ordered + cycle_tables, cycles

    @staticmethod
    def _find_cycle_components(
        cycle_tables: list[str],
        dependents: dict[str, set[str]],
    ) -> list[list[str]]:
        """Agrupa nodos en ciclo FK en componentes conexas mediante BFS no dirigido."""
        adj = DumpOrchestrator._build_cycle_adj(cycle_tables, dependents)
        visited: set[str] = set()
        cycles: list[list[str]] = []
        for start in cycle_tables:
            if start not in visited:
                component = DumpOrchestrator._bfs_component(start, adj, visited)
                cycles.append(component)
        return cycles

    @staticmethod
    def _build_cycle_adj(
        cycle_tables: list[str],
        dependents: dict[str, set[str]],
    ) -> dict[str, set[str]]:
        """Construye grafo de adyacencia no dirigido restringido a los nodos en ciclo."""
        cycle_set = set(cycle_tables)
        adj: dict[str, set[str]] = {t: set() for t in cycle_tables}
        for node, deps in dependents.items():
            if node not in cycle_set:
                continue
            for dep in deps:
                if dep in cycle_set:
                    adj[node].add(dep)
                    adj[dep].add(node)
        return adj

    @staticmethod
    def _bfs_component(
        start: str,
        adj: dict[str, set[str]],
        visited: set[str],
    ) -> list[str]:
        """Retorna todos los nodos alcanzables desde ``start`` mediante BFS."""
        component: list[str] = []
        queue: deque[str] = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            queue.extend(n for n in adj[node] if n not in visited)
        return component

    @staticmethod
    def _build_audit_summary(
        audit_path: Path | None,
        desde: datetime,
        audit_failures: int = 0,
        *,
        audited_rows: int | None = None,
        unaudited_committed_rows: int = 0,
        audit_uncommitted_records: int = 0,
    ) -> DumpAuditSummary | None:
        """Lee el CSV de auditoría y extrae métricas del volcado actual.

        Filtra por ``timestamp >= desde`` para aislar las entradas de este volcado
        frente a operaciones previas que pudieran existir en el mismo CSV.
        Devuelve ``None`` si la ruta no está configurada, o si el fichero no existe o no
        hay entradas en el rango temporal y no hubo incidencias. Si ``audit_failures``,
        ``unaudited_committed_rows`` o ``audit_uncommitted_records`` es mayor que 0 devuelve
        siempre un resumen (con métricas del CSV a 0 si no hay entradas), para que el
        problema no quede oculto.

        ``audited_rows`` son las filas que el volcado escribió según sus contadores; ``None`` si
        no se conocen (entonces vale 0 en el resumen y no se compara con el CSV). Si difiere de
        ``total_filas`` se registra un WARNING.
        """
        if audit_path is None:
            return None

        counters: dict[str, int] = {
            "audit_failures": audit_failures,
            "audited_rows": audited_rows or 0,
            "unaudited_committed_rows": unaudited_committed_rows,
            "audit_uncommitted_records": audit_uncommitted_records,
        }
        incidencias = audit_failures > 0 or unaudited_committed_rows > 0 or audit_uncommitted_records > 0

        def _sin_entradas() -> DumpAuditSummary | None:
            if not incidencias:
                return None
            return DumpAuditSummary(
                total_operaciones=0,
                total_filas=0,
                tiempo_total_seg=0.0,
                tiempo_promedio_seg=0.0,
                tablas_auditadas=0,
                tabla_mas_activa=None,
                audit_path=audit_path,
                **counters,
            )

        if not audit_path.is_file():
            return _sin_entradas()
        try:
            mgr = AuditManager(audit_path, cache_enabled=False)
            df = mgr.leer_auditoria()
        except Exception as exc:
            _log.warning("No se pudo leer el CSV de auditoría '%s': %s", audit_path, exc)
            return _sin_entradas()
        if df.empty:
            return _sin_entradas()
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        # H3 (audit-code 2026-09-25): el CSV guarda el timestamp truncado al segundo; comparar con ``desde`` y sus
        # microsegundos descartaba las operaciones terminadas en el mismo segundo en que empezó el volcado.
        df = df[df["timestamp"] >= pd.Timestamp(desde.replace(microsecond=0))]
        if df.empty:
            return _sin_entradas()
        tabla_mas_activa: str | None = str(df["tabla"].value_counts().index[0]) if len(df) > 0 else None
        total_filas = int(df["total_filas"].sum())
        if audited_rows is not None and audited_rows != total_filas:
            _log.warning(
                "Auditoría del volcado: el CSV suma %d filas desde el inicio y el volcado escribió %d. Causas "
                "probables: otros procesos escriben en el mismo CSV, o registros escritos antes de un commit que "
                "falló (audit_uncommitted_records=%d).",
                total_filas,
                audited_rows,
                audit_uncommitted_records,
            )
        return DumpAuditSummary(
            total_operaciones=int(len(df)),
            total_filas=total_filas,
            tiempo_total_seg=round(float(df["tiempo_seg"].sum()), 3),
            tiempo_promedio_seg=round(float(df["tiempo_seg"].mean()), 3),
            tablas_auditadas=int(df["tabla"].nunique()),
            tabla_mas_activa=tabla_mas_activa,
            audit_path=audit_path,
            **counters,
        )

    @staticmethod
    def _warn_sqlite_source(source: Engine, target: Engine) -> None:
        """Advierte de un origen SQLite: sin tipos, fechas y DECIMAL no llegan como ``datetime``/``Decimal``.

        PD-07 (performance-audit de dump 2026-09-25): SQLite no tiene tipos de columna, así que el driver entrega las
        fechas como texto y los DECIMAL como ``float``. Un destino servidor convierte el texto; un destino SQLite rechaza
        las fechas como texto (``SQLite DateTime type only accepts Python datetime…``) y los DECIMAL pierden precisión.
        """
        if source.dialect.name != "sqlite":
            return
        _log.warning(
            "Origen SQLite: las fechas se leen como texto y los DECIMAL como float (SQLite no tiene tipos de columna). "
            "Con destino SQLite, las tablas con columnas de fecha fallarán; los DECIMAL pueden perder precisión."
            if target.dialect.name == "sqlite"
            else "Origen SQLite: las fechas se leen como texto (el destino las convierte) y los DECIMAL como float "
            "(pueden perder precisión), porque SQLite no tiene tipos de columna."
        )

    @staticmethod
    def _warn_chunk_size(engine: Engine, chunk_size: int) -> None:
        """Advierte si chunk_size es alto para destinos MariaDB/MySQL.

        Tablas con columnas TEXT/BLOB/JSON pueden producir paquetes INSERT que superen
        ``max_allowed_packet`` del servidor (16 MB por defecto en MariaDB antiguas),
        resultando en ``Lost connection to server during query`` (error 2013).
        """
        if engine.dialect.name not in ("mariadb", "mysql"):
            return
        if chunk_size > 1000:
            _log.warning(
                "chunk_size=%d con destino %s puede causar 'Lost connection to server during query' "
                "en tablas con columnas TEXT/BLOB/JSON extensas (max_allowed_packet excedido). "
                "Considera reducir chunk_size a 500 o menos, o aumentar max_allowed_packet en el servidor.",
                chunk_size,
                engine.dialect.name,
            )

    @staticmethod
    def _warn_pool_config(engine: Engine) -> None:
        """Emite warnings si el engine MariaDB/MySQL destino carece de configuración de pool robusta.

        El driver nativo ``mariadb+mariadbconnector`` tiene casos donde ``ping()`` retorna éxito
        pero la siguiente query falla con ``InterfaceError: Server has gone away``. Mitigaciones:
        - ``pool_pre_ping=True``: SQLAlchemy verifica la conexión antes de usarla.
        - ``pool_recycle=3600``: fuerza rotación de conexiones cada hora.

        Engines creados vía ``SyncDatabaseManager.get_sqlalchemy_engine()`` ya incluyen ambas.
        """
        if engine.dialect.name not in ("mariadb", "mysql"):
            return
        pre_ping: bool = getattr(engine.pool, "_pre_ping", False)
        if not pre_ping:
            _log.warning(
                "El engine destino (%s) no tiene pool_pre_ping=True. "
                "Crea el engine con create_engine(url, pool_pre_ping=True, pool_recycle=3600) "
                "o usa SyncDatabaseManager.get_sqlalchemy_engine().",
                engine.dialect.name,
            )
        recycle: int = getattr(engine.pool, "_recycle", -1)
        if recycle < 0:
            _log.warning(
                "El engine destino (%s) no tiene pool_recycle configurado. "
                "Sin rotación de conexiones, 'Server has gone away' puede ocurrir en volcados largos. "
                "Añade pool_recycle=3600 al create_engine() o usa SyncDatabaseManager.get_sqlalchemy_engine().",
                engine.dialect.name,
            )
