"""Orquestador de volcado de datos entre esquemas/bases de datos.

Punto de entrada público: ``DumpOrchestrator(config).run() → DumpResult``.

Flujo (5 fases):
  1. Análisis: orden de carga topológico (FK), tablas y columnas faltantes.
  2. Desactivación de constraints en destino.
  3. Limpieza del destino (si ``truncate_target=True``).
  4. Carga de datos (best-effort, continúa ante errores).
  5. Rehabilitación de constraints + sincronización PK + informe Excel.

La documentación pública (``docs/api/dump.md``, ``docs/functional/dump_data_export.md``) y los docstrings de
``DumpConfig``/``DumpResult`` numeran las mismas etapas del 1 al 7 (introspección, análisis FK, constraints,
limpieza, carga, rehabilitación con la sincronización de PK como «Fase 6a», informe). Los comentarios y el log de
este módulo usan la agrupación en 5 fases de arriba: la «Fase 5a» del log es la «Fase 6a» de la documentación.

Nota de rendimiento: el volcado **no** ejecuta una comparación de esquemas
(``SchemaComparator``). La introspección se limita a lo imprescindible para la
carga (tablas, columnas y FKs de origen); las columnas presentes en origen y
ausentes en destino se derivan durante la carga (``TableDumpResult.skipped_columns``)
y alimentan directamente el informe Excel, evitando la cascada N+1 de comparar
índices, FKs de destino, comentarios y vistas que no intervienen en el volcado.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import pandas as pd

from sqlalchemy import Engine, Inspector, Integer, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import sqltypes

from util_bbdd._core.batching import resolve_write_batch_size
from util_bbdd.audit.counters import AuditCounters
from util_bbdd.audit.events import AuditEvent
from util_bbdd.audit.readiness import ReadinessBlock
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader, RangePartitioner
from util_bbdd.bulk._execution.parallel_planner import SINGLE_WRITER_DIALECTS, ParallelPlanner, PlanInput
from util_bbdd.bulk._support.dialect import MYSQL_FAMILY
from util_bbdd.bulk._support.iterables import close_if_closable
from util_bbdd.bulk._support.pool import pool_capacity
from util_bbdd.bulk.options import (
    AuditOptions,
    BatchOptions,
    BulkOptions,
    ExecutionOptions,
    ParallelOptions,
    RejectOptions,
)

from .._core.exceptions import AuditError, DumpError, DumpReportError
from ..connection.performance_advisor import EngineReadinessAdvisor
from ..metadata.reflection import (
    MetadataKind,
    TableMetadata,
    inspector_for,
    prefetch_table_metadata,
    table_names,
)
from . import _audit_summary, _fk_graph
from ._audit_events import DumpAuditEvents, DumpAuditWriter
from ._constraints import ConstraintManager, ConstraintResult
from ._indexes import IndexManager
from ._models import DumpAuditSummary, DumpConfig, DumpResult, IndexActionResult, PKSyncResult, TableDumpResult
from ._source_reader import (
    _PREFETCH_SOURCE_DIALECTS,
    _execute_read as _execute_read,  # re-export (R10a): tests y llamadores previos
    _prefetch,
    _read_chunks,
    _rebatch,
)
from ._sql_utils import quote_identifier, quote_table
from .reporters import DumpReporter

_AuditCounters = AuditCounters  # contadores de auditoría del volcado (BulkCrud + ParallelLoadResult)


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

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    # Contadores de auditoría de los ParallelBulkLoader del volcado (se reinician en _reset_audit_tracking).
    _loader_audit: _AuditCounters
    #: Metadatos de las tablas del volcado leídos por lotes al empezar (D2, ADR-003); sin ellos, tabla a tabla.
    _src_meta: TableMetadata | None = None
    _dst_meta: TableMetadata | None = None

    def __init__(self, config: DumpConfig) -> None:
        self._cfg = config
        self._src_insp: Inspector = inspector_for(config.source_engine)
        self._dst_insp: Inspector = inspector_for(config.target_engine)
        self._src_meta = self._dst_meta = None
        self._warn_pool_config(config.target_engine)
        self._warn_sqlite_source(config.source_engine, config.target_engine)
        self._reset_audit_tracking()
        #: run_id de los eventos de ``audit_sink`` del volcado en curso (None sin destino).
        self._audit_run_id: str | None = None

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def run(self) -> DumpResult:
        """Ejecuta el volcado completo y retorna el resultado con el informe.

        Con ``DumpConfig.audit_sink``, al terminar (también si falla) escribe en él un evento por tabla, constraint,
        índice y contador PK y un ``run`` de cierre, con el ``run_id`` del volcado (``DumpResult.audit_run_id``).

        Raises:
            DumpError: Si falla el análisis inicial de carga (introspección de tablas
                de origen/destino) — un fallo no recuperable de orquestación, a
                diferencia de los fallos por tabla individual durante la carga
                (best-effort, reflejados en ``TableDumpResult.error_msg``).
            DumpReportError: Si falla la generación del informe Excel, ya terminada la carga. ``exc.result`` lleva el
                ``DumpResult`` completo (su ``report`` es la ruta prevista, sin crear).
        """
        sink = self._cfg.audit_sink
        if sink is None:
            self._audit_run_id = None
            return self._run_dump()
        self._audit_run_id = uuid.uuid4().hex
        writer = DumpAuditWriter(sink)
        started = time.perf_counter()
        try:
            result = self._run_dump()
        except DumpReportError as exc:
            self._write_dump_events(writer, exc.result, exc, time.perf_counter() - started)
            raise
        except Exception as exc:
            self._write_dump_events(writer, None, exc, time.perf_counter() - started)
            raise
        self._write_dump_events(writer, result, None, time.perf_counter() - started)
        return result

    def _init_dump_run(self) -> tuple[Path, Path | None, datetime]:
        """Inicializa paths y auditoría para el volcado."""
        cfg = self._cfg
        output_dir: Path = cfg.output_dir  # Path por DumpConfig (PathField, T-09); antes se revalidaba aquí
        bulk_audit_path: Path | None = cfg.bulk_audit_path
        dump_inicio = datetime.now()
        self._reset_audit_tracking()
        # 3.4 (PF-08): tamaño del CSV de auditoría al empezar; el resumen solo lee lo añadido desde aquí.
        self._audit_start_offset = DumpOrchestrator._file_size(bulk_audit_path)
        self._audit_start_identity = DumpOrchestrator._file_identity(bulk_audit_path)
        if bulk_audit_path is None and cfg.audit_sink is None:
            # M-4 (audit-code de ParallelBulkLoader 2026-09-25): un aviso por volcado, no uno por BulkCrud creada.
            self.logger.info("Auditoría bulk deshabilitada en el volcado (bulk_audit_path=None).")
        return output_dir, bulk_audit_path, dump_inicio

    def _engine_readiness(self) -> list[ReadinessBlock]:
        """Condiciones de origen y destino (``EngineReadinessAdvisor``) para la hoja «Condiciones del motor».

        Se verifican al empezar, una vez por engine en el proceso: el ``BulkCrud`` del destino reutiliza la verificación
        y no la repite. Nunca lanza: un motor que no se puede verificar sale con su aviso y el volcado sigue.
        """
        cfg = self._cfg
        roles: list[tuple[str, Engine]] = (
            [("Origen y destino", cfg.target_engine)]
            if cfg.source_engine is cfg.target_engine
            else [("Origen", cfg.source_engine), ("Destino", cfg.target_engine)]
        )
        advisor = EngineReadinessAdvisor()
        blocks: list[ReadinessBlock] = []
        for role, engine in roles:
            try:
                blocks.append((f"{role} · {advisor.describe_engine(engine)}", advisor.engine_report(engine)))
            except Exception as exc:
                self.logger.warning(
                    "No se pudieron verificar las condiciones del motor (%s): %s", role, type(exc).__name__
                )
                blocks.append((role, None))
        return blocks

    def _analyze_dump_phase(self) -> tuple[list[str], dict[str, str], list[str], list[str], list[list[str]]]:
        """FASE 1: Análisis de carga. Retorna (src_tables, dst_lower, missing_in_dst, load_order, cycles)."""
        cfg = self._cfg
        try:
            src_tables = self._get_source_tables()
            _dst_names = table_names(self._dst_insp, cfg.target_schema)
        except SQLAlchemyError as exc:
            raise DumpError(f"Error analizando tablas de origen/destino para el volcado: {exc}") from exc

        # Comparación case-insensitive: motores distintos pueden devolver distinto case
        dst_lower: dict[str, str] = {}
        for _t in _dst_names:
            _key = _t.lower()
            if _key in dst_lower:
                self.logger.warning(
                    "Colisión de nombre en destino (case): '%s' y '%s' colisionan al normalizar; se usará '%s'.",
                    dst_lower[_key],
                    _t,
                    dst_lower[_key],
                )
            else:
                dst_lower[_key] = _t

        missing_in_dst: list[str] = [t for t in src_tables if t.lower() not in dst_lower]
        load_order, cycles = DumpOrchestrator._topological_sort(src_tables, self._src_insp, cfg.source_schema)
        return src_tables, dst_lower, missing_in_dst, load_order, cycles

    def _compute_load_order(
        self,
        src_tables: list[str],
        dst_lower: dict[str, str],
        load_order: list[str],
    ) -> tuple[dict[str, str], list[str], list[str]]:
        """Calcula src_to_dst y órdenes efectivos."""
        # src_to_dst: nombre_origen → nombre_canonical_destino
        src_to_dst: dict[str, str] = {t: dst_lower[t.lower()] for t in src_tables if t.lower() in dst_lower}
        # Orden topológico filtrado a tablas presentes en destino
        effective_src_order: list[str] = [t for t in load_order if t in src_to_dst]
        effective_dst_order: list[str] = [src_to_dst[t] for t in effective_src_order]
        return src_to_dst, effective_src_order, effective_dst_order

    def _execute_load_phases(
        self,
        effective_src_order: list[str],
        effective_dst_order: list[str],
        src_to_dst: dict[str, str],
        cycles: list[list[str]],
        missing_in_dst: list[str],
    ) -> tuple[list[TableDumpResult], IndexManager | None, BulkCrud, ConstraintManager]:
        """Ejecuta Fases 2-4: constraints, cleanup y carga."""
        cfg = self._cfg
        table_results: list[TableDumpResult] = []
        constraint_mgr = ConstraintManager(cfg.target_engine, cfg.target_schema)
        index_mgr: IndexManager | None = None

        # Fases 2-4 dentro del ConstraintManager (enable_all garantizado en __exit__)
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
                else:
                    table_results.extend(self._load_sequential(effective_src_order, src_to_dst, cycle_set, crud))
                # Reflejar en la crud compartida las tablas cargadas para la Fase 5a (PK sync): las cargadas en otros
                # hilos o por rangos de PK (ParallelBulkLoader, con sus propias BulkCrud) no están en su caché. PD-11
                # (2026-09-26): antes solo se hacía con max_parallel_tables > 1 y con rangos no se sincronizaba nada.
                self._reflect_loaded_tables(crud, table_results, src_to_dst)

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
        return table_results, index_mgr, crud, constraint_mgr

    def _load_sequential(
        self, effective_src_order: list[str], src_to_dst: dict[str, str], cycle_set: set[str], crud: BulkCrud
    ) -> list[TableDumpResult]:
        """Carga las tablas secuencialmente."""
        results: list[TableDumpResult] = []
        for position, src_t in enumerate(effective_src_order):
            dst_t = src_to_dst[src_t]
            result = self._process_table(src_t, dst_t, position, src_t in cycle_set, crud)
            results.append(result)
            self.logger.info(
                "  [%d/%d] %s → %s (%d filas)",
                position + 1,
                len(effective_src_order),
                src_t,
                result.status,
                result.target_rows_after,
            )
        return results

    def _safe_summarize_audit(self, bulk_audit_path: Path | None, dump_inicio: datetime) -> DumpAuditSummary | None:
        """Resumen seguro de auditoría (captura errores)."""
        # Resumen de auditoría antes del informe, que lo incluye en la hoja "Auditoría Bulk". Las cargas y sus
        # sesiones de auditoría ya han terminado; la sincronización de PK no audita.
        # El resumen es informativo: un fallo inesperado no debe impedir el informe (la carga ya terminó).
        try:
            return self._summarize_audit(bulk_audit_path, dump_inicio)
        except Exception as exc:
            self.logger.warning("No se pudo resumir la auditoría del volcado: %s", exc, exc_info=True)
            return None

    def _generate_dump_report(
        self,
        dump_result: DumpResult,
        table_results: list[TableDumpResult],
        missing_tables: list[str],
        constraint_results: list[ConstraintResult],
        cycles: list[list[str]],
        index_results: list[IndexActionResult] | None,
        audit_summary: DumpAuditSummary | None,
        pk_sync_results: list[PKSyncResult] | None,
        constraint_reactivation_error: str | None,
        output_dir: Path,
        engine_readiness: list[ReadinessBlock] | None = None,
    ) -> Path:
        """Genera el informe Excel (FASE 5b)."""
        # La hoja "Columnas Inexistentes" se deriva de TableDumpResult.skipped_columns; no requiere comparación de
        # esquemas.
        try:
            return DumpReporter(output_dir).generate(
                table_results=table_results,
                missing_tables=missing_tables,
                constraint_results=constraint_results,
                cycles=cycles,
                index_results=index_results,
                audit_summary=audit_summary,
                pk_sync_results=pk_sync_results,
                constraint_reactivation_error=constraint_reactivation_error,
                engine_readiness=engine_readiness,
            )
        except DumpReportError as exc:
            # Sin esto, un fallo del informe perdía el resultado de una carga ya completada.
            dump_result.report = exc.output_path or output_dir
            exc.result = dump_result
            # Sin traza: la excepción se relanza y la lleva; el llamador la registraría dos veces.
            self.logger.error("Volcado completado, pero sin informe Excel: %s", exc)
            raise

    def _write_dump_events(
        self, writer: DumpAuditWriter, result: DumpResult | None, error: BaseException | None, elapsed_s: float
    ) -> None:
        """Eventos finales del volcado (elementos de ``result`` y ``run`` de cierre) en ``audit_sink``.

        Nunca lanza: ``DumpAuditWriter.write`` construye y escribe dentro de su ``try`` (fallo = ERROR en el log).
        """
        cfg = self._cfg
        run_id = self._audit_run_id

        def build() -> list[AuditEvent]:
            engine = cfg.target_engine.dialect.name
            events = (
                []
                if result is None
                else DumpAuditEvents.result_events(result, engine=engine, namespace=cfg.target_schema, run_id=run_id)
            )
            events.append(
                DumpAuditEvents.run(
                    engine=engine,
                    namespace=cfg.target_schema,
                    run_id=run_id,
                    elapsed_s=elapsed_s,
                    result=result,
                    error=error,
                )
            )
            return events

        writer.write(build)

    def _run_dump(self) -> DumpResult:
        """Cuerpo de :meth:`run` (mismas excepciones)."""
        output_dir, bulk_audit_path, dump_inicio = self._init_dump_run()
        engine_readiness = self._engine_readiness()
        src_tables, dst_lower, missing_in_dst, load_order, cycles = self._analyze_dump_phase()
        src_to_dst, effective_src_order, effective_dst_order = self._compute_load_order(
            src_tables, dst_lower, load_order
        )
        self._prefetch_metadata(effective_src_order, effective_dst_order)
        self._warn_large_batch_with_lobs(effective_dst_order)
        self.logger.info(
            "Volcado: %d tablas origen, %d en destino, %d faltantes, %d ciclos FK.",
            len(src_tables),
            len(effective_src_order),
            len(missing_in_dst),
            len(cycles),
        )
        table_results, index_mgr, crud, constraint_mgr = self._execute_load_phases(
            effective_src_order, effective_dst_order, src_to_dst, cycles, missing_in_dst
        )
        constraint_results: list[ConstraintResult] = constraint_mgr.constraint_results
        constraint_reactivation_error: str | None = constraint_mgr.reactivation_error
        index_results: list[IndexActionResult] | None = index_mgr.index_results if index_mgr is not None else None
        # FASE 5a: Resincronizar contadores PK en destino (si está habilitado)
        pk_sync_results: list[PKSyncResult] | None = self._sync_pk_sequences(
            crud=crud, effective_dst_order=effective_dst_order
        )
        audit_summary = self._safe_summarize_audit(bulk_audit_path, dump_inicio)
        dump_result = DumpResult(
            table_results=table_results,
            constraint_results=constraint_results,
            load_order=load_order,
            cycles_detected=cycles,
            report=output_dir,  # se sustituye por la ruta del informe
            audit_summary=audit_summary,
            pk_sync_results=pk_sync_results,
            index_results=index_results,
            audit_run_id=self._audit_run_id,
            constraint_reactivation_error=constraint_reactivation_error,
        )
        dump_result.report = self._generate_dump_report(
            dump_result,
            table_results,
            missing_in_dst,
            constraint_results,
            cycles,
            index_results,
            audit_summary,
            pk_sync_results,
            constraint_reactivation_error,
            output_dir,
            engine_readiness,
        )
        return dump_result

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
            self.logger.debug("Limpiadas %d tablas con un único TRUNCATE.", len(tables))
            return True
        except SQLAlchemyError as exc:
            conn.rollback()
            self.logger.warning("TRUNCATE conjunto falló (%s); se limpia tabla a tabla.", exc)
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
            self.logger.debug("Limpiada tabla '%s' (%s).", table, "DELETE" if use_delete else "TRUNCATE")
        except SQLAlchemyError as exc:
            conn.rollback()
            if not use_delete and dialect == "mssql":
                self._cleanup_table_delete_fallback(conn, table, quoted)
            else:
                self.logger.warning("Error limpiando tabla '%s': %s", table, exc)

    def _cleanup_table_delete_fallback(self, conn: Any, table: str, quoted: str) -> None:
        """Retry DELETE tras TRUNCATE fallido en SQL Server (FK de esquema externo)."""
        try:
            conn.execute(text(f"DELETE FROM {quoted}"))
            conn.commit()
            self.logger.debug("Limpiada tabla '%s' (DELETE fallback).", table)
        except SQLAlchemyError as exc:
            conn.rollback()
            self.logger.warning("Error limpiando tabla '%s': %s", table, exc)

    def _get_dst_fk_referenced_tables(self, schema: str | None) -> frozenset[str]:
        """Devuelve el conjunto (lowercase) de tablas destino con FK entrantes.

        Sólo se invoca para SQL Server. Permite usar TRUNCATE TABLE en tablas
        sin referencias FK entrantes. Si falla, devuelve frozenset vacío y el
        retry DELETE en _cleanup actúa como safety net.
        """
        try:
            tables = table_names(self._dst_insp, schema)
            referred = DumpOrchestrator._referred_tables(tables, self._dst_insp, schema)
            return frozenset(ref.lower() for refs in referred.values() for ref in refs if ref)
        except SQLAlchemyError:
            self.logger.warning(
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
        pk_range_col = self._detect_pk_range_col(src_table, common_cols) if self._pk_ranges_requested() else None
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
            error_msgs, rows_rejected = self._load_in_pk_ranges(
                src_table,
                common_cols,
                col_name_map,
                pk_range_col,
                dest_table_logical,
                n_ranges,
                crud=crud,
                rows_hint=source_rows,
            )
        else:
            # La BulkCrud se reutiliza entre las tablas del hilo: sus rechazos de esta tabla, por diferencia.
            rejected_before: int = crud.rows_rejected
            error_msgs = self._load_whole_table(src_table, common_cols, col_name_map, dest_table_logical, crud)
            rows_rejected = crud.rows_rejected - rejected_before
        if rows_rejected:
            self.logger.warning(
                "%s: %d filas rechazadas en %s (on_error='isolate')", src_table, rows_rejected, cfg.rejects_csv_path
            )

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
            rows_rejected=rows_rejected,
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
                renamed: Iterator[pd.DataFrame] = (chunk[common_cols].rename(columns=col_name_map) for chunk in chunks)
                write_batch = self._resolve_write_batch_size()
                if write_batch > cfg.chunk_size:
                    renamed = _rebatch(renamed, write_batch)
                try:
                    if cfg.source_engine.dialect.name in _PREFETCH_SOURCE_DIALECTS:
                        renamed = _prefetch(renamed)
                    crud.bulk_insert_from_chunks(renamed, dest_table_logical)
                except (SQLAlchemyError, ValueError, AuditError, OSError) as exc:
                    # AuditError/OSError: con bulk_audit_strict un fallo al escribir la auditoría deshace la tabla;
                    # queda como error de esa tabla, como cualquier otro fallo de carga, y el volcado sigue.
                    error_msgs.append(str(exc))
                finally:
                    # A1 (audit-code 2026-09-26): si la escritura falla, el for de bulk_insert_from_chunks no cierra el
                    # generador; sin esto, el with devolvía la conexión al pool con el hilo de _prefetch aún usándola.
                    # Cerrarlo espera al hilo lector (join) antes de salir del with.
                    close_if_closable(renamed)
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
        *,
        crud: BulkCrud | None = None,
        rows_hint: int | None = None,
    ) -> tuple[list[str], int]:
        """Particiona la tabla por rangos contiguos de ``pk_col`` y los carga en paralelo.

        Devuelve los errores de los rangos y las filas rechazadas (``on_error="isolate"``). Con
        ``parallel_pk_ranges="auto"``, ``n_ranges`` es el tope: el número de rangos lo decide ``ParallelPlanner`` con la
        cota de filas ``MAX − MIN + 1`` (o ``rows_hint``, el ``COUNT(*)`` del origen de ``collect_row_counts``, si es menor:
        con huecos en la PK la cota sobrestima); si sale 1, la tabla se carga entera con ``crud`` (o una ``BulkCrud``
        nueva). ``rows_hint`` negativo o ``None``: sin recuento, solo la cota.

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
            return [f"Error calculando rango PK: {exc}"], 0

        if row[0] is None or row[1] is None:
            return [], 0  # tabla vacía

        lo, hi = int(row[0]), int(row[1])
        if getattr(self, "_auto_pk_ranges", False):
            rows: int = hi - lo + 1
            if rows_hint is not None and rows_hint >= 0:
                rows = min(rows, rows_hint)
            n_ranges = self._plan_pk_ranges(src_table, rows, n_ranges)
            if n_ranges <= 1:
                worker = crud if crud is not None else self._make_worker_crud()
                rejected_before: int = worker.rows_rejected
                errors = self._load_whole_table(src_table, common_cols, col_name_map, dest_table_logical, worker)
                return errors, worker.rows_rejected - rejected_before
        bounds = DumpOrchestrator._compute_range_bounds(lo, hi, n_ranges)
        cols_quoted = ", ".join(quote_identifier(c, cfg.source_engine) for c in common_cols)
        write_batch = self._resolve_write_batch_size()

        def _make_reader(low: int, high: int, is_last: bool) -> Callable[[], Iterator[pd.DataFrame]]:
            op = "<=" if is_last else "<"
            sql = f"SELECT {cols_quoted} FROM {table_quoted} WHERE {pk_q} >= :lo AND {pk_q} {op} :hi"

            def _reader() -> Iterator[pd.DataFrame]:
                with cfg.source_engine.connect() as conn:
                    chunks = (
                        chunk[common_cols].rename(columns=col_name_map)
                        for chunk in _read_chunks(conn, sql, cfg.chunk_size, {"lo": low, "hi": high})
                    )
                    yield from _rebatch(chunks, write_batch) if write_batch > cfg.chunk_size else chunks

            return _reader

        options = self._bulk_options()
        loader = ParallelBulkLoader(
            cfg.target_engine,
            batch=options.batch,
            audit=options.audit,
            rejects=options.rejects,
            execution=options.execution,
            parallel=ParallelOptions(max_workers=n_ranges),
        )
        readers = [_make_reader(lo, hi, last) for lo, hi, last in bounds]
        result = loader.load(dest_table_logical, readers)
        with self._audit_lock:
            self._loader_audit = self._loader_audit + _AuditCounters.of(result)
        return result.partition_errors, result.rows_rejected

    @staticmethod
    def _compute_range_bounds(lo: int, hi: int, n: int) -> list[tuple[int, int, bool]]:
        """Divide [lo, hi] en hasta ``n`` rangos contiguos ``(low, high, is_last)``.

        Para rangos no finales: ``pk >= low AND pk < high`` (high exclusivo). Para el
        último: ``pk >= low AND pk <= hi`` (inclusivo). Sin solapes ni huecos.
        """
        if hi < lo:
            return []
        # Los rangos inclusivos de RangePartitioner, con el límite superior exclusivo salvo en el último (mismo SQL).
        return [
            (low, high, True) if high == hi else (low, high + 1, False)
            for low, high in RangePartitioner.partition_ranges(lo, hi, max(1, n))
        ]

    def _detect_pk_range_col(self, src_table: str, common_cols: list[str]) -> str | None:
        """Devuelve el nombre de la PK si es una única columna entera presente en ``common_cols``.

        Usa el Inspector de origen (no thread-safe): debe invocarse en serie, nunca en hilos.
        ``None`` si no hay PK de columna única entera o no está en las columnas comunes.
        """
        source = self._side_meta("src")
        try:
            pk = source.get("pk", src_table)
        except SQLAlchemyError:
            return None
        cols = pk.get("constrained_columns") or []
        if len(cols) != 1 or cols[0] not in common_cols:
            return None
        pk_col = cols[0]
        try:
            for column in source.get("columns", src_table):
                if column["name"] == pk_col:
                    return pk_col if isinstance(column.get("type"), Integer) else None
        except SQLAlchemyError:
            return None
        return None

    def _pk_ranges_requested(self) -> bool:
        """``True`` si ``parallel_pk_ranges`` pide particionar por rangos de PK (``"auto"`` o un entero > 1)."""
        ranges = self._cfg.parallel_pk_ranges
        return ranges == "auto" or ranges > 1

    def _resolve_range_count(self, requested: int | Literal["auto"], table_workers: int) -> int:
        """Clampa el nº de rangos para que ``table_workers * rangos`` no exceda el pool (1 con destino SQLite).

        Con ``"auto"`` devuelve el tope por tabla (``ParallelOptions().max_workers``, recortado por el pool sin avisar):
        el número de cada tabla lo decide :meth:`_plan_pk_ranges` cuando se conocen sus filas. Si el motor de destino no
        gana con rangos en ningún volumen medido, devuelve 1 (sin el ``MIN/MAX`` de cada tabla) y lo dice una vez (INFO).
        """
        self._auto_pk_ranges = requested == "auto"
        if requested == "auto":
            return self._auto_range_ceiling(table_workers)
        if requested <= 1:
            return 1
        if self._single_writer_target("parallel_pk_ranges", requested):
            return 1
        self._warn_slow_pk_ranges(requested)
        cap = self._known_pool_capacity()
        if cap is not None:
            allowed = max(1, cap // max(table_workers, 1))
            if requested > allowed:
                self.logger.warning(
                    "parallel_pk_ranges=%d con %d tablas en paralelo excede la capacidad del pool (%d); "
                    "se degrada a %d rangos.",
                    requested,
                    table_workers,
                    cap,
                    allowed,
                )
                return allowed
        return requested

    def _auto_range_ceiling(self, table_workers: int) -> int:
        """Tope de rangos por tabla con ``parallel_pk_ranges="auto"``; 1 si el destino no gana con rangos (ver arriba)."""
        dialect: str = self._cfg.target_engine.dialect.name
        if dialect in SINGLE_WRITER_DIALECTS:
            return 1
        rule = ParallelPlanner.rule("source", dialect, "insert")
        if rule is None or rule.workers <= 1:
            reason = "sin medición" if rule is None else rule.evidence
            self.logger.info("parallel_pk_ranges='auto' con destino %s: sin rangos de PK (%s).", dialect, reason)
            return 1
        ceiling = ParallelOptions().max_workers
        cap = self._known_pool_capacity()
        return ceiling if cap is None else max(1, min(ceiling, cap // max(table_workers, 1)))

    def _known_pool_capacity(self) -> int | None:
        """Menor capacidad conocida de los pools de origen y destino (``size + max_overflow``), o ``None``."""
        capacities = [
            DumpOrchestrator._pool_capacity(self._cfg.source_engine),
            DumpOrchestrator._pool_capacity(self._cfg.target_engine),
        ]
        known = [c for c in capacities if c is not None and c > 0]
        return min(known) if known else None

    def _plan_pk_ranges(self, src_table: str, rows: int, ceiling: int) -> int:
        """Rangos de PK de una tabla con ``parallel_pk_ranges="auto"`` (``ParallelPlanner``, cada hilo lee del origen).

        ``rows`` son las filas del origen (``COUNT(*)``) o, sin recuento, la cota ``MAX − MIN + 1``. El motivo va al log.
        """
        plan = ParallelPlanner.plan(
            PlanInput(
                dialect=self._cfg.target_engine.dialect.name,
                operation="insert",
                options=ParallelOptions(mode="auto", max_workers=max(1, ceiling)),
                rows=rows,
                workload="source",
            )
        )
        self.logger.info(
            "%s: %d rango(s) de PK (parallel_pk_ranges='auto', %d filas): %s",
            src_table,
            plan.workers,
            rows,
            "; ".join(plan.reasons),
        )
        return plan.workers

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
                    self.logger.info(
                        "  (par) %s → %s (%d filas)", futures[future], result.status, result.target_rows_after
                    )

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
                self.logger.info("  (ciclo) %s → %s (%d filas)", src_t, result.status, result.target_rows_after)

        results.sort(key=lambda r: r.load_order_position)
        return results

    def _precompute_table_meta(
        self, src_table: str, dst_table: str
    ) -> tuple[list[str], list[str], dict[str, str], str | None]:
        """Calcula en serie (Inspector no thread-safe) columnas comunes + PK de rango."""
        common_cols, skipped_cols, col_name_map = self._common_columns(src_table, dst_table)
        pk_col = self._detect_pk_range_col(src_table, common_cols) if self._pk_ranges_requested() else None
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
                self.logger.debug("No se pudo reflejar '%s' para PK sync: %s", dest_logical, exc)

    def _make_worker_crud(self) -> BulkCrud:
        """Crea una ``BulkCrud`` del volcado (la principal o una dedicada por hilo).

        La auditoría es concurrente-segura: ``AuditCsvRepository`` serializa las
        escrituras al mismo CSV mediante un lock por-ruta, por lo que cada worker
        puede registrar inserts en ``bulk_audit_path`` sin intercalar filas. La instancia
        queda registrada para sumar sus contadores de auditoría al resumen del volcado.
        """
        # run() avisa una vez por volcado de la auditoría deshabilitada (for_worker quita el aviso de cada BulkCrud).
        options = self._bulk_options()
        crud = BulkCrud(self._cfg.target_engine, **options.for_worker(run_id=options.audit.run_id).as_kwargs())
        with self._audit_lock:
            self._audit_cruds.append(crud)
        return crud

    def _bulk_options(self) -> BulkOptions:
        """Opciones comunes de las ``BulkCrud`` y los ``ParallelBulkLoader`` del volcado (R15: antes repetidas en los dos).

        v3.0.0: único punto de traducción de los campos planos de ``DumpConfig`` a los paquetes de ``bulk``.
        """
        cfg = self._cfg
        return BulkOptions(
            batch=BatchOptions(
                chunk_size=self._resolve_write_batch_size(), commit_every_n_chunks=cfg.commit_every_n_chunks
            ),
            # F5 (sesión 2026-10-02c): eventos de auditoría con el run_id del volcado.
            audit=AuditOptions(
                csv_path=cfg.bulk_audit_path,
                strict=cfg.bulk_audit_strict,
                sink=cfg.audit_sink,
                run_id=getattr(self, "_audit_run_id", None),  # tests que crean la instancia sin __init__
            ),
            # Fase 4 (sesión 2026-10-01u): filas que el destino no admite, al CSV de rechazos.
            rejects=RejectOptions(on_error=cfg.on_error, csv_path=cfg.rejects_csv_path, max_rejects=cfg.max_rejects),
            # PD-05: copia fiel del origen; Q9: bulk no usa las FK de la tabla destino.
            execution=ExecutionOptions(strip_strings=False, reflect_foreign_keys=False),
        )

    def _resolve_write_batch_size(self) -> int:
        """Filas por lote de escritura: ``write_batch_size`` si se fijó; si no, 20 000 con destino PostgreSQL (sin
        ``commit_every_n_chunks``, para no cambiar cada cuántas filas se confirma) y ``chunk_size`` en el resto (Q5).

        Refactor v0.30.1: lógica centralizada en _core.batching.resolve_write_batch_size() (motor-específico).
        """
        cfg = self._cfg
        if cfg.write_batch_size is not None:
            return cfg.write_batch_size
        return resolve_write_batch_size(
            db_type=None,
            chunk_size=cfg.chunk_size,
            commit_every_n_chunks=cfg.commit_every_n_chunks,
            target_engine=cfg.target_engine,
        )

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
            start_offset=self._audit_offset_if_same_file(audit_path),
        )

    def _audit_offset_if_same_file(self, audit_path: Path | None) -> int | None:
        """Desplazamiento de inicio del CSV, o ``None`` (leerlo entero) si ya no es el mismo fichero.

        Si el CSV tenía una cabecera no válida, la primera escritura lo aparta y crea otro con la misma ruta: el tamaño
        del inicio no sirve para el nuevo, que puede crecer más y hacer que se leyera desde mitad de sus filas.
        """
        offset: int | None = getattr(self, "_audit_start_offset", None)
        if offset is None:
            return None
        if DumpOrchestrator._file_identity(audit_path) != getattr(self, "_audit_start_identity", None):
            return None
        return offset

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
                self.logger.warning(
                    "max_parallel_tables=%d excede la capacidad del pool (%d); se degrada a %d. "
                    "Aumenta pool_size/max_overflow para mayor paralelismo.",
                    requested,
                    cap,
                    cap,
                )
                return cap
        return requested

    def _warn_slow_pk_ranges(self, requested: int) -> None:
        """Avisa si ``parallel_pk_ranges > 1`` con destino MySQL/MariaDB, donde la carga por rangos es más lenta.

        Q4 (performance-audit de dump 2026-09-26): a 3,5M filas, 4 rangos tardan +84 % a +94 % frente a la carga
        secuencial (que solapa lectura y escritura), también con 2 y 4 GB de redo log. No se fuerza a 1: es más lento, no
        incorrecto.
        """
        dialect = self._cfg.target_engine.dialect.name
        if dialect not in MYSQL_FAMILY:
            return
        self.logger.warning(
            "parallel_pk_ranges=%d con destino %s: la carga por rangos de PK es más lenta que la secuencial en este "
            "motor (medido: casi el doble de tiempo a 3,5M filas). Se recomienda parallel_pk_ranges=1.",
            requested,
            dialect,
        )

    def _single_writer_target(self, option: str, requested: int) -> bool:
        """``True`` (con WARNING) si el destino admite un solo escritor a la vez (SQLite) y se pidió paralelismo.

        PD-06 (performance-audit de dump 2026-09-25): con destino SQLite, las particiones o tablas en paralelo chocaban
        con ``database is locked``; la tabla quedaba en ``error`` y a medio cargar (1,5M de 2M filas con 4 rangos).
        """
        if self._cfg.target_engine.dialect.name not in SINGLE_WRITER_DIALECTS:
            return False
        self.logger.warning(
            "%s=%d no se aplica con destino SQLite (admite un solo escritor a la vez); se carga sin paralelismo.",
            option,
            requested,
        )
        return True

    @staticmethod
    def _pool_capacity(engine: Engine) -> int | None:
        """Capacidad del pool (``size + max_overflow``) o ``None`` si no es determinable (:func:`pool_capacity`)."""
        return pool_capacity(engine)

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
            self.logger.debug("PK sync: no hay tablas en caché para sincronizar (load vacío).")
            return None

        results = crud.sync_pk_sequences(tables)

        synced = sum(1 for r in results if r.status == "synced")
        no_rows = sum(1 for r in results if r.status == "no_rows")
        skipped = sum(1 for r in results if r.status == "skipped")
        unsupported = sum(1 for r in results if r.status == "unsupported")
        errors = sum(1 for r in results if r.status == "error")

        self.logger.info(
            "Fase 5a (PK sync): synced=%d, no_rows=%d, skipped=%d, unsupported=%d, errors=%d",
            synced,
            no_rows,
            skipped,
            unsupported,
            errors,
        )
        for r in results:
            if r.status == "error":
                self.logger.warning("  PK sync error %s.%s: %s", r.table_name, r.column_name, r.error_msg)

        return results or None

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _get_source_tables(self) -> list[str]:
        if self._cfg.tables is not None:
            return sorted(self._cfg.tables)
        return table_names(self._src_insp, self._cfg.source_schema)

    def _side_meta(self, side: str) -> TableMetadata:
        """Metadatos precargados de un lado (``"src"``/``"dst"``) o, sin precarga, consulta tabla a tabla."""
        meta = self._src_meta if side == "src" else self._dst_meta
        if meta is not None:
            return meta
        if side == "src":
            return TableMetadata(self._src_insp, self._cfg.source_schema)
        return TableMetadata(self._dst_insp, self._cfg.target_schema)

    def _prefetch_metadata(self, src_tables: list[str], dst_tables: list[str]) -> None:
        """Columnas y PK de origen y columnas de destino de todas las tablas del volcado, por lotes (D2).

        Antes, cada tabla consultaba sus columnas en origen y destino (y su PK con ``parallel_pk_ranges``). Lo que
        no se pueda precargar se consulta tabla a tabla al pedirlo, con el mismo error que antes.
        """
        cfg = self._cfg
        src_kinds: list[MetadataKind] = ["columns", "pk"] if self._pk_ranges_requested() else ["columns"]
        try:
            self._src_meta = prefetch_table_metadata(self._src_insp, cfg.source_schema, src_tables, kinds=src_kinds)
            self._dst_meta = prefetch_table_metadata(self._dst_insp, cfg.target_schema, dst_tables, kinds=["columns"])
        except SQLAlchemyError as exc:
            self.logger.debug("Precarga de metadatos fallida (%s); se consultan tabla a tabla.", exc)

    def _common_columns(self, src_table: str, dst_table: str) -> tuple[list[str], list[str], dict[str, str]]:
        """Retorna (columnas_comunes_origen, columnas_omitidas, mapa_origen→destino).

        El mapa permite renombrar el DataFrame antes del INSERT cuando la BD
        destino tiene el mismo nombre de columna en distinto case (p.ej. origen
        ``UserID`` → destino ``userid`` en una BD case-sensitive).
        Acepta nombres distintos para origen (``src_table``) y destino (``dst_table``)
        para soportar motores con diferente sensibilidad a mayúsculas.
        """
        src = [c["name"] for c in self._side_meta("src").get("columns", src_table)]
        dst_by_lower = {c["name"].lower(): c["name"] for c in self._side_meta("dst").get("columns", dst_table)}
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
            # SQLAlchemy 2.1: un text() sin columnas tipadas infiere un resultado sin tipo y mypy pide la anotación.
            val: Any = result.scalar_one()
            return int(val) if val is not None else 0

    _build_fk_graph = staticmethod(_fk_graph.build_fk_graph)

    _referred_tables = staticmethod(_fk_graph.referred_tables)

    _topological_levels = staticmethod(_fk_graph.topological_levels)

    _topological_sort = staticmethod(_fk_graph.topological_sort)

    _find_cycle_components = staticmethod(_fk_graph.find_cycle_components)

    _build_cycle_adj = staticmethod(_fk_graph.build_cycle_adj)

    _bfs_component = staticmethod(_fk_graph.bfs_component)

    _file_size = staticmethod(_audit_summary.file_size)

    _file_identity = staticmethod(_audit_summary.file_identity)

    _read_audit_csv = staticmethod(_audit_summary.read_audit_csv)

    _build_audit_summary = staticmethod(_audit_summary.build_audit_summary)

    @staticmethod
    def _warn_sqlite_source(source: Engine, target: Engine) -> None:
        """Advierte de un origen SQLite: sin tipos, fechas y DECIMAL no llegan como ``datetime``/``Decimal``.

        PD-07 (performance-audit de dump 2026-09-25): SQLite no tiene tipos de columna, así que el driver entrega las
        fechas como texto y los DECIMAL como ``float``. Un destino servidor convierte el texto; un destino SQLite rechaza
        las fechas como texto (``SQLite DateTime type only accepts Python datetime…``) y los DECIMAL pierden precisión.
        """
        if source.dialect.name != "sqlite":
            return
        DumpOrchestrator.logger.warning(
            "Origen SQLite: las fechas se leen como texto y los DECIMAL como float (SQLite no tiene tipos de columna). "
            "Con destino SQLite, las tablas con columnas de fecha fallarán; los DECIMAL pueden perder precisión."
            if target.dialect.name == "sqlite"
            else "Origen SQLite: las fechas se leen como texto (el destino las convierte) y los DECIMAL como float "
            "(pueden perder precisión), porque SQLite no tiene tipos de columna."
        )

    def _warn_large_batch_with_lobs(self, dst_tables: list[str]) -> None:
        """Advierte si el lote de escritura es alto para MariaDB/MySQL y alguna tabla destino tiene columnas LOB/JSON.

        Filas con TEXT/BLOB/JSON extensos pueden producir paquetes INSERT que superen ``max_allowed_packet`` del
        servidor (16 MB por defecto en MariaDB antiguas), con ``Lost connection to server during query`` (error 2013).
        Paso 2.3 del roadmap de dump (2026-09-26): antes se avisaba en todos los volcados a estos motores, aunque ninguna
        tabla tuviera esas columnas (sin ellas, lotes de 5000 no dieron errores).
        """
        engine = self._cfg.target_engine
        if engine.dialect.name not in MYSQL_FAMILY:
            return
        batch = self._resolve_write_batch_size()
        if batch <= 1000:
            return
        lob_tables: list[str] = []
        for table in dst_tables:
            try:
                columns = self._side_meta("dst").get("columns", table)
            except SQLAlchemyError:
                continue
            if any(isinstance(col["type"], (sqltypes.Text, sqltypes.LargeBinary, sqltypes.JSON)) for col in columns):
                lob_tables.append(table)
        if not lob_tables:
            return
        self.logger.warning(
            "Lote de escritura de %d filas con destino %s y columnas TEXT/BLOB/JSON en %s: puede causar 'Lost "
            "connection to server during query' (max_allowed_packet excedido). Considera write_batch_size=500 o menos, "
            "o aumentar max_allowed_packet en el servidor.",
            batch,
            engine.dialect.name,
            ", ".join(lob_tables[:5]) + (f" y {len(lob_tables) - 5} más" if len(lob_tables) > 5 else ""),
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
        if engine.dialect.name not in MYSQL_FAMILY:
            return
        pre_ping: bool = getattr(engine.pool, "_pre_ping", False)
        if not pre_ping:
            DumpOrchestrator.logger.warning(
                "El engine destino (%s) no tiene pool_pre_ping=True. "
                "Crea el engine con create_engine(url, pool_pre_ping=True, pool_recycle=3600) "
                "o usa SyncDatabaseManager.get_sqlalchemy_engine().",
                engine.dialect.name,
            )
        recycle: int = getattr(engine.pool, "_recycle", -1)
        if recycle < 0:
            DumpOrchestrator.logger.warning(
                "El engine destino (%s) no tiene pool_recycle configurado. "
                "Sin rotación de conexiones, 'Server has gone away' puede ocurrir en volcados largos. "
                "Añade pool_recycle=3600 al create_engine() o usa SyncDatabaseManager.get_sqlalchemy_engine().",
                engine.dialect.name,
            )
