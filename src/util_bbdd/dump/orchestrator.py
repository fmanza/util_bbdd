"""Orquestador de volcado de datos entre esquemas/bases de datos.

Punto de entrada público: ``DumpOrchestrator(config).run() → DumpResult``.

Flujo (6 fases):
  1. Inspección: introspección de origen y destino + comparación de esquemas.
  2. Análisis: orden de carga topológico (FK), tablas faltantes.
  3. Desactivación de constraints en destino.
  4. Limpieza del destino (si ``truncate_target=True``).
  5. Carga de datos (best-effort, continúa ante errores).
  6. Rehabilitación de constraints + generación del informe Excel.
"""

from __future__ import annotations

import logging

from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from sqlalchemy import Engine, Inspector, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk.audit import AuditManager
from util_bbdd.comparar import SchemaComparator, SchemaDiff

from ._constraints import ConstraintManager, ConstraintResult
from ._models import DumpAuditSummary, DumpConfig, DumpResult, TableDumpResult
from ._sql_utils import quote_identifier, quote_table
from .reporters import DumpReporter

_log = logging.getLogger(__name__)

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

    def __init__(self, config: DumpConfig) -> None:
        self._cfg = config
        self._src_insp: Inspector = inspect(config.source_engine)
        self._dst_insp: Inspector = inspect(config.target_engine)
        self._warn_pool_config(config.target_engine)
        self._warn_chunk_size(config.target_engine, config.chunk_size)

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def run(self) -> DumpResult:
        """Ejecuta el volcado completo y retorna el resultado con el informe."""
        cfg = self._cfg
        dump_inicio = datetime.now()

        # FASE 1: Inspección y comparación de esquemas
        diff: SchemaDiff = SchemaComparator().compare(
            self._src_insp,
            self._dst_insp,
            source_schema=cfg.source_schema,
            target_schema=cfg.target_schema,
            include_routines=False,
        )

        # FASE 2: Análisis de carga
        src_tables = self._get_source_tables()
        _dst_names = self._dst_insp.get_table_names(schema=cfg.target_schema)
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

        # Fases 3-6: dentro del ConstraintManager (enable_all garantizado en __exit__)
        table_results: list[TableDumpResult] = []
        constraint_mgr = ConstraintManager(cfg.target_engine, cfg.target_schema)

        with constraint_mgr:
            # FASE 3: Deshabilitar constraints (usando nombres canónicos del destino)
            constraint_mgr.disable_all(tables=effective_dst_order)

            # FASE 4: Limpieza del destino (usando nombres canónicos del destino)
            if cfg.truncate_target:
                self._cleanup(list(reversed(effective_dst_order)), skip=set(missing_in_dst))

            # FASE 5: Carga (best-effort)
            cycle_set = {t for group in cycles for t in group}
            crud = BulkCrud(cfg.target_engine, chunk_size=cfg.chunk_size, audit_csv_path=cfg.bulk_audit_path)
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

        # FASE 6b: Generar informe Excel
        report_path = DumpReporter(cfg.output_dir).generate(
            table_results=table_results,
            missing_tables=missing_in_dst,
            diff=diff,
            constraint_results=constraint_results,
            cycles=cycles,
        )

        return DumpResult(
            table_results=table_results,
            constraint_results=constraint_results,
            load_order=load_order,
            cycles_detected=cycles,
            report=report_path,
            audit_summary=DumpOrchestrator._build_audit_summary(cfg.bulk_audit_path, dump_inicio),
        )

    # ------------------------------------------------------------------
    # Fase 4: Limpieza del destino
    # ------------------------------------------------------------------

    def _cleanup(self, reversed_order: list[str], skip: set[str]) -> None:
        """Borra o trunca las tablas destino antes de cargar.

        Para SQL Server: TRUNCATE TABLE en tablas sin FK entrantes (instantáneo)
        y DELETE FROM en las referenciadas. Si TRUNCATE falla (FK de esquema
        externo no detectada), reintenta con DELETE via ``_cleanup_table``.
        Para otros motores: TRUNCATE TABLE siempre.
        """
        cfg = self._cfg
        dialect = cfg.target_engine.dialect.name
        mssql_referenced: frozenset[str] = (
            self._get_dst_fk_referenced_tables(cfg.target_schema) if dialect == "mssql" else frozenset()
        )
        with cfg.target_engine.connect() as conn:
            for table in reversed_order:
                if table in skip:
                    continue
                use_delete = dialect == "mssql" and table.lower() in mssql_referenced
                self._cleanup_table(conn, table, cfg.target_schema, use_delete, dialect)

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
    # Fase 5: Carga de tabla individual
    # ------------------------------------------------------------------

    def _process_table(self, src_table: str, dst_table: str, position: int, in_cycle: bool, crud: BulkCrud) -> TableDumpResult:
        cfg = self._cfg
        common_cols, skipped_cols, col_name_map = self._common_columns(src_table, dst_table)

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

        cols_quoted = ", ".join(quote_identifier(c, cfg.source_engine) for c in common_cols)
        table_quoted = quote_table(src_table, cfg.source_schema, cfg.source_engine)
        sql = f"SELECT {cols_quoted} FROM {table_quoted}"

        # bulk_insert_from_df → reflect_table espera nombre lógico sin quoting de dialecto
        # (schema.tabla o solo tabla). quote_table genera backticks/corchetes que reflect_table
        # no puede procesar, pues los pasa literalmente a SQLAlchemy Table().
        dest_table_logical = f"{cfg.target_schema}.{dst_table}" if cfg.target_schema else dst_table
        error_msgs: list[str] = []

        try:
            with cfg.source_engine.connect() as conn:
                chunks = pd.read_sql(text(sql), conn, chunksize=cfg.chunk_size)
                try:
                    with crud.bulk_session():
                        for chunk in chunks:
                            df_filtered = chunk[common_cols].rename(columns=col_name_map)
                            crud.bulk_insert_from_df(df_filtered, dest_table_logical, generar_sql=False)
                except (SQLAlchemyError, ValueError) as exc:
                    error_msgs.append(str(exc))
        except (SQLAlchemyError, ValueError, pd.errors.DatabaseError) as exc:
            error_msgs.append(f"Error leyendo origen: {exc}")

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
    def _build_audit_summary(audit_path: Path | None, desde: datetime) -> DumpAuditSummary | None:
        """Lee el CSV de auditoría y extrae métricas del volcado actual.

        Filtra por ``timestamp >= desde`` para aislar las entradas de este volcado
        frente a operaciones previas que pudieran existir en el mismo CSV.
        Devuelve ``None`` si la ruta no está configurada, el fichero no existe o no
        hay entradas en el rango temporal.
        """
        if audit_path is None or not audit_path.exists():
            return None
        try:
            mgr = AuditManager(audit_path, cache_enabled=False)
            df = mgr.leer_auditoria()
        except Exception as exc:
            _log.warning("No se pudo leer el CSV de auditoría '%s': %s", audit_path, exc)
            return None
        if df.empty:
            return None
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df[df["timestamp"] >= pd.Timestamp(desde)]
        if df.empty:
            return None
        tabla_mas_activa: str | None = str(df["tabla"].value_counts().index[0]) if len(df) > 0 else None
        return DumpAuditSummary(
            total_operaciones=int(len(df)),
            total_filas=int(df["total_filas"].sum()),
            tiempo_total_seg=round(float(df["tiempo_seg"].sum()), 3),
            tiempo_promedio_seg=round(float(df["tiempo_seg"].mean()), 3),
            tablas_auditadas=int(df["tabla"].nunique()),
            tabla_mas_activa=tabla_mas_activa,
            audit_path=audit_path,
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
