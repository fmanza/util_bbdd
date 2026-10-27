"""
Módulo para operaciones CRUD en lote desde DataFrames de pandas.

bulk_crud proporciona operaciones de INSERT, UPDATE y DELETE en lote
compatible con SQLAlchemy para múltiples tipos de bases de datos:
- Oracle (identifiers minúsculos)
- MySQL/MariaDB (identifiers mayúsculos)
- PostgreSQL (identifiers minúsculos)
- SQLite (identifiers minúsculos)
- SQL Server (identifiers mayúsculos, pymssql + pyodbc)
- HSQLDB (identifiers mayúsculos)
Compatible con SyncDatabaseManager para integración simplificada.
"""

from __future__ import annotations

import logging
import math
import uuid
import warnings

from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from sqlalchemy import (
    JSON,
    Column,
    ColumnElement,
    Engine,
    Insert,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    Update,
    and_,
    bindparam,
    insert,
    update,
)
from sqlalchemy.exc import SQLAlchemyError

from .._core.exceptions import ParallelLoadError
from .._core.timing import medir_tiempo
from .._core.validation import StrPath
from ..audit.counters import AuditCounters
from ..connection.performance_advisor import EngineReadinessAdvisor
from ..metadata import facts as catalog_facts
from ..metadata.catalog_registry import CatalogDialectNotFoundError
from ..metadata.model import Kind
from ..metadata.reflection import reflect_table
from ..metadata.source import CatalogSource
from ._execution.batch import (
    STAGING_UPDATE_DIALECTS,
    BatchStatementExecutor,
    DeleteBatchExecutor,
    StagingUpdateStrategy,
)
from ._execution.executors import batch_failure_note
from ._execution.maintenance import TableMaintenance
from ._execution.parallel_planner import ParallelPlan, ParallelPlanner, PlanInput
from ._execution.range_partitioner import HashPartitioner, RangePartitioner
from ._execution.session import SessionScope
from ._models import MaintenanceScopeResult, PKSyncResult
from ._support import oracle_batch_errors
from ._support.batch_sizes import DEFAULT_CHUNK_SIZE, BulkOperation, resolve_batch_sizes
from ._support.dialect import (
    MYSQL_FAMILY,
)
from ._support.iterables import closing_iterable
from ._support.persistence import BulkPersistenceManager
from ._support.pk_sync import PKSequenceSyncer
from ._support.pool import pool_capacity
from ._support.prefetch import prefetch
from ._support.rejects import (
    REJECTS_FAILURE_NOTE,
    Isolator,
    RejectsCoordinator,
    RejectsWriter,
)
from ._support.secondary_indexes import IndexMode, resolve_index_mode
from ._support.sql_helpers import (
    SqlColumns,
    build_override_identity_text_stmt,
    generate_delete_sql,
    generate_insert_sql,
    generate_insert_sql_override_identity,
    generate_update_sql,
    iter_identity_insert_sql,
    json_passthrough_binds,
    restore_binary_values,
    should_wrap_identity_insert,
)
from ._support.table_utils import get_column_case_insensitive, get_max_column_value
from ._support.validation import (
    UpdatePlan,
    align_dataframe_columns,
    build_update_plan,
    detect_always_identity_columns,
    get_insert_columns,
    get_pk_columns,
    normalize_dataframe_columns,
    normalize_identifier,
    validate_engine,
)
from .audit import AuditError, AuditManager
from .normalize import dataframe_to_sql_columns, dataframe_to_sql_records
from .options import AuditOptions, BatchOptions, BulkOptions, ExecutionOptions, ParallelOptions, RejectOptions

if TYPE_CHECKING:
    from ._execution.parallel_loader import ParallelLoadResult


@dataclass(frozen=True, slots=True)
class _PreparedBulkOperation:
    """Resultado de preparar una operación bulk concreta."""

    rowcount: int
    generate_sql_lines: Callable[[], Iterable[str]]  # por bloques (P-07): se consume una vez, al escribir
    execute: Callable[[], None]


@dataclass(frozen=True, slots=True)
class _BulkOperationStrategy:
    """Estrategia de preparación para una operación bulk."""

    operation_name: str
    prepare: Callable[[pd.DataFrame, str], _PreparedBulkOperation]


@dataclass(frozen=True, slots=True)
class _StreamPosition:
    """Chunk en curso de una vía ``*_from_chunks`` (notas de error y cadencia del DELETE, B-08)."""

    chunk: int
    row_offset: int
    first: bool


#: Tipos LOB: el UPDATE con alguno de ellos aísla por bisección y no con ``batcherrors`` (S-5, ORA-03106).
_LOB_TYPES: tuple[type, ...] = (Text, LargeBinary, JSON)

#: Longitud a partir de la cual un ``String`` se trata como LOB en esa regla: con ``MAX_STRING_SIZE=EXTENDED`` un
#: ``VARCHAR2(32767)`` admite valores de más de 8000 caracteres, que oracledb enlaza como cadena larga, el caso del
#: ORA-03106 (B-2, audit-code 2026-10-01; sesión 2026-10-01y).
_LOB_LIKE_STRING_LENGTH: int = 4000


def _lob_like(column_type: Any) -> bool:
    """``True`` si ``column_type`` es LOB o un ``String`` de más de 4000 caracteres (regla del ORA-03106 de S-5)."""
    if isinstance(column_type, _LOB_TYPES):
        return True
    length = getattr(column_type, "length", None) if isinstance(column_type, String) else None
    return length is not None and length > _LOB_LIKE_STRING_LENGTH


def _resolve_generar_sql(method: str, generar_sql: bool | None, dry_run: bool | None) -> bool:
    """``generar_sql`` efectivo de un ``bulk_*_from_df`` a partir de ``generar_sql`` y ``dry_run`` (G35 de util_bbdd_web).

    Sin ninguno de los dos, ``True`` (el valor por defecto de siempre) con un ``FutureWarning`` dirigido a quien llama:
    en 5.0.0 el valor por defecto pasará a ejecutar.

    Raises:
        ValueError: Si se pasan los dos con valores distintos.
    """
    if dry_run is None:
        if generar_sql is not None:
            return generar_sql
        # stacklevel: este helper, el método, el wrapper de medir_tiempo y quien llama.
        warnings.warn(
            f"BulkCrud.{method}: sin generar_sql ni dry_run se escribe el SQL y no se ejecuta (generar_sql=True). "
            "En 5.0.0 el valor por defecto será ejecutar: pasa dry_run=True para generar el SQL o generar_sql=False "
            "para ejecutar.",
            FutureWarning,
            stacklevel=4,
        )
        return True
    if generar_sql is not None and generar_sql != dry_run:
        raise ValueError(
            f"BulkCrud.{method}: generar_sql={generar_sql} y dry_run={dry_run} se contradicen; pasa solo uno de los dos."
        )
    return dry_run


class BulkCrud:
    """Realiza operaciones CRUD en lote sobre bases de datos usando SQLAlchemy."""

    def __init__(
        self,
        engine: Engine | None,
        *,
        batch: BatchOptions | None = None,
        audit: AuditOptions | None = None,
        rejects: RejectOptions | None = None,
        execution: ExecutionOptions | None = None,
        parallel: ParallelOptions | None = None,
    ):
        """
        Constructor de ``BulkCrud``.

        v3.0.0: las opciones llegan en paquetes inmutables (:mod:`util_bbdd.bulk.options`), validados al construirse.
        Hasta v2.x eran 16 parámetros sueltos; equivalencias en ``docs/guides/api_3_0_migration.md``.

        Args:
            engine: Engine de SQLAlchemy para las operaciones. Obligatorio.
            batch: Tamaño de lote, ``commit_every_n_chunks`` y ``prefetch_blocks`` (:class:`BatchOptions`). ``None``: el
                lote por motor y operación (B-04), una transacción por operación, sin preparación anticipada.

                ``commit_every_n_chunks`` es **crítico para MariaDB/MySQL en cargas masivas** (millones de filas): sin él
                el undo log crece linealmente y el buffer pool se satura. Valores orientativos (mide en tu entorno):

                | BD | Buffer Pool | Recomendado | Aprox. Filas/commit |
                |---|---|---|---|
                | MariaDB 8.0 | 256 MB | 10 | 50 K |
                | MariaDB 8.0 | 1 GB | 20 | 100 K |
                | MariaDB 8.0 | 4 GB+ | 50 | 250 K |
                | MySQL 8.0 | 1 GB | 20 | 100 K |

                **Ejemplo de tuning** (10M filas en MariaDB con 1 GB buffer pool)::

                    bulk = BulkCrud(engine, batch=BatchOptions(chunk_size=5_000, commit_every_n_chunks=20))
                    bulk.bulk_insert_from_df(df_10m, "tabla_destino", generar_sql=False)
                    # Commitea cada 20 × 5_000 = 100 K filas → undo log limitado

                Con la cadencia la sesión deja de ser atómica: un fallo a mitad deja confirmados los lotes anteriores.
            audit: CSV de auditoría, política de fallo (``strict``), destino de eventos (``sink``) y ``run_id``
                (:class:`AuditOptions`). ``None``: sin auditoría (con un WARNING una vez).
            rejects: ``on_error="isolate"`` aparta las filas con errores de datos (PK duplicada, FK, valor demasiado
                largo...) a un CSV y aplica el resto (:class:`RejectOptions`). Coste (INSERT de 1M filas): sin filas
                malas 1,00–1,02×; 10 filas malas 1,13–1,23× (PostgreSQL 1,65×). Solo operaciones ejecutadas (no
                ``generar_sql``). Ver :attr:`rows_rejected` (S-2). ``None``: un error de datos hace fallar la operación.
            execution: ``fast_executemany`` (SQL Server + pyodbc), ``insert_resolver``, ``update_via_staging``
                (MySQL/MariaDB ~12,5×, PostgreSQL 2,35×), ``strip_strings`` y ``reflect_foreign_keys``
                (:class:`ExecutionOptions`). ``None``: los valores por defecto.
            parallel: Ejecución paralela de ``bulk_*_from_df`` (:class:`ParallelOptions`): el DataFrame se reparte en
                particiones disjuntas que carga ``ParallelBulkLoader``, cada una en su hilo y su transacción. ``None``
                (default): en serie y atómica, como siempre. Con ``mode="auto"`` decide los hilos
                :class:`~util_bbdd.bulk.ParallelPlanner` (en serie donde el paralelismo no gana o no se ha medido). Ver
                :meth:`bulk_insert_from_df` y :attr:`last_parallel_result`.

        Raises:
            ValueError: Si engine es None. Los paquetes validan sus valores al construirse (``ValueError``).
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        options = BulkOptions.of(batch=batch, audit=audit, rejects=rejects, execution=execution, parallel=parallel)
        #: Paquetes recibidos (v3.0.0); los workers de una carga paralela se crean con ``options.for_worker``.
        self._options: BulkOptions = options
        # A5 (v1.1.0): escritor, presupuesto, ámbito y aislador de on_error="isolate" en RejectsCoordinator.
        # Las lambdas resuelven reflect_table y __batch_errors en cada llamada, como cuando vivían aquí.
        rejects_path: Path | None = options.rejects.csv_path
        self._rejects: RejectsCoordinator = RejectsCoordinator(
            writer=None if rejects_path is None else RejectsWriter(rejects_path),
            max_rejects=options.rejects.max_rejects,
            reflect_table=lambda tabla_destino: self.reflect_table(tabla_destino),
            batch_errors=lambda: self.__batch_errors(),
            attach=self.__attach_isolator,
            logger=self.logger,
        )

        self.engine: Engine = validate_engine(engine)
        self._table_cache: dict[str, Table] = {}

        commit_every_n_chunks: int | None = options.batch.commit_every_n_chunks
        explicit_chunk_size: int | None = options.batch.chunk_size
        #: Lote base: el ``chunk_size`` explícito o 5000. Lo usa la generación de SQL (``generar_sql=True``).
        self.chunk_size: int = DEFAULT_CHUNK_SIZE if explicit_chunk_size is None else explicit_chunk_size
        # B-04: filas por lote de cada operación (por motor si no se fijó chunk_size).
        self._batch_sizes: dict[BulkOperation, int] = resolve_batch_sizes(
            self.engine.dialect.name, explicit_chunk_size, commit_every_n_chunks
        )
        audit_options: AuditOptions = options.audit
        # Con audit.sink la auditoría no está deshabilitada aunque no haya CSV: no se avisa.
        self.audit_manager: AuditManager = AuditManager(
            audit_options.csv_path,
            warn_if_disabled=audit_options.warn_if_disabled and audit_options.sink is None,
            engine=self.engine,
        )
        # Sin destino no hay eventos ni run_id, como en ParallelBulkLoader (audit-code 2026-10-02c, 3).
        self._audit_run_id: str | None = (
            None if audit_options.sink is None else (audit_options.run_id or uuid.uuid4().hex)
        )
        execution_options: ExecutionOptions = options.execution
        # Estado de la instancia, no del paquete: se apaga si falta el privilegio (ver __execute_update_blocks).
        self._update_via_staging: bool = (
            execution_options.update_via_staging and self.engine.dialect.name in STAGING_UPDATE_DIALECTS
        )
        self._strip_strings: bool = execution_options.strip_strings
        self._reflect_foreign_keys: bool = execution_options.reflect_foreign_keys
        self._prefetch_blocks: bool = options.batch.prefetch_blocks
        #: Resultado de la última carga paralela de un ``bulk_*_from_df`` (None si no hubo).
        self._last_parallel_result: ParallelLoadResult | None = None
        #: Contadores de auditoría y rechazos de las cargas paralelas (los de sus workers), sumados a los propios.
        self._parallel_audit: AuditCounters = AuditCounters()
        self._parallel_rows_rejected: int = 0
        #: Privilegio TEMP de PostgreSQL para el plan del UPDATE paralelo (None: sin comprobar).
        self._temp_tables_allowed: bool | None = None

        # Inicializar db_info
        self.db_info: str = self.engine.dialect.name.upper()

        # Detectar driver específico para SQL Server
        self.__detectar_sqlserver_driver()

        # Verificar condiciones de ejecución para todos los motores
        self.__validate_engine_config()

        self._persistence: BulkPersistenceManager = BulkPersistenceManager(
            engine_url=str(self.engine.url),
            logger=self.logger,
            audit_manager=self.audit_manager,
            db_info=self.db_info,
            audit_strict=audit_options.strict,
            audit_sink=audit_options.sink,
            audit_run_id=self._audit_run_id,
            engine_name=self.engine.dialect.name,
        )
        # Conexión de bulk_session() y gancho de commit, compartidos por los dos ejecutores (R14).
        self._session: SessionScope = SessionScope()
        self._batch_statement_executor: BatchStatementExecutor = BatchStatementExecutor(
            engine=self.engine,
            # INSERT y UPDATE le llegan ya en bloques de su tamaño; el ejecutor no debe trocearlos más.
            chunk_size=max(self._batch_sizes["insert"], self._batch_sizes["update"]),
            enable_fast_executemany=execution_options.fast_executemany,
            insert_resolver=execution_options.insert_resolver,
            commit_every_n_chunks=commit_every_n_chunks,
            session=self._session,
        )
        self._delete_batch_executor: DeleteBatchExecutor = DeleteBatchExecutor(
            engine=self.engine,
            chunk_size=self._batch_sizes["delete"],
            commit_every_n_chunks=commit_every_n_chunks,
            session=self._session,
        )
        #: Chunk en curso de bulk_update_from_chunks / bulk_delete_from_chunks (None fuera de ellas).
        self._stream: _StreamPosition | None = None
        #: Estrategias de UPDATE por staging reutilizadas en la instancia: PostgreSQL comprueba TEMP una sola vez.
        self._staging_strategies: dict[tuple[int, tuple[str, ...], tuple[str, ...]], StagingUpdateStrategy] = {}
        # INSERT no entra en este dict porque requiere kwargs extra (override_identity,
        # exclude_autoincrement_pk) que la interfaz Callable[[df, tabla], ...] no soporta.
        self._operation_strategies: dict[Literal["update", "delete"], _BulkOperationStrategy] = {
            "update": _BulkOperationStrategy(
                operation_name="UPDATE",
                prepare=self.__prepare_update_operation,
            ),
            "delete": _BulkOperationStrategy(
                operation_name="DELETE",
                prepare=self.__prepare_delete_operation,
            ),
        }

    def __detectar_sqlserver_driver(self) -> None:
        """Detecta el driver específico de SQL Server (pymssql o pyodbc) y actualiza db_info."""
        sqlserver_driver: str = ""
        if self.engine.dialect.name == "mssql":
            driver_name: str = str(self.engine.url.drivername).lower()
            if "pymssql" in driver_name:
                sqlserver_driver = "pymssql"
            elif "pyodbc" in driver_name:
                sqlserver_driver = "pyodbc"
            else:
                sqlserver_driver = "mssql"  # Dialecto genérico
            # Actualizar db_info con el driver específico
            self.db_info = f"MSSQL ({sqlserver_driver})"
            self.logger.debug(f"🟢 Driver SQL Server detectado: {sqlserver_driver}")
            if sqlserver_driver == "pymssql":
                # P-17 (performance-audit de bulk): con pymssql el INSERT/UPDATE masivo va a ~2.700/~1.800 filas/s;
                # pyodbc + ODBC Driver 17/18 con fast_executemany, a ~49.000/~33.500. La carga nativa bulk_copy de
                # pymssql se descartó: no aplica CHECK ni claves foráneas y las marca como no confiables.
                self.logger.info(
                    "SQL Server con pymssql: para cargas masivas, mssql+pyodbc con ODBC Driver 17/18 es ~15× más "
                    "rápido en INSERT/UPDATE (ver docs/guides/benchmarks.md)."
                )

    def __validate_engine_config(self) -> None:
        """Verifica las condiciones de ejecución del motor una vez por engine (``EngineReadinessAdvisor.report_once``)."""
        EngineReadinessAdvisor().report_once(self.engine)

    def __validar_y_generar_path_sql(self, path_sql: StrPath | None, tabla_destino: str, operacion: str) -> Path:
        """
        Valida path_sql y genera el nombre dinámico combinado con la ruta proporcionada.

        Args:
            path_sql: Ruta base donde guardar el archivo SQL.
            tabla_destino: Nombre de la tabla.
            operacion: Tipo de operación (insert, update, delete).

        Returns:
            Path completa con el nombre dinámico.

        Raises:
            ValueError: Si path_sql es None o no es una ruta (``str`` o ``Path``).
        """
        return self._persistence.resolve_sql_output_path(path_sql, tabla_destino, operacion)

    @medir_tiempo()
    def bulk_insert_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool | None = None,
        path_sql: StrPath | None = None,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
        *,
        dry_run: bool | None = None,
    ) -> None:
        """
        Inserta en bloque los datos del DataFrame en la tabla destino, o genera la SQL si se indica.

        Args:
            df: DataFrame con los datos.
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Si True, genera la sentencia SQL en texto y no ejecuta nada; si False, ejecuta. ``None``
                (default): como ``True``, con un ``FutureWarning`` si tampoco se pasa ``dry_run``, porque en 5.0.0 el
                valor por defecto será ejecutar (G35 de util_bbdd_web, v4.5.0). Pásalo siempre explícito.
            path_sql: Directorio (``str`` o ``Path``) del archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.
            override_identity: Si True y el motor es PostgreSQL, genera INSERT con
                     OVERRIDING SYSTEM VALUE para columnas GENERATED ALWAYS AS IDENTITY.
                     Ignorado en otros motores. Por defecto False.
            exclude_autoincrement_pk: Si True, excluye la columna PK autoincremental/identity
                     del INSERT (tanto en ejecución como en generación SQL). El DataFrame original
                     no se modifica. Solo afecta a INSERT; no a UPDATE ni DELETE. Por defecto False.
            dry_run: Nombre explícito del modo seco (v4.5.0): ``True`` equivale a ``generar_sql=True`` (escribe el SQL
                en ``path_sql`` y no toca la BD) y ``False`` a ``generar_sql=False``.

        Raises:
            ValueError: Si generar_sql y dry_run se pasan con valores distintos.
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.
            ValueError: Si el DataFrame es vacío o si hay errores de SQL.
            ValueError: Si override_identity=False y el DataFrame incluye columnas
                     GENERATED ALWAYS AS IDENTITY en PostgreSQL.

        La operación se registra en auditoría si fue configurada.

        Con ``parallel`` (:class:`ParallelOptions`) y ``generar_sql=False``, fuera de una :meth:`bulk_session`, si el plan
        (:meth:`parallel_plan`) da más de un hilo el DataFrame se reparte en particiones consecutivas que inserta
        ``ParallelBulkLoader``, una transacción por partición: **deja de ser atómica**. Si alguna partición falla, lanza
        ``ParallelLoadError`` (las demás quedan confirmadas); el resultado queda en :attr:`last_parallel_result`.
        ``parallel_plan("insert", len(df)).atomic`` lo dice antes de cargar; ``ParallelOptions(require_atomic=True)``
        fuerza un hilo.
        """
        generar_sql = _resolve_generar_sql("bulk_insert_from_df", generar_sql, dry_run)
        if self.__run_in_parallel(
            df,
            tabla_destino,
            "insert",
            generar_sql,
            override_identity=override_identity,
            exclude_autoincrement_pk=exclude_autoincrement_pk,
        ):
            return
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="insert",
            override_identity=override_identity,
            exclude_autoincrement_pk=exclude_autoincrement_pk,
        )

    @medir_tiempo()
    def bulk_update_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool | None = None,
        path_sql: StrPath | None = None,
        *,
        dry_run: bool | None = None,
    ) -> None:
        """
        Actualiza en bloque los registros del DataFrame en la tabla destino.

        Args:
            df: DataFrame con los datos a actualizar.
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Como en :meth:`bulk_insert_from_df` (``None``: ``True`` con ``FutureWarning``, G35).
            path_sql: Directorio (``str`` o ``Path``) del archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.
            dry_run: Como en :meth:`bulk_insert_from_df` (v4.5.0).

        Raises:
            ValueError: Si no hay claves primarias o columnas actualizables.
            ValueError: Si generar_sql y dry_run se pasan con valores distintos.
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.

        La operación se registra en auditoría si fue configurada. Con ``parallel``, como :meth:`bulk_insert_from_df`; las
        particiones son disjuntas por PK (o por ``ParallelOptions.partition_column``).
        """
        generar_sql = _resolve_generar_sql("bulk_update_from_df", generar_sql, dry_run)
        if self.__run_in_parallel(df, tabla_destino, "update", generar_sql):
            return
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="update",
        )

    @medir_tiempo()
    def bulk_delete_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool | None = None,
        path_sql: StrPath | None = None,
        *,
        dry_run: bool | None = None,
    ) -> None:
        """
        Borra en bloque registros del DataFrame desde la tabla destino.

        Args:
            df: DataFrame con los datos a borrar (debe contener claves primarias).
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Como en :meth:`bulk_insert_from_df` (``None``: ``True`` con ``FutureWarning``, G35).
            path_sql: Directorio (``str`` o ``Path``) del archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.
            dry_run: Como en :meth:`bulk_insert_from_df` (v4.5.0).

        Raises:
            ValueError: Si no hay columnas de clave primaria disponibles.
            ValueError: Si generar_sql y dry_run se pasan con valores distintos.
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.

        La operación se registra en auditoría si fue configurada. Con ``parallel``, como :meth:`bulk_update_from_df`.
        """
        generar_sql = _resolve_generar_sql("bulk_delete_from_df", generar_sql, dry_run)
        if self.__run_in_parallel(df, tabla_destino, "delete", generar_sql):
            return
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="delete",
        )

    @medir_tiempo()
    def bulk_insert_from_chunks(
        self,
        chunks: Iterable[pd.DataFrame],
        tabla_destino: str,
        *,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> int:
        """Inserta en streaming una secuencia de DataFrames en la tabla destino.

        Pensado para cargas de gran volumen sin materializar todo el dataset en memoria
        (p.ej. consumiendo ``pandas.read_sql(..., chunksize=N)``). A diferencia de llamar
        repetidamente a :meth:`bulk_insert_from_df`, resuelve las columnas de inserción y
        la estrategia de identidad **una sola vez** (a partir del primer chunk no vacío),
        evitando la re-resolución por chunk. Todos los chunks se insertan dentro de un
        único :meth:`bulk_session` (atómico, salvo que se construya la instancia con
        ``commit_every_n_chunks``).

        Solo ejecuta (no genera SQL). El esquema de columnas debe ser **homogéneo** entre
        chunks (invariante natural de ``pandas.read_sql(chunksize=...)``). No debe llamarse
        dentro de un ``bulk_session`` ya abierto: gestiona su propia transacción.

        Args:
            chunks: Iterable de DataFrames con el mismo conjunto de columnas.
            tabla_destino: Nombre de la tabla destino (``schema.tabla`` o ``tabla``).
            override_identity: Igual que en :meth:`bulk_insert_from_df` (PostgreSQL).
            exclude_autoincrement_pk: Excluye la PK autoincremental/identity del INSERT.

        Returns:
            Número total de filas insertadas.

        Raises:
            ValueError: Si hay columnas GENERATED ALWAYS AS IDENTITY (PostgreSQL) y
                ``override_identity=False``.
            SQLAlchemyError: Ante errores SQL durante la inserción.
        """
        self.__ensure_no_open_session("bulk_insert_from_chunks")
        tabla: Table = self.reflect_table(tabla_destino)
        total: int = 0
        resolved: tuple[Any, list[str]] | None = None
        self._session.rows.start_operation()  # B-11: last_operation_rows_committed cuenta todo el stream

        with self._rejects.operation(tabla_destino, "INSERT") as isolated, self.bulk_session():
            for chunk_index, chunk in enumerate(chunks):
                working_df: pd.DataFrame = chunk.copy(deep=False)
                self.__actualizar_df(working_df, tabla)
                if working_df.empty:
                    continue
                if resolved is None:
                    resolved = self.__resolve_stream_insert(
                        working_df,
                        tabla,
                        override_identity=override_identity,
                        exclude_autoincrement_pk=exclude_autoincrement_pk,
                    )
                stmt, insert_cols = resolved

                numero_registros: int = len(working_df)
                isolated.rows = total + numero_registros  # B-4: filas recibidas, también si este chunk falla
                rejected_before: int = self._rejects.rejected_so_far()
                size: int = self._batch_sizes["insert"]
                start: float = perf_counter()
                with batch_failure_note("INSERT", tabla.fullname, chunk_index, total, numero_registros):
                    if isinstance(stmt, Insert) and self._batch_statement_executor.supports_columns:
                        # B-03: tuplas desde las columnas, sin un dict por fila; lotes de chunk_size como el ejecutor.
                        sql_source = self.__sql_blocks(working_df[insert_cols], tabla, size)
                        with closing_iterable(self.__prefetched(sql_source)) as sql_items:
                            for index, block in enumerate(sql_items):
                                self.__ejecutar_batch_stmt(block, stmt, len(block), total + index * size)
                    else:
                        record_source = self.__record_blocks(working_df[insert_cols], tabla, size)
                        with closing_iterable(self.__prefetched(record_source)) as record_items:
                            for index, records_sql in enumerate(record_items):
                                self.__ejecutar_batch_stmt(records_sql, stmt, len(records_sql), total + index * size)
                elapsed: float = perf_counter() - start
                total += numero_registros

                self._persistence.register_operation(
                    table_name=tabla_destino,
                    operation="INSERT",
                    # S-2: con on_error="isolate", las filas aplicadas (las rechazadas no están en la BD).
                    rowcount=numero_registros - (self._rejects.rejected_so_far() - rejected_before),
                    elapsed=elapsed,
                    generated_sql=False,
                )

        self.logger.info(f"✅ bulk INSERT (chunks) finalizado: {total} filas ({self.db_info}).")
        return total

    @medir_tiempo()
    def bulk_update_from_chunks(self, chunks: Iterable[pd.DataFrame], tabla_destino: str) -> int:
        """Actualiza en streaming con una secuencia de DataFrames, sin materializar todo el dataset en memoria (B-08).

        Equivale a :meth:`bulk_update_from_df` con cada chunk, todos dentro de un único :meth:`bulk_session` (atómico,
        salvo que la instancia tenga ``commit_every_n_chunks``, cuya cadencia sigue de un chunk al siguiente). Consume el
        iterable de forma perezosa (no lee el chunk siguiente hasta escribir el actual) y lo cierra al terminar, también
        si falla. Cada chunk se audita como una operación. Con ``commit_every_n_chunks``, si falla a mitad,
        :attr:`last_operation_rows_committed` dice cuántas filas de la secuencia quedaron confirmadas.

        No debe llamarse dentro de un ``bulk_session`` ya abierto: gestiona su propia transacción.

        Args:
            chunks: Iterable de DataFrames con la PK y las columnas a actualizar.
            tabla_destino: Nombre de la tabla destino (``schema.tabla`` o ``tabla``).

        Returns:
            Número total de filas enviadas.
        """
        return self.__stream_operation(chunks, tabla_destino, "update")

    @medir_tiempo()
    def bulk_delete_from_chunks(self, chunks: Iterable[pd.DataFrame], tabla_destino: str) -> int:
        """Borra en streaming las filas cuyas PK llegan en una secuencia de DataFrames (B-08).

        Como :meth:`bulk_update_from_chunks`, con :meth:`bulk_delete_from_df` en cada chunk.

        Args:
            chunks: Iterable de DataFrames con las columnas de la PK.
            tabla_destino: Nombre de la tabla destino (``schema.tabla`` o ``tabla``).

        Returns:
            Número total de filas enviadas.
        """
        return self.__stream_operation(chunks, tabla_destino, "delete")

    def __stream_operation(
        self, chunks: Iterable[pd.DataFrame], tabla_destino: str, strategy_key: Literal["update", "delete"]
    ) -> int:
        """Ejecuta ``strategy_key`` chunk a chunk en una sesión; una sola operación en el libro de filas (B-11)."""
        self.__ensure_no_open_session(f"bulk_{strategy_key}_from_chunks")
        # Reflejar antes de abrir la sesión: un worker de ParallelBulkLoader no pide una segunda conexión mientras
        # retiene la de la sesión (regla size + max_overflow).
        self.reflect_table(tabla_destino)
        self._session.rows.start_operation()
        total: int = 0
        first: bool = True
        operation: str = strategy_key.upper()
        with (
            closing_iterable(chunks) as items,
            self._rejects.operation(tabla_destino, operation) as isolated,
            self.bulk_session(),
        ):
            for chunk_index, chunk in enumerate(items):
                if chunk.empty:
                    continue
                self._stream = _StreamPosition(chunk=chunk_index, row_offset=total, first=first)
                isolated.rows = total + len(chunk)  # B-4: filas recibidas, también si este chunk falla
                try:
                    self.__run_bulk_pipeline(
                        df=chunk,
                        tabla_destino=tabla_destino,
                        generar_sql=False,
                        path_sql=None,
                        strategy_key=strategy_key,
                    )
                finally:
                    self._stream = None
                first = False
                total += len(chunk)
        self.logger.info(f"✅ bulk {strategy_key.upper()} (chunks) finalizado: {total} filas ({self.db_info}).")
        return total

    def __prefetched[T](self, blocks: Iterator[T]) -> Iterator[T]:
        """``blocks`` preparados en un hilo con ``prefetch_blocks`` (S-4); si no, tal cual.

        Quien consume debe recorrerlos dentro de ``closing_iterable``: si el envío falla, cerrar el generador espera al
        hilo (``prefetch`` hace ``join`` en su ``finally``) en lugar de dejarlo preparando bloques hasta el GC.
        """
        return prefetch(blocks) if self._prefetch_blocks else blocks

    def __ensure_no_open_session(self, method: str) -> None:
        """``RuntimeError`` si hay una ``bulk_session`` abierta (A3, audit-code 2026-10-01).

        Las vías ``*_from_chunks`` abren su propia sesión: dentro de otra pedían una segunda conexión (en SQLite,
        ``database is locked``) y al salir dejaban la sesión externa sin conexión, así que lo que viniera después dejaba de
        ser atómico con ella.
        """
        if self._session.active:
            raise RuntimeError(
                f"{method} gestiona su propia transacción y no puede llamarse dentro de bulk_session(): ciérrala antes, "
                "o usa bulk_insert_from_df / bulk_update_from_df / bulk_delete_from_df por chunk dentro de la sesión."
            )

    def __batch_note(
        self, operation: BulkOperation, tabla: Table, index: int, rows: int
    ) -> AbstractContextManager[None]:
        """Nota de error del lote ``index`` (B-15a), con la posición en la secuencia si es un ``*_from_chunks``."""
        chunk = None if self._stream is None else self._stream.chunk
        return batch_failure_note(
            operation.upper(), tabla.fullname, index, self.__first_row(operation, index), rows, chunk
        )

    def __first_row(self, operation: BulkOperation, index: int) -> int:
        """Posición en la entrada (o en la secuencia de un ``*_from_chunks``) de la primera fila del lote ``index``."""
        offset: int = 0 if self._stream is None else self._stream.row_offset
        return offset + index * self._batch_sizes[operation]

    @contextmanager
    def rejects_scope(self, *, partition: int | None = None, row_offset: int = 0) -> Generator[None, None, None]:
        """Agrupa varias operaciones en una sola secuencia de entrada para los rechazos (``on_error="isolate"``).

        Dentro del bloque, las operaciones comparten un presupuesto de ``max_rejects`` y la columna ``fila`` del CSV de
        rechazos es la posición en la secuencia: ``row_offset`` + filas de las operaciones anteriores del bloque +
        posición dentro de la operación. ``partition`` va a la columna ``particion``. Pensado para cargar por chunks
        dentro de :meth:`bulk_session` (cada ``bulk_*_from_df`` es una operación) o para reanudar una secuencia
        (``row_offset`` = filas ya confirmadas). ``ParallelBulkLoader`` envuelve así cada intento de cada partición.
        Sin ``on_error="isolate"`` no hace nada. Cada operación avanza la posición con todas las filas que recibió,
        también si falla: el DataFrame entero de un ``*_from_df``, o los chunks leídos (incluido el que falló) de un
        ``*_from_chunks`` (B-4, audit-code 2026-10-02).

        Args:
            partition: Valor de la columna ``particion`` del CSV de rechazos (``None``: vacía).
            row_offset: Posición (base 0) de la primera fila de la primera operación del bloque.

        Raises:
            ValueError: Si ``row_offset`` no es un entero ≥ 0 o ``partition`` no es ``None`` ni un entero ≥ 0 (también
                de numpy).
            RuntimeError: Si ya hay un ``rejects_scope`` abierto en la instancia.

        Examples:
            >>> with crud.bulk_session(), crud.rejects_scope():
            ...     for chunk in pd.read_csv("datos.csv", chunksize=50_000):
            ...         crud.bulk_insert_from_df(chunk, "items", generar_sql=False)
        """
        with self._rejects.scope(partition=partition, row_offset=row_offset):
            yield

    def __batch_errors(self) -> bool:
        """``True`` si se aíslan filas con ``batcherrors`` (Oracle con oracledb, S-5); registra el listener una vez."""
        if not oracle_batch_errors.supports(self.engine) or not isinstance(self.engine, Engine):
            return False
        oracle_batch_errors.install(self.engine)
        return True

    def __attach_isolator(self, isolator: Isolator | None) -> None:
        """Engancha a los dos ejecutores el aislador de la operación en curso (``None`` al terminar)."""
        self._batch_statement_executor.isolator = isolator
        self._delete_batch_executor.isolator = isolator

    def __resolve_stream_insert(
        self,
        df: pd.DataFrame,
        tabla: Table,
        *,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
    ) -> tuple[Any, list[str]]:
        """Resuelve (stmt_de_ejecución, columnas_de_inserción) para la carga en streaming.

        Misma resolución que ``__prepare_insert_operation`` (``__insert_columns``), sin la rama de generación de SQL,
        que no aplica al streaming.
        """
        insert_cols, override = self.__insert_columns(
            df, tabla, override_identity=override_identity, exclude_autoincrement_pk=exclude_autoincrement_pk
        )
        if override:
            stmt: Any = build_override_identity_text_stmt(tabla, insert_cols, self.engine.dialect)
        else:
            stmt = self.__insert_stmt(tabla, insert_cols)
        return stmt, insert_cols

    def __insert_columns(
        self,
        df: pd.DataFrame,
        tabla: Table,
        *,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
    ) -> tuple[list[str], bool]:
        """Columnas de inserción y si hay que usar ``OVERRIDING SYSTEM VALUE`` (común a streaming y a ``prepare``).

        Raises:
            ValueError: Si hay columnas ``GENERATED ALWAYS AS IDENTITY`` (PostgreSQL) y ``override_identity=False``.
        """
        insert_cols: list[str] = get_insert_columns(
            list(df.columns), tabla, exclude_autoincrement_pk=exclude_autoincrement_pk
        )
        is_postgres: bool = self.engine.dialect.name == "postgresql"
        always_identity_cols: list[str] = detect_always_identity_columns(insert_cols, tabla) if is_postgres else []

        if always_identity_cols and not override_identity:
            raise ValueError(
                f"❌ Las columnas {always_identity_cols} son GENERATED ALWAYS AS IDENTITY en PostgreSQL. "
                "Usa override_identity=True para insertar valores manuales."
            )
        return insert_cols, bool(override_identity and always_identity_cols)

    def parallel_plan(self, operation: Literal["insert", "update", "delete"], rows: int) -> ParallelPlan:
        """Plan de ejecución de un ``bulk_*_from_df`` de ``rows`` filas con las ``ParallelOptions`` de la instancia.

        Lo decide :class:`~util_bbdd.bulk.ParallelPlanner` con el motor, la operación, ``rows`` y la capacidad del pool;
        ``plan.reasons`` explica la decisión. Sin ``parallel`` en el constructor, en serie. En el UPDATE de PostgreSQL
        comprueba (una vez por instancia, solo si el plan es paralelo) el privilegio ``TEMP``.

        ``plan.atomic`` (v4.5.0, G36 de util_bbdd_web) dice si la operación irá en una sola transacción: ``False`` con
        más de un hilo (una transacción por partición) o con ``commit_every_n_chunks``. ``ParallelOptions(
        require_atomic=True)`` fuerza un hilo. Es el plan de una operación fuera de :meth:`bulk_session` (dentro va
        siempre en serie, en la transacción de la sesión) y con ``generar_sql=False``.

        Args:
            operation: ``"insert"``, ``"update"`` o ``"delete"``.
            rows: Número de filas de la operación.

        Returns:
            ``ParallelPlan`` con el número de hilos (``workers``), los motivos (``reasons``) y ``atomic``.

        Examples:
            >>> crud = BulkCrud(engine, parallel=ParallelOptions(mode="auto"))  # doctest: +SKIP
            >>> crud.parallel_plan("insert", 2_000_000).reasons  # doctest: +SKIP
            ('INSERT en mssql: INSERT 50K-1M: 2,4-2,8× con 4 hilos',)
        """
        options = self._options.parallel
        periodic_commits: bool = self._options.batch.commit_every_n_chunks is not None
        if options is None:
            return ParallelPlan(1, ("sin ParallelOptions: en serie",), atomic=not periodic_commits)
        dialect: str = self.engine.dialect.name
        plan_input = PlanInput(
            dialect=dialect,
            operation=operation,
            options=options,
            rows=rows,
            pool_capacity=pool_capacity(self.engine),
            staging_update=self._update_via_staging,
            periodic_commits=periodic_commits,
        )
        plan = ParallelPlanner.plan(plan_input)
        if plan.parallel and operation == "update" and dialect == "postgresql" and self._update_via_staging:
            if not self.__temp_tables_allowed():
                plan = ParallelPlanner.plan(replace(plan_input, staging_update=False))
        return plan

    def __temp_tables_allowed(self) -> bool:
        """``True`` si la sesión puede crear tablas temporales (PostgreSQL, privilegio ``TEMP``); cacheado."""
        if self._temp_tables_allowed is None:
            with self.engine.connect() as conn:
                self._temp_tables_allowed = catalog_facts.can_create_temp_tables(conn)
        return self._temp_tables_allowed

    def __run_in_parallel(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        operation: Literal["insert", "update", "delete"],
        generar_sql: bool,
        *,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> bool:
        """Hace la operación con ``ParallelBulkLoader`` si hay ``parallel`` y el plan da más de un hilo.

        Devuelve ``False`` (sigue en serie) con ``generar_sql``, dentro de una :meth:`bulk_session` (los hilos usan otras
        conexiones: la carga no sería atómica con la sesión), de un ``*_from_chunks`` o de un :meth:`rejects_scope` (las
        particiones tienen su propio presupuesto y sus posiciones; no continuarían la secuencia del ámbito), si el plan es
        en serie, o si en UPDATE/DELETE no se encuentran en el DataFrame las columnas de la PK (la vía en serie da su
        error habitual).

        Raises:
            ParallelLoadError: Si alguna partición falló (las demás quedan confirmadas).
        """
        if self._options.parallel is None or generar_sql or df.empty:
            return False
        if self._session.active or self._stream is not None or self._rejects.scope_active:
            self.logger.debug(
                f"bulk {operation.upper()} en serie: dentro de bulk_session(), de un *_from_chunks o de rejects_scope()."
            )
            return False
        plan = self.parallel_plan(operation, len(df))
        if not plan.parallel:
            self.logger.debug(f"bulk {operation.upper()} de {len(df)} filas en serie: {'; '.join(plan.reasons)}")
            return False
        partitions = self.__partitions(df, tabla_destino, operation, plan.workers)
        if partitions is None:
            return False
        self.logger.info(
            f"▶️  bulk {operation.upper()} de {len(df)} filas → {tabla_destino} en {len(partitions)} particiones "
            f"paralelas ({self.db_info}): {'; '.join(plan.reasons) or 'ParallelOptions'}."
        )
        self.__load_partitions(
            partitions,
            tabla_destino,
            operation,
            plan.workers,
            override_identity=override_identity,
            exclude_autoincrement_pk=exclude_autoincrement_pk,
        )
        return True

    def __partitions(
        self, df: pd.DataFrame, tabla_destino: str, operation: Literal["insert", "update", "delete"], n: int
    ) -> list[pd.DataFrame] | None:
        """``df`` en ``n`` particiones disjuntas; ``None`` si en UPDATE/DELETE no hay columnas por las que repartirlo.

        INSERT: tramos consecutivos (cualquier reparto es disjunto). UPDATE y DELETE: por PK (o ``partition_column``),
        para que dos hilos no toquen la misma fila: por rangos si es una sola columna entera o datetime sin repetidos
        (como en las mediciones), por hash si no (PK compuesta, texto, UUID o valores repetidos: los rangos cortan por
        posición y dos filas con la misma clave podrían quedar en particiones distintas).
        """
        if operation == "insert":
            size: int = math.ceil(len(df) / n)
            return [df.iloc[start : start + size] for start in range(0, len(df), size)]
        columns = self.__partition_columns(df, tabla_destino)
        if columns is None:
            return None
        if len(columns) == 1 and RangePartitioner.is_rangeable(df[columns[0]]) and df[columns[0]].is_unique:
            return RangePartitioner.partition_dataframe(df, columns[0], n)
        return HashPartitioner.partition_dataframe(df, columns, n)

    def __partition_columns(self, df: pd.DataFrame, tabla_destino: str) -> list[str] | None:
        """Columnas de ``df`` por las que repartir un UPDATE/DELETE: ``partition_column`` o las de la PK de la tabla."""
        options = self._options.parallel
        column: str | None = None if options is None else options.partition_column
        if column is not None:
            if column not in df.columns:
                raise ValueError(f"ParallelOptions.partition_column '{column}' no es una columna del DataFrame.")
            return [column]
        by_name: dict[str, str] = {str(name).lower(): str(name) for name in df.columns}
        pk: list[str | None] = [by_name.get(col.name.lower()) for col in self.reflect_table(tabla_destino).primary_key]
        if not pk or any(name is None for name in pk):
            return None
        return [name for name in pk if name is not None]

    def __load_partitions(
        self,
        partitions: list[pd.DataFrame],
        tabla_destino: str,
        operation: Literal["insert", "update", "delete"],
        workers: int,
        *,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
    ) -> None:
        """Carga las particiones con ``ParallelBulkLoader`` y suma sus contadores a los de la instancia."""
        # Diferido: parallel_loader importa BulkCrud.
        from ._execution.parallel_loader import ParallelBulkLoader

        options = self._options
        assert options.parallel is not None  # lo comprueba __run_in_parallel
        self._session.rows.start_operation()
        loader = ParallelBulkLoader(
            self.engine,
            batch=options.batch,
            # Los eventos de las particiones, con el run_id de la instancia; sin el INFO de auditoría deshabilitada en cada
            # carga (la instancia ya avisó al crearse).
            audit=replace(options.audit, run_id=self._audit_run_id, warn_if_disabled=False),
            rejects=options.rejects,
            execution=options.execution,
            parallel=replace(options.parallel, mode="manual", max_workers=workers),
        )
        # El privilegio TEMP ya comprobado por parallel_plan: el loader no abre otra conexión para consultarlo.
        loader._temp_tables_allowed = self._temp_tables_allowed  # noqa: SLF001 — mismo paquete (bulk)
        readers = [lambda partition=partition: iter((partition,)) for partition in partitions]
        if operation == "insert":
            result = loader.load(
                tabla_destino,
                readers,
                override_identity=override_identity,
                exclude_autoincrement_pk=exclude_autoincrement_pk,
            )
        elif operation == "update":
            result = loader.update(tabla_destino, readers)
        else:
            result = loader.delete(tabla_destino, readers)
        self._last_parallel_result = result
        # G37: cada partición confirmó sus filas en su transacción; cuentan también si otra falló.
        self._session.rows.record_committed(result.total_rows)
        self._parallel_audit = self._parallel_audit + AuditCounters.of(result)
        self._parallel_rows_rejected += result.rows_rejected
        if result.partition_errors:
            raise ParallelLoadError(
                f"bulk {operation.upper()} en paralelo sobre '{tabla_destino}': fallaron {len(result.partition_errors)} "
                f"de {len(partitions)} particiones; {result.total_rows} filas quedaron confirmadas. "
                f"{'; '.join(result.partition_errors)}",
                result=result,
            )
        self.logger.info(
            f"✅ bulk {operation.upper()} en paralelo finalizado: {result.total_rows} filas en "
            f"{result.elapsed_seconds:.2f} s ({self.db_info})."
        )

    def __run_bulk_pipeline(
        self,
        *,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool,
        path_sql: StrPath | None,
        strategy_key: Literal["insert", "update", "delete"],
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> None:
        """Template Method para operaciones bulk con estrategia por operación."""
        # Sin este log, el tiempo de la operación se atribuía en el log a la línea anterior (p. ej. el informe del advisor)
        self.logger.debug(
            f"▶️  bulk {strategy_key.upper()} iniciado: {len(df)} filas → {tabla_destino} "
            f"({'solo SQL' if generar_sql else 'en BD'}, {self.db_info})."
        )
        if generar_sql:
            path_sql = self.__validar_y_generar_path_sql(path_sql, tabla_destino, strategy_key)
        else:
            path_sql = None

        if self._stream is None:
            self._session.rows.start_operation()  # B-11; dentro de un *_from_chunks la operación es el stream
        # Copia superficial: solo se renombran columnas y con Copy-on-Write no se toca el DataFrame del llamador.
        working_df: pd.DataFrame = df.copy(deep=False)
        try:
            # Dentro del try: un fallo al reflejar la tabla se registra igual que cuando ocurría en prepare().
            self.__actualizar_df(working_df, self.reflect_table(tabla_destino))
            if strategy_key == "insert":
                operation_name = "INSERT"
                prepared_operation = self.__prepare_insert_operation(
                    working_df,
                    tabla_destino,
                    override_identity=override_identity,
                    exclude_autoincrement_pk=exclude_autoincrement_pk,
                )
            else:
                strategy: _BulkOperationStrategy = self._operation_strategies[strategy_key]
                operation_name = strategy.operation_name
                prepared_operation = strategy.prepare(working_df, tabla_destino)

            start: float = perf_counter()
            rejected: int = 0
            if generar_sql:
                self.__guardar_fichero_sql(prepared_operation.generate_sql_lines(), path_sql)
            else:
                with self._rejects.operation(tabla_destino, operation_name) as isolated:
                    isolated.rows = prepared_operation.rowcount
                    rejected_before: int = self._rejects.rejected_so_far()
                    prepared_operation.execute()
                    rejected = self._rejects.rejected_so_far() - rejected_before
            elapsed: float = perf_counter() - start

            self._persistence.register_operation(
                table_name=tabla_destino,
                operation=operation_name,
                # S-2: con on_error="isolate", las filas aplicadas (las rechazadas no están en la BD).
                rowcount=prepared_operation.rowcount - rejected,
                elapsed=elapsed,
                generated_sql=generar_sql,
            )
            self.logger.info(f"✅ bulk {operation_name} finalizado ({self.db_info}).")
        except ValueError as error:
            self.logger.error(str(error))
            raise
        except SQLAlchemyError as error:
            self.logger.error(f"❌ Error en bulk {strategy_key.upper()}: {error}")
            raise
        except (AuditError, OSError) as error:
            if any(note.startswith(REJECTS_FAILURE_NOTE) for note in getattr(error, "__notes__", ())):
                self.logger.error(f"❌ No se pudo escribir el CSV de rechazos de bulk {strategy_key.upper()}: {error}")
            else:
                self.logger.error(f"❌ Error registrando auditoría de bulk {strategy_key.upper()}: {error}")
            raise

    def __prepare_insert_operation(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        *,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> _PreparedBulkOperation:
        tabla: Table = self.reflect_table(tabla_destino)
        insert_cols, override = self.__insert_columns(
            df, tabla, override_identity=override_identity, exclude_autoincrement_pk=exclude_autoincrement_pk
        )

        insert_df: pd.DataFrame = df[insert_cols]
        numero_registros: int = len(insert_df)
        dialect = self.engine.dialect

        def blocks() -> Iterator[list[dict[str, Any]]]:
            return self.__record_blocks(insert_df, tabla, self._batch_sizes["insert"])

        def execute_blocks(stmt_exec: Any) -> None:
            with self.__blocks_transaction():
                if isinstance(stmt_exec, Insert) and self._batch_statement_executor.supports_columns:
                    # B-03 (performance-audit de bulk 2026-10-01): COPY, execute_values y el executemany de PyMySQL envían
                    # tuplas; con el bloque por columnas no se construye (y deshace) un dict por fila.
                    with closing_iterable(self.__prefetched(sql_blocks())) as sql_items:
                        for index, sql_block in enumerate(sql_items):
                            with self.__batch_note("insert", tabla, index, len(sql_block)):
                                self.__ejecutar_batch_stmt(
                                    sql_block, stmt_exec, len(sql_block), self.__first_row("insert", index)
                                )
                    return
                with closing_iterable(self.__prefetched(blocks())) as record_items:
                    for index, block in enumerate(record_items):
                        with self.__batch_note("insert", tabla, index, len(block)):
                            self.__ejecutar_batch_stmt(block, stmt_exec, len(block), self.__first_row("insert", index))

        def sql_blocks() -> Iterator[SqlColumns]:
            return self.__sql_blocks(insert_df, tabla, self._batch_sizes["insert"])

        if override:
            stmt_for_sql: Insert = insert(tabla)
            text_stmt = build_override_identity_text_stmt(tabla, insert_cols, dialect)
            return _PreparedBulkOperation(
                rowcount=numero_registros,
                generate_sql_lines=lambda: (
                    line
                    for block in sql_blocks()
                    for line in generate_insert_sql_override_identity(stmt_for_sql, block, dialect)
                ),
                execute=lambda: execute_blocks(text_stmt),
            )

        stmt: Insert = self.__insert_stmt(tabla, insert_cols)

        def insert_lines() -> Iterator[str]:
            return (line for block in sql_blocks() for line in self.__generar_sql_insert(stmt, block))

        if should_wrap_identity_insert(tabla, insert_cols, dialect):
            return _PreparedBulkOperation(
                rowcount=numero_registros,
                generate_sql_lines=lambda: iter_identity_insert_sql(insert_lines(), tabla, dialect),
                execute=lambda: execute_blocks(stmt),
            )

        return _PreparedBulkOperation(
            rowcount=numero_registros,
            generate_sql_lines=insert_lines,
            execute=lambda: execute_blocks(stmt),
        )

    def __record_blocks(self, df: pd.DataFrame, tabla: Table, size: int) -> Iterator[list[dict[str, Any]]]:
        """Registros de ``chunk_size`` en ``chunk_size`` filas, el lote del ejecutor (P-07).

        Antes se convertía todo el DataFrame a registros antes del primer lote: el pico de memoria era 3,8–4,7 veces
        el DataFrame al ejecutar y 8,9–9,5 veces al generar SQL (200K filas).
        """
        for start in range(0, len(df), size):
            records: list[dict[str, Any]] = dataframe_to_sql_records(
                df.iloc[start : start + size], strip_strings=self._strip_strings
            )
            restore_binary_values(records, tabla)  # P-21
            yield records

    def __sql_blocks(self, df: pd.DataFrame, tabla: Table, size: int) -> Iterator[SqlColumns]:
        """Como :meth:`__record_blocks`, por columnas, para generar SQL sin un diccionario por fila (P-34)."""
        for start in range(0, len(df), size):
            block = SqlColumns(
                *dataframe_to_sql_columns(df.iloc[start : start + size], strip_strings=self._strip_strings)
            )
            restore_binary_values(block, tabla)  # P-21
            yield block

    @contextmanager
    def __blocks_transaction(self) -> Generator[None, None, None]:
        """Una transacción para todos los bloques (P-07): la de ``bulk_session`` si ya está abierta, o una nueva.

        Equivale a lo anterior, cuando todos los lotes iban en una sola llamada al ejecutor: atómica, o
        commit-as-you-go con ``commit_every_n_chunks``.
        """
        if self._session.active:
            yield
            return
        with self.bulk_session():
            yield

    def __prepare_update_operation(self, df: pd.DataFrame, tabla_destino: str) -> _PreparedBulkOperation:
        tabla: Table = self.reflect_table(tabla_destino)
        update_plan = build_update_plan(tabla, list(df.columns), tabla_destino)
        # P-09: solo PK + columnas actualizables; el resto del DataFrame no se usa.
        update_df: pd.DataFrame = df[update_plan.pk_cols + update_plan.update_cols]
        numero_registros: int = len(update_df)

        def blocks() -> Iterator[list[dict[str, Any]]]:
            for records in self.__record_blocks(update_df, tabla, self._batch_sizes["update"]):
                for record in records:
                    for original_col, alias_col in update_plan.pk_param_map.items():
                        record[alias_col] = record[original_col]
                yield records

        def sql_blocks() -> Iterator[SqlColumns]:
            for block in self.__sql_blocks(update_df, tabla, self._batch_sizes["update"]):
                for original_col, alias_col in update_plan.pk_param_map.items():
                    block.add_alias(alias_col, original_col)
                yield block

        return _PreparedBulkOperation(
            rowcount=numero_registros,
            generate_sql_lines=lambda: (
                line
                for block in sql_blocks()
                for line in self.__generar_sql_update(
                    tabla,
                    block,
                    update_plan.update_cols,
                    update_plan.pk_param_map,
                    update_plan.pk_cols,
                )
            ),
            execute=lambda: self.__execute_update_blocks(tabla, update_plan, blocks()),
        )

    def __execute_update_blocks(
        self, tabla: Table, update_plan: UpdatePlan, blocks: Iterator[list[dict[str, Any]]]
    ) -> None:
        """Ejecuta el UPDATE bloque a bloque en una sola transacción (P-07), por staging si está activo (P-04)."""
        where_clause: ColumnElement[bool] = and_(
            *(tabla.c[col] == bindparam(update_plan.pk_param_map[col]) for col in update_plan.pk_cols)
        )
        json_binds = json_passthrough_binds(tabla, update_plan.update_cols)  # P-19: sin doble serialización
        stmt: Update = (
            update(tabla)
            .where(where_clause)
            .values({col: json_binds.get(col, bindparam(col)) for col in update_plan.update_cols})
        )
        executor = self._batch_statement_executor
        if self._rejects.isolator is not None:
            # S-5: con un bind LOB grande y una fila mala, batcherrors da ORA-03106 en el UPDATE (oracledb thin 4.0.1,
            # 4.0.2 y 26.0.1; el INSERT no falla: sesión 2026-10-01y).
            self._rejects.isolator.batch_errors = self.__batch_errors() and not any(
                _lob_like(tabla.c[column].type) for column in update_plan.update_cols
            )
        staging: StagingUpdateStrategy | None = None
        if self._update_via_staging:
            key = (id(tabla), tuple(update_plan.pk_cols), tuple(update_plan.update_cols))
            staging = self._staging_strategies.get(key)
            if staging is None:
                staging = StagingUpdateStrategy(
                    table=tabla,
                    pk_cols=update_plan.pk_cols,
                    update_cols=update_plan.update_cols,
                    loader=executor.insert_strategy,
                )
                self._staging_strategies[key] = staging
        with self.__blocks_transaction(), closing_iterable(self.__prefetched(blocks)) as update_items:
            for index, block in enumerate(update_items):
                with self.__batch_note("update", tabla, index, len(block)):
                    executor.execute(
                        records=block, stmt=stmt, strategy=staging, first_row=self.__first_row("update", index)
                    )
        if staging is not None and staging.staging_denied:
            # Sin privilegio: no volver a intentarlo en esta instancia (el aviso ya quedó en el log).
            self._update_via_staging = False

    def __prepare_delete_operation(self, df: pd.DataFrame, tabla_destino: str) -> _PreparedBulkOperation:
        tabla: Table = self.reflect_table(tabla_destino)
        pk_cols: list[str] = self.__obtener_pk_cols(tabla, df.columns)
        numero_registros: int = len(df)

        def delete_lines() -> Iterator[str]:
            for start in range(0, len(df), self.chunk_size):  # P-07: por bloques
                yield from self.__generar_sql_delete(df.iloc[start : start + self.chunk_size], tabla, pk_cols)

        return _PreparedBulkOperation(
            rowcount=numero_registros,
            generate_sql_lines=delete_lines,
            execute=lambda: self.__ejecutar_delete_batch(df, tabla, pk_cols, numero_registros),
        )

    @staticmethod
    def __insert_stmt(tabla: Table, insert_cols: list[str]) -> Insert:
        """``insert(tabla)`` con las columnas JSON enlazadas sin volver a serializar (P-19)."""
        stmt: Insert = insert(tabla)
        json_binds = json_passthrough_binds(tabla, insert_cols)
        return stmt.values(json_binds) if json_binds else stmt

    def __ejecutar_batch_stmt(
        self, records: Sequence[Mapping[str, Any]], stmt: Any, numero_registros: int, first_row: int = 0
    ) -> None:
        """Ejecuta un statement de SQLAlchemy por lotes.

        Único punto de ejecución del INSERT: un bloque por columnas (``SqlColumns``, B-03) va por
        ``execute_columns`` sin trocearlo (``SqlColumns[a:b]`` construiría un dict por fila).

        Args:
            records: lista de diccionarios con datos a procesar, o un bloque ``SqlColumns``.
            stmt: Statement SQLAlchemy (Insert, Update, Delete).
            numero_registros: Total de registros (para logging).
            first_row: Posición en la entrada de la primera fila (filas rechazadas con ``on_error="isolate"``).
        """
        if isinstance(records, SqlColumns):
            self._batch_statement_executor.execute_columns(block=records, stmt=stmt, first_row=first_row)
            return
        self._batch_statement_executor.execute(records=records[:numero_registros], stmt=stmt, first_row=first_row)

    def __obtener_pk_cols(self, tabla: Table, df_cols) -> list[str]:
        """Obtiene las columnas PK presentes en el DataFrame.

        Args:
            tabla: Objeto Table reflejado.
            df_cols: Columnas del DataFrame.

        Returns:
            lista de nombres de columnas PK.

        Raises:
            ValueError: Si no hay PKs presentes en el DataFrame.
        """
        return get_pk_columns(tabla, df_cols)

    def __ejecutar_delete_batch(
        self,
        df: pd.DataFrame,
        tabla: Table,
        pk_cols: list[str],
        numero_registros: int,
    ):
        """Ejecuta borrado por lotes en la base de datos."""
        del numero_registros
        stream = self._stream
        self._delete_batch_executor.execute(
            table=tabla,
            df=df,
            pk_cols=pk_cols,
            row_offset=0 if stream is None else stream.row_offset,
            chunk=None if stream is None else stream.chunk,
            continue_cadence=stream is not None and not stream.first,
        )

    def __actualizar_df(self, df: pd.DataFrame, tabla: Table) -> None:
        """Normaliza nombres de columnas según el dialecto de BBDD y los alinea con los de la tabla reflejada.

        Args:
            df: DataFrame a normalizar. Debe ser una copia — se muta en lugar.
            tabla: Tabla destino reflejada. Las columnas que tras normalizar solo coinciden con ella sin distinguir
                mayúsculas toman su nombre reflejado (PD-01: SQL Server con columnas en minúsculas o mixtas).

        Comportamiento de dialectos:
            - oracle: Minúsculas (identifiers sin comillas se tratan como minúsculas)
            - postgresql: Minúsculas (identifiers sin comillas se tratan como minúsculas)
            - sqlite: Minúsculas (comportamiento nativo de SQLite)
            - mysql/mariadb: NO se normaliza (SQLAlchemy reflection preserva el case original)
            - mssql: Mayúsculas (identifiers por defecto en SQL Server)
            - hsqldb: Mayúsculas (comportamiento nativo de HSQLDB)

        Nota: Para MySQL/MariaDB, no normalizamos porque SQLAlchemy reflection ya maneja
        correctamente los nombres de columnas tal como existen en la BD, independientemente
        de lower_case_table_names. Normalizar causaría mismatch si las columnas están en minúsculas.
        """
        # Skip normalization for MySQL/MariaDB; SQLAlchemy handles column name matching correctly
        if self.engine.dialect.name not in MYSQL_FAMILY:
            normalize_dataframe_columns(df, self.engine.dialect.name, self.logger)
        align_dataframe_columns(df, tabla)

    def reflect_table(self, tabla_destino: str) -> Table:
        """
        Refleja una tabla desde la base de datos y devuelve el objeto `Table` correspondiente.

        El resultado se almacena en ``_table_cache`` (Identity Map) para evitar round-trips
        repetidos de introspección cuando se llama varias veces con el mismo nombre de tabla
        dentro de la misma instancia (p.ej. loop de chunks en ``DumpOrchestrator``).

        Args:
            tabla_destino: Nombre lógico de la tabla. Puede ser ``"schema.tabla"`` para
                especificar un schema explícito. Para MySQL/MariaDB, el nombre se preserva
                tal como es (SQLAlchemy maneja la búsqueda independientemente del case).
                Para otros dialectos, se normaliza el casing según el dialecto.

        Returns:
            El objeto `Table` reflejado.
        """
        if tabla_destino in self._table_cache:
            return self._table_cache[tabla_destino]
        metadata = MetaData()
        # PD-08 (performance-audit de dump 2026-09-25): sin resolve_fks=False SQLAlchemy reflejaba también, de forma
        # recursiva, todas las tablas referenciadas por FK; con un MetaData nuevo por llamada el coste era cuadrático y una
        # cadena de ~150 FK lanzaba RecursionError. bulk solo necesita las columnas, la PK y la identidad de la tabla.

        # Para MySQL/MariaDB, no normalizar: SQLAlchemy reflection maneja correctamente
        # la búsqueda independientemente del case usado (depende de lower_case_table_names)
        skip_normalization: bool = self.engine.dialect.name in MYSQL_FAMILY

        if "." in tabla_destino:
            schema_part, table_part = tabla_destino.split(".", 1)
            tabla_normalizada: str = (
                table_part if skip_normalization else normalize_identifier(table_part, self.engine.dialect.name)
            )
            schema: str | None = schema_part
        else:
            tabla_normalizada = (
                tabla_destino if skip_normalization else normalize_identifier(tabla_destino, self.engine.dialect.name)
            )
            schema = None
        tabla = Table(tabla_normalizada, metadata, schema=schema)
        # Q9: sin leer las FK salvo reflect_foreign_keys=True (metadata.reflection, ADR-003 C5)
        reflect_table(self.engine, tabla, foreign_keys=self._reflect_foreign_keys)
        self._table_cache[tabla_destino] = tabla
        return tabla

    @property
    def audit_failures(self) -> int:
        """Registros de auditoría que no se pudieron escribir en el CSV (solo con ``audit_strict=False``).

        Cada uno queda además en el log como ERROR, con tabla, operación, filas y tiempo. Incluye los de las cargas
        paralelas de la instancia (como el resto de contadores de auditoría y :attr:`rows_rejected`).
        """
        return self._persistence.audit_failures + self._parallel_audit.audit_failures

    @property
    def audited_rows(self) -> int:
        """Filas (``rowcount``) de los registros escritos en el CSV de auditoría por esta instancia.

        Con auditoría activa y sin incidencias coincide con las filas cargadas. La diferencia se explica con
        :attr:`audit_failures`, :attr:`unaudited_committed_rows` y :attr:`audit_uncommitted_records`. Incluye las
        operaciones con ``generar_sql=True``, que no tocan la BD.
        """
        return self._persistence.audited_rows + self._parallel_audit.audited_rows

    @property
    def audit_uncommitted_records(self) -> int:
        """Registros escritos en el CSV antes de un commit que falló (solo con ``audit_strict=True``).

        En modo estricto la auditoría de :meth:`bulk_session` se escribe antes del commit; si el commit falla, esos
        registros quedan en el CSV sin datos en la BD. Cada caso queda además en el log como ERROR.
        """
        return self._persistence.audit_uncommitted_records + self._parallel_audit.audit_uncommitted_records

    @property
    def unaudited_committed_rows(self) -> int:
        """Filas confirmadas por commits periódicos que no constan en el CSV (``commit_every_n_chunks``).

        Si una sesión falla, la operación que tenía parte de sus lotes confirmados no se audita. Esas filas están en la
        BD (y en :attr:`rows_committed`) pero no en el CSV. Cuenta INSERT, UPDATE y DELETE (hasta v0.17.x era
        aproximado en sesiones con DELETE, que no sumaba a :attr:`rows_committed`).
        """
        return self._persistence.unaudited_committed_rows + self._parallel_audit.unaudited_committed_rows

    @property
    def batch_sizes(self) -> dict[BulkOperation, int]:
        """Filas por lote de cada operación (``insert``, ``update``, ``delete``), resueltas en el constructor (B-04)."""
        return dict(self._batch_sizes)

    @property
    def last_operation_rows_committed(self) -> int:
        """Filas de la última operación (o de la que falló) ya confirmadas en la BD: su prefijo confirmado.

        B-11 (performance-audit de bulk 2026-10-01). Con ``commit_every_n_chunks`` los lotes se confirman en orden, así
        que tras un fallo basta con reanudar desde esa posición (``df.iloc[n:]``, o saltando ``n`` filas de la secuencia
        en las vías ``*_from_chunks``, que cuentan como una sola operación). En modo atómico, desde v4.5.0 (G37 de
        util_bbdd_web), son todas las filas de la operación cuando su transacción (o la de :meth:`bulk_session`) se
        confirma, y 0 si falla: el fallo la deshace entera. Hasta v4.4.x era siempre 0 en modo atómico. A diferencia de
        :attr:`rows_committed` (acumulado de la instancia), no incluye filas de operaciones anteriores que un commit de
        esta confirmó.

        Cuenta las filas enviadas (``len(df)``, también las apartadas con ``on_error="isolate"``, ver
        :attr:`rows_rejected`), no las que la BD dice haber modificado: un UPDATE o DELETE de una clave que no existe
        cuenta. En una carga paralela (``ParallelOptions``) son las filas de las particiones confirmadas
        (``last_parallel_result.total_rows``); si alguna falló no forman un prefijo: para reanudar, ``partition_results``.
        """
        return self._session.rows.op_committed

    @property
    def audit_run_id(self) -> str | None:
        """``run_id`` de los eventos de ``audit_sink`` (el recibido o uno nuevo por instancia); ``None`` sin destino."""
        return self._audit_run_id

    @property
    def rows_rejected(self) -> int:
        """Filas rechazadas por esta instancia con ``on_error="isolate"`` (escritas en ``rejects_csv_path``), acumulado.

        S-2 (2026-10-01). Las filas rechazadas no están en la BD ni en la auditoría, pero sí cuentan en
        :attr:`rows_committed` y :attr:`last_operation_rows_committed`, que son posiciones de la entrada para reanudar.
        Si la operación falla después por otra causa (o por ``max_rejects``), lo ya escrito en el CSV se queda.
        Si no se puede escribir el CSV (p. ej. abierto en Excel), la operación falla con ``OSError`` (nota «no se pudo
        escribir el CSV de rechazos») y esa fila no cuenta.
        """
        return self._rejects.rows_rejected + self._parallel_rows_rejected

    @property
    def options(self) -> BulkOptions:
        """Paquetes de opciones de la instancia (v3.0.0), tal como se recibieron (con los valores por defecto)."""
        return self._options

    @property
    def last_parallel_result(self) -> ParallelLoadResult | None:
        """Resultado de la última carga paralela de un ``bulk_*_from_df`` (``ParallelOptions``); ``None`` si no hubo.

        También tras un ``ParallelLoadError`` (es el mismo que ``exc.result``). Desde v4.5.0 (G37 de util_bbdd_web) sus
        ``total_rows`` cuentan en :attr:`rows_committed` y en :attr:`last_operation_rows_committed`; el detalle está en
        ``partition_results``.
        """
        return self._last_parallel_result

    @property
    def rows_committed(self) -> int:
        """Filas durablemente comprometidas en BD por esta instancia hasta el momento.

        Cuenta las filas enviadas de INSERT, UPDATE y DELETE (``len(df)``, como el CSV de auditoría; no las que la BD dice
        haber modificado). Hasta v0.17.x no contaba las del DELETE.

        BLK-08 (AUDIT_CODE 2026-09-22): avanza con cada commit, nunca con filas ejecutadas pendientes de confirmar. Con
        ``commit_every_n_chunks``, en cada commit periódico y en el final de ``bulk_session()``. En modo atómico
        (default), desde v4.5.0 (G37 de util_bbdd_web), cuando se confirma la transacción de la operación o de la sesión;
        un fallo la revierte entera y no suma nada. Hasta v4.4.x permanecía en 0 en modo atómico. Incluye las filas de
        las particiones confirmadas de las cargas paralelas de ``bulk_*_from_df`` (:attr:`last_parallel_result`).

        Permite a quien orquesta cargas por partición (p.ej. ``ParallelBulkLoader``)
        saber cuántas filas sobrevivieron aunque la carga falle a mitad de sesión.
        """
        return self._batch_statement_executor.rows_committed

    @contextmanager
    def bulk_session(self, *, atomic: bool = True) -> Generator[None, None, None]:
        """Context manager que reutiliza una única conexión de BD para múltiples operaciones bulk.

        Usar cuando se invoca ``bulk_insert_from_df`` repetidamente (p.ej. en un loop
        de chunks), para evitar abrir y cerrar una transacción por cada invocación.
        ``bulk_update_from_df`` y ``bulk_delete_from_df`` participan en la misma transacción.

        Args:
            atomic: Si ``True`` (default), todos los inserts de la sesión se commitean
                atómicamente al salir del bloque. Un error en cualquier chunk hace
                rollback de toda la sesión. Si ``False``, cada ``bulk_insert_from_df``
                gestiona su propia transacción (comportamiento legacy).

        Nota: ``BulkCrud`` no es thread-safe. No compartir instancias entre hilos.

        Nota: si se construyó ``BulkCrud(batch=BatchOptions(commit_every_n_chunks=N))``, la sesión usa
        commit-as-you-go (commitea cada N lotes y al salir el resto). En ese modo
        la sesión **no** es atómica aunque ``atomic=True``: un fallo a mitad deja
        committeados los lotes anteriores.

        Auditoría: dentro de la sesión cada operación se escribe en el CSV cuando un commit la confirma (al salir
        del bloque o, con ``commit_every_n_chunks``, en el commit periódico). Si la sesión acaba en rollback, lo
        pendiente se descarta con un WARNING. Así la traza no cuenta filas deshechas ni las repite cuando se
        reintenta la sesión. El ``timestamp`` sigue siendo el de fin de cada operación. Con ``commit_every_n_chunks``,
        lo que confirman los commits periódicos se escribe por tandas (64 registros o 1 s) y al cerrar la sesión; una
        operación que no llega a confirmarse entera antes de un fallo no se audita, y sus filas ya confirmadas se
        suman a :attr:`unaudited_committed_rows`. Las operaciones con ``generar_sql=True`` no tocan la BD y se
        escriben al momento. Si falla la escritura del CSV, ver ``audit_strict`` en el constructor; con
        ``audit_strict=True``, si lo que falla es el commit, lo ya escrito se cuenta en
        :attr:`audit_uncommitted_records`.
        """
        if not atomic:
            yield
            return
        # La sesión la comparten el INSERT/UPDATE y el DELETE (P-26); la cadencia es la del INSERT/UPDATE.
        cadence = self._batch_statement_executor.cadence
        persistence = self._persistence
        committed_before = cadence.rows_committed
        committed_rows: int | None = None
        try:
            if cadence.every is not None:
                cadence.restart()
                with self.engine.connect() as conn, self._session.bind(conn, commit_hook=persistence.commit):
                    persistence.start_session_audit(conn)
                    try:
                        # Lo que sigue al yield es el commit del camino feliz, no limpieza: no debe ir en un finally
                        # (confirmaría tras un error). La limpieza está en el finally exterior.
                        yield  # NOSONAR
                        persistence.commit(conn)
                        cadence.confirm()
                    except BaseException:
                        # PL-1 (audit-code de ParallelBulkLoader): lo confirmado por commits periódicos, para contar
                        # las filas que no constan en el CSV.
                        committed_rows = cadence.rows_committed - committed_before
                        # Lo pendiente se deshace con la sesión: sin descartarlo, la siguiente que termina bien lo
                        # sumaba a rows_committed.
                        cadence.discard_pending()
                        raise
                return
            try:
                with self.engine.begin() as conn, self._session.bind(conn):
                    persistence.start_session_audit(conn)
                    yield  # NOSONAR - igual que arriba: el flush solo procede si el bloque termina bien
                    persistence.flush_audit_before_commit()
            except BaseException:
                self._session.rows.discard()  # G37: el rollback deshace las filas anotadas
                raise
            self._session.rows.confirm()
            persistence.flush_audit_after_commit()
        finally:
            for exc in self._session.run_after_end():
                self.logger.error(f"❌ Acción posterior a la sesión fallida: {exc}")
            persistence.end_session_audit(committed_rows=committed_rows)

    def get_columna_may_min(self, tabla: Table, nombre_col: str) -> Column | None:
        """Devuelve una columna de una tabla SQLAlchemy ignorando mayúsculas/minúsculas.

        Args:
            tabla: Tabla SQLAlchemy reflejada.
            nombre_col: Nombre de la columna en cualquier capitalización.

        Returns:
            La columna, o ``None`` si no existe.
        """
        return get_column_case_insensitive(tabla, nombre_col)

    def obtener_valor_max_columna(self, tabla: Table, nombre_col: str) -> int:
        """Devuelve MAX(nombre_col)+1; retorna 1 si la columna está vacía o el máximo es negativo.

        Args:
            tabla: Tabla SQLAlchemy reflejada.
            nombre_col: Columna numérica de la que se lee el máximo.

        Returns:
            El siguiente valor libre de la columna.
        """
        return get_max_column_value(self.engine, tabla, nombre_col)

    @contextmanager
    def maintenance_scope(
        self,
        tabla_destino: str,
        disable_constraints: bool = True,
        disable_indexes: bool | IndexMode = False,
        require_optimization: bool = False,
        validate_fks_after: bool = True,
    ) -> Generator[MaintenanceScopeResult, None, None]:
        """Context manager que prepara la tabla para una carga de alto volumen (>1M).

        Deshabilita temporalmente las comprobaciones de integridad y (opcionalmente)
        los índices para maximizar el rendimiento (throughput).

        Soporte por motor (constraints):
        - **MariaDB/MySQL**: Deshabilita `FOREIGN_KEY_CHECKS` a nivel de sesión. Con FK checks desactivadas tampoco se
          ejecutan los ``ON DELETE/UPDATE CASCADE``: un DELETE o UPDATE dentro del bloque no los propaga a las hijas.
        - **Oracle**: Deshabilita cada FK, CHECK (no SYS_C) y UNIQUE con
          ``ALTER TABLE ... DISABLE CONSTRAINT``. Re-habilita con ``ENABLE VALIDATE``. En Oracle el DDL confirma la
          transacción: lo cargado en la sesión antes de entrar y lo cargado dentro del bloque queda confirmado al
          desactivar y al reactivar; si el bloque falla, se deshace lo pendiente antes de reactivar.
        - **PostgreSQL**: Ejecuta ``ALTER TABLE ... DISABLE TRIGGER ALL``. Requiere ser
          propietario de la tabla o superusuario; si no, opera sin optimización (se registra
          un aviso). Al restaurar, ejecuta un orphan-check de FK para detectar violaciones
          cargadas con los triggers desactivados (audit H-01, 2026-09-27).
        - **SQL Server**: Ejecuta ``ALTER TABLE ... NOCHECK CONSTRAINT ALL``. Persiste en
          catálogo pero se restaura al salir del bloque.
        - **SQLite**: No soportado; opera sin optimización.

        Índices (``disable_indexes``; desde 3.2.0, la misma estrategia que ``DumpConfig.manage_indexes``): se desactivan
        los secundarios **no únicos** y se reconstruyen al salir (``index_results``); nunca los de PK/UNIQUE ni el
        índice clustered. SQL Server ``ALTER INDEX … DISABLE``→``REBUILD`` (NONCLUSTERED; hasta 3.1.x solo en tablas sin
        CLUSTERED); PostgreSQL ``DROP INDEX``→recreación desde ``pg_get_indexdef`` (se loguea antes; DDL dentro de la
        transacción: el rollback de la sesión los devuelve); Oracle ``UNUSABLE``→``REBUILD`` (confirma la transacción,
        como sus constraints); MyISAM/Aria ``DISABLE KEYS``; InnoDB ``DROP INDEX``→un ``ADD INDEX`` por tabla (sin los
        que necesita una FK), **solo con** ``commit_every_n_chunks``: en la sesión atómica se omite, porque su DDL
        confirmaría lo pendiente. Un índice que no se puede desactivar o reconstruir se avisa y no detiene al resto.
        Medido en serie a 3,5M filas con 2 secundarios: entre −9 % (MariaDB) y −88 % (Oracle) de tiempo total.

        ``disable_indexes="all"`` (v3.3.0): además, los índices únicos y PK/UNIQUE (nunca el clustered, la PK de InnoDB
        ni la de una IOT de Oracle), con las FK de otras tablas que los referencian: SQL Server y Oracle las reactivan
        (``WITH CHECK CHECK CONSTRAINT``/``ENABLE VALIDATE``) y PostgreSQL las borra y recrea (``NOT VALID`` +
        ``VALIDATE``). **La unicidad no se comprueba durante la carga**: solo para datos ya validados (la carga final
        de un proceso con iteraciones de calidad). Exige ``disable_constraints=True`` y no admite
        ``RejectOptions(on_error="isolate")``; avisa si la tabla ya tiene filas. Si un único no se puede reconstruir
        (duplicados), al salir lanza :exc:`~util_bbdd.exceptions.IndexRebuildError` con las claves repetidas, después
        de restaurar todo lo demás: en PostgreSQL y SQL Server la sesión deshace también la carga; en Oracle y
        MariaDB/MySQL las filas quedan cargadas. En Oracle, una UNIQUE que ya desactivó ``disable_constraints`` sigue a
        cargo de esa ruta. Los índices únicos sin constraint de Oracle (desde 4.0.0) se borran y se recrean con su
        ``DBMS_METADATA.GET_DDL``; si no se puede obtener, no se tocan y salen en ``index_results`` como ``"skipped"``.

        Args:
            tabla_destino: Nombre de la tabla destino (acepta "esquema.tabla").
            disable_constraints: Deshabilita FKs y triggers. Por defecto True.
            disable_indexes: ``True`` o ``"secondary"`` (equivalentes): desactiva los índices secundarios no únicos
                durante el bloque (ver arriba). Por defecto False.
            require_optimization: Si True y la optimización no puede aplicarse (p.ej.
                PostgreSQL sin privilegios suficientes), lanza :exc:`RuntimeError` en lugar
                de continuar en silencio. Por defecto False.
            validate_fks_after: MariaDB/MySQL (v3.3.0; por defecto desde v3.4.0): al reactivar
                ``FOREIGN_KEY_CHECKS`` comprueba con un ``NOT EXISTS`` por FK que no se cargaron filas huérfanas
                (``constraint_results`` con ``"enabled"`` o ``"failed"`` por FK en vez de ``"unverified"``). Cuesta en
                torno al 1 % de la carga (1M filas, 2 FK). En el resto de motores la validación ya se hace al
                reactivar. Por defecto True; ``False`` mantiene la fila única ``"unverified"`` de hasta 3.3.0.

        Yields:
            :class:`MaintenanceScopeResult` con ``optimization_applied``, ``constraint_results`` e ``index_results``
            (estos dos, disponibles tras salir del bloque ``with``).

        Ejemplo::

            bulk = BulkCrud(engine)
            with bulk.bulk_session():
                with bulk.maintenance_scope("usuarios", disable_indexes=True) as ms:
                    bulk.bulk_insert_from_df(df, "usuarios", generar_sql=False)
            for r in ms.constraint_results:
                print(r.constraint_name, r.status)

        Raises:
            RuntimeError: Si se invoca fuera de un :meth:`bulk_session` activo, o si
                ``require_optimization=True`` y la optimización no puede aplicarse.
            ValueError: Si ``disable_indexes`` no es ``bool``, ``"secondary"`` ni ``"all"``, o ``"all"`` sin
                ``disable_constraints`` o con ``on_error="isolate"``.
            IndexRebuildError: Con ``"all"``, si un índice único o PK no se puede reconstruir al salir.
        """
        index_mode = resolve_index_mode(disable_indexes, "disable_indexes")
        if index_mode == "all":
            # D1 y F2 del AUDIT_PLAN (sesión 2026-10-18b): sin desactivar las FK no se puede quitar una PK referenciada,
            # y sin unicidad "isolate" no tendría duplicados que apartar.
            if not disable_constraints:
                raise ValueError("disable_indexes='all' exige disable_constraints=True.")
            if self._options.rejects.on_error == "isolate":
                raise ValueError(
                    "disable_indexes='all' no admite RejectOptions(on_error='isolate'): los duplicados no darían error."
                )
        tabla = self.reflect_table(tabla_destino)
        # A5 (v1.1.0): la desactivación y restauración por motor viven en TableMaintenance (_execution/maintenance.py).
        # Se crea en cada llamada para usar el engine, la sesión y el _table_snapshot vigentes.
        maintenance = TableMaintenance(
            engine=self.engine,
            session=self._session,
            cadence=self._batch_statement_executor.cadence,
            table_snapshot=self._table_snapshot,
            logger=self.logger,
        )
        with maintenance.scope(
            tabla,
            tabla_destino,
            disable_constraints=disable_constraints,
            index_mode=index_mode,
            require_optimization=require_optimization,
            validate_fks_after=validate_fks_after,
        ) as result:
            yield result

    def _table_snapshot(self, tabla: Table, kinds: set[Kind]) -> Any:
        """Metadatos ``kinds`` de una tabla con una consulta por tipo (``metadata``, ADR-003 C5); sin caché."""
        try:
            source = CatalogSource.from_engine(self.engine)
        except CatalogDialectNotFoundError as exc:
            raise LookupError(f"sin catálogo para '{self.engine.dialect.name}'") from exc
        return source.snapshot(tabla.schema, kinds=kinds, tables=[tabla.name])

    def __generar_sql_insert(self, stmt: Insert, records: Sequence[dict[str, Any]]) -> list[str]:
        """Genera SQL INSERT desde un statement y una lista de registros.

        Maneja valores binarios convirtiendo a hexadecimal.
        """
        return generate_insert_sql(stmt, records, self.engine.dialect)

    def __generar_sql_update(
        self,
        tabla: Table,
        records: Sequence[dict[str, Any]],
        update_cols: list[str],
        pk_param_map: dict[str, str],
        pk_cols: list[str],
    ) -> list[str]:
        return generate_update_sql(
            table=tabla,
            records=records,
            update_cols=update_cols,
            pk_param_map=pk_param_map,
            pk_cols=pk_cols,
            dialect=self.engine.dialect,
        )

    def __generar_sql_delete(self, df: pd.DataFrame, tabla: Table, pk_cols: list[str]) -> list[str]:
        delete_records: list[dict[str, Any]] = [
            {str(key): value for key, value in record.items()} for record in df[pk_cols].to_dict(orient="records")
        ]
        return generate_delete_sql(
            records=delete_records,
            table=tabla,
            pk_cols=pk_cols,
            dialect=self.engine.dialect,
        )

    def __guardar_fichero_sql(self, sql_lines: Iterable[str], fichero_sql: Path | None) -> None:
        """Guarda las líneas SQL en un archivo o las imprime en log.

        Args:
            sql_lines: líneas SQL (se escriben a medida que se generan).
            fichero_sql: Ruta del archivo destino. Si es None, imprime en log.
        """
        self._persistence.persist_sql(sql_lines, fichero_sql)

    def sync_pk_sequences(self, tables: list[str] | None = None) -> list[PKSyncResult]:
        """Sincroniza los contadores PK tras una carga masiva con PKs explícitas.

        Debe llamarse **después** de haber insertado los datos, cuando los contadores
        de sequence/identity/auto_increment han quedado por detrás del MAX real de la tabla.

        Args:
            tables: Nombres de tabla a sincronizar (misma convención que
                ``bulk_insert_from_df``). ``None`` = sincronizar todas las tablas
                reflejadas en esta sesión (``_table_cache``).

        Returns:
            Lista de ``PKSyncResult``, uno por columna PK identity procesada.
            Los errores se capturan en ``PKSyncResult.status = "error"``; no se propagan.

        Permisos requeridos por motor:

        - **PostgreSQL**: propietario de la tabla o ``SUPERUSER``.
        - **SQL Server**: ``ALTER TABLE`` permission o membresía en ``db_owner``.
        - **MariaDB/MySQL**: ``ALTER`` privilege sobre la tabla.
        - **Oracle >= 12c**: ``SELECT`` en ``ALL_TAB_IDENTITY_COLS`` +
          ``ALTER ANY SEQUENCE`` (o ser propietario de la sequence).
        """
        if tables is None:
            table_objects = list(self._table_cache.values())
        else:
            table_objects = [self.reflect_table(t) for t in tables]

        if not table_objects:
            return []

        syncer = PKSequenceSyncer(self.engine)
        return syncer.sync_all(table_objects)
