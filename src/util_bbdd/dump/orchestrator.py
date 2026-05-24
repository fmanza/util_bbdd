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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from sqlalchemy import Engine, Inspector, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk import bulk_crud
from util_bbdd.comparar import SchemaComparator, SchemaDiff

from ._constraints import ConstraintManager, ConstraintResult

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos públicos
# ---------------------------------------------------------------------------


@dataclass
class DumpConfig:
    """Configuración de un volcado de datos de esquema/BD origen a destino.

    Args:
        source_engine: Engine SQLAlchemy del esquema origen (lectura).
        target_engine: Engine SQLAlchemy del esquema destino (escritura).
        source_schema: Nombre del schema origen; ``None`` usa el default del engine.
        target_schema: Nombre del schema destino; ``None`` usa el default del engine.
        tables: Tablas a volcar. ``None`` = todas las tablas del origen.
        chunk_size: Filas por chunk tanto en lectura como en bulk insert.
        output_dir: Directorio donde guardar el informe Excel.
        truncate_target: ``True`` (default) = limpiar tablas destino antes de cargar.
            Recomendado para volcados completos. ``False`` = modo append.
    """

    source_engine: Engine
    target_engine: Engine
    source_schema: str | None = None
    target_schema: str | None = None
    tables: list[str] | None = None
    chunk_size: int = 5000
    output_dir: Path = field(default_factory=Path)
    truncate_target: bool = True


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


# ---------------------------------------------------------------------------
# Helpers de quoting e identificadores
# ---------------------------------------------------------------------------


def _qi(name: str, engine: Engine) -> str:
    """Quoted identifier según el dialect del engine."""
    return engine.dialect.identifier_preparer.quote(name)


def _qt(table: str, schema: str | None, engine: Engine) -> str:
    """Tabla quoted con prefijo de schema opcional."""
    if schema:
        return f"{_qi(schema, engine)}.{_qi(table, engine)}"
    return _qi(table, engine)


def _count_rows(engine: Engine, table: str, schema: str | None) -> int:
    quoted = _qt(table, schema, engine)
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
        val = result.scalar_one()
        return int(val) if val is not None else 0


# ---------------------------------------------------------------------------
# Sort topológico (Kahn)
# ---------------------------------------------------------------------------


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
    dependents, in_degree = _build_fk_graph(tables, inspector, schema)

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
    cycles: list[list[str]] = [cycle_tables] if cycle_tables else []

    return ordered + cycle_tables, cycles


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

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def run(self) -> DumpResult:
        """Ejecuta el volcado completo y retorna el resultado con el informe."""
        cfg = self._cfg

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
        dst_tables_set = set(self._dst_insp.get_table_names(schema=cfg.target_schema))
        missing_in_dst: list[str] = [t for t in src_tables if t not in dst_tables_set]

        load_order, cycles = _topological_sort(src_tables, self._src_insp, cfg.source_schema)
        # Tablas que existen en destino, en el orden topológico calculado
        effective_order: list[str] = [t for t in load_order if t in dst_tables_set]

        _log.info(
            "Volcado: %d tablas origen, %d en destino, %d faltantes, %d ciclos FK.",
            len(src_tables),
            len(effective_order),
            len(missing_in_dst),
            len(cycles),
        )

        # Fases 3-6: dentro del ConstraintManager (enable_all garantizado en __exit__)
        table_results: list[TableDumpResult] = []
        constraint_mgr = ConstraintManager(cfg.target_engine, cfg.target_schema)

        with constraint_mgr:
            # FASE 3: Deshabilitar constraints
            constraint_mgr.disable_all(tables=effective_order)

            # FASE 4: Limpieza del destino
            if cfg.truncate_target:
                self._cleanup(list(reversed(effective_order)), skip=set(missing_in_dst))

            # FASE 5: Carga (best-effort)
            cycle_set = {t for group in cycles for t in group}
            for position, table in enumerate(effective_order):
                result = self._process_table(table, position, table in cycle_set)
                table_results.append(result)
                _log.info(
                    "  [%d/%d] %s → %s (%d filas)",
                    position + 1,
                    len(effective_order),
                    table,
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

        constraint_results = constraint_mgr.constraint_results

        # FASE 6b: Generar informe Excel
        from .reporters import DumpReporter  # import local para evitar ciclo

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
        )

    # ------------------------------------------------------------------
    # Fase 4: Limpieza del destino
    # ------------------------------------------------------------------

    def _cleanup(self, reversed_order: list[str], skip: set[str]) -> None:
        """Borra o trunca las tablas destino antes de cargar.

        SQL Server usa DELETE (TRUNCATE no funciona con FKs catalogadas aunque
        estén desactivadas). Otros motores usan TRUNCATE TABLE.
        """
        cfg = self._cfg
        dialect = cfg.target_engine.dialect.name
        use_delete = dialect == "mssql"

        with cfg.target_engine.connect() as conn:
            for table in reversed_order:
                if table in skip:
                    continue
                quoted = _qt(table, cfg.target_schema, cfg.target_engine)
                sql = f"DELETE FROM {quoted}" if use_delete else f"TRUNCATE TABLE {quoted}"
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    _log.debug("Limpiada tabla '%s'.", table)
                except SQLAlchemyError as exc:
                    conn.rollback()
                    _log.warning("Error limpiando tabla '%s': %s", table, exc)

    # ------------------------------------------------------------------
    # Fase 5: Carga de tabla individual
    # ------------------------------------------------------------------

    def _process_table(self, table: str, position: int, in_cycle: bool) -> TableDumpResult:
        cfg = self._cfg
        common_cols, skipped_cols = self._common_columns(table)

        if not common_cols:
            return TableDumpResult(
                table_name=table,
                source_rows=self._safe_count(cfg.source_engine, table, cfg.source_schema),
                target_rows_before=self._safe_count(cfg.target_engine, table, cfg.target_schema),
                target_rows_after=self._safe_count(cfg.target_engine, table, cfg.target_schema),
                status="skipped",
                skipped_columns=skipped_cols,
                load_order_position=position,
                in_cycle=in_cycle,
            )

        source_rows = self._safe_count(cfg.source_engine, table, cfg.source_schema)
        target_rows_before = self._safe_count(cfg.target_engine, table, cfg.target_schema)

        cols_quoted = ", ".join(_qi(c, cfg.source_engine) for c in common_cols)
        table_quoted = _qt(table, cfg.source_schema, cfg.source_engine)
        sql = f"SELECT {cols_quoted} FROM {table_quoted}"

        crud = bulk_crud(cfg.target_engine, chunk_size=cfg.chunk_size)
        error_msgs: list[str] = []

        try:
            with cfg.source_engine.connect() as conn:
                chunks = pd.read_sql(text(sql), conn, chunksize=cfg.chunk_size)
                for chunk in chunks:
                    df_filtered = chunk[common_cols]
                    try:
                        crud.bulk_insert_from_df(df_filtered, table, generar_sql=False)
                    except (SQLAlchemyError, ValueError) as exc:
                        error_msgs.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            error_msgs.append(f"Error leyendo origen: {exc}")

        target_rows_after = self._safe_count(cfg.target_engine, table, cfg.target_schema)
        status: Literal["success", "error"] = "error" if error_msgs else "success"

        return TableDumpResult(
            table_name=table,
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
            return list(self._cfg.tables)
        return self._src_insp.get_table_names(schema=self._cfg.source_schema)

    def _common_columns(self, table: str) -> tuple[list[str], list[str]]:
        """Retorna (columnas_comunes, columnas_omitidas) en el case del origen."""
        src = [c["name"] for c in self._src_insp.get_columns(table, schema=self._cfg.source_schema)]
        dst_lower = {c["name"].lower() for c in self._dst_insp.get_columns(table, schema=self._cfg.target_schema)}
        common = [name for name in src if name.lower() in dst_lower]
        skipped = [name for name in src if name.lower() not in dst_lower]
        return common, skipped

    def _safe_count(self, engine: Engine, table: str, schema: str | None) -> int:
        try:
            return _count_rows(engine, table, schema)
        except SQLAlchemyError:
            return -1
