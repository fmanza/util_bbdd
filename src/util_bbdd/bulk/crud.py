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

from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import pandas as pd

from sqlalchemy import (
    Column,
    ColumnElement,
    Engine,
    Insert,
    Inspector,
    MetaData,
    Table,
    Update,
    and_,
    bindparam,
    insert,
    inspect,
    text,
    update,
)
from sqlalchemy.exc import SQLAlchemyError

from ..metadata.mariadb.tables import fetch_table_storage_engine_sql
from ..metadata.sqlserver.indexes import fetch_clustered_index_count_sql
from ._execution.batch import (
    BatchStatementExecutor,
    DeleteBatchExecutor,
    InsertStrategyResolver,
    MySQLStagingUpdateStrategy,
    validate_chunk_size,
)
from ._execution.session import SessionScope
from ._models import MaintenanceScopeConstraintResult, MaintenanceScopeResult, PKSyncResult
from ._support.dialect import (
    MYSQL_FAMILY,
    can_disable_pg_triggers,
    disable_table_integrity_sql,
    enable_table_integrity_sql,
)
from ._support.persistence import BulkPersistenceManager
from ._support.pk_sync import PKSequenceSyncer
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

try:
    from util.timing.medir_tiempo import medir_tiempo
except ImportError:

    def medir_tiempo(proceso: str = "") -> Any:
        """Decorator placeholder for timing (util not available).

        Args:
            proceso: Process name for logging (unused)

        Returns:
            Decorator function that returns the original function unchanged
        """
        _: str = proceso

        def _decorator(function: Any) -> Any:
            return function

        return _decorator


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


def _no_foreign_keys(*_args: Any, **_kwargs: Any) -> dict[Any, list[Any]]:
    """Sustituto de ``Inspector.get_multi_foreign_keys`` que no lee nada (``reflect_foreign_keys=False``)."""
    return {}


class BulkCrud:
    """Realiza operaciones CRUD en lote sobre bases de datos usando SQLAlchemy."""

    def __init__(
        self,
        engine: Engine | None,
        chunk_size: int = 5000,
        audit_csv_path: Path | None = None,
        enable_fast_executemany: bool = True,
        insert_resolver: InsertStrategyResolver | None = None,
        commit_every_n_chunks: int | None = None,
        update_via_staging: bool = True,
        audit_strict: bool = False,
        warn_if_audit_disabled: bool = True,
        strip_strings: bool = True,
        reflect_foreign_keys: bool = True,
    ):
        """
        Constructor de la clase bulk_crud.

        Args:
            engine: Engine de SQLAlchemy para las operaciones. Obligatorio.
            chunk_size: Tamaño del lote para procesar. Por defecto es 5000.
            audit_csv_path: Ruta del archivo CSV para auditoría. Por defecto es None.
            enable_fast_executemany: Si True (default) y el engine es mssql+pyodbc,
                activa fast_executemany en el dialecto del engine, igual que
                ``create_engine(..., fast_executemany=True)`` (afecta a todo el engine).
                Medido en SQL Server 2022 + ODBC Driver 18: INSERT ~12× más rápido.
                Poner a False si el entorno SQL Server no lo soporta
                (p.ej. NVARCHAR(MAX) en pyodbc < 4.0.28 con algunas configuraciones).
            insert_resolver: Estrategia INSERT personalizada. None usa la resolución
                automática (execute_values para postgresql+psycopg2, default para el resto).
            commit_every_n_chunks: Si se indica (entero ≥ 1), commitea cada N lotes de
                ``chunk_size`` filas en lugar de en una única transacción al final. **Crítico
                para MariaDB/MySQL en cargas masivas** (millones de filas) donde el undo log
                crece linealmente y el buffer pool se satura, causando degradación exponencial
                de latencia.

                | BD | Buffer Pool | Recomendado | Aprox. Filas/commit |
                |---|---|---|---|
                | MariaDB 8.0 | 256 MB | 10 | 50 K |
                | MariaDB 8.0 | 1 GB | 20 | 100 K |
                | MariaDB 8.0 | 4 GB+ | 50 | 250 K |
                | MySQL 8.0 | 1 GB | 20 | 100 K |

                **Ejemplo de tuning** (10M filas en MariaDB con 1 GB buffer pool)::

                    bulk = BulkCrud(engine, chunk_size=5_000, commit_every_n_chunks=20)
                    bulk.bulk_insert_from_df(df_10m, "tabla_destino")
                    # Commitea cada 20 × 5_000 = 100 K filas → undo log limitado

                ``None`` (default) = una sola transacción (comportamiento atómico).
                **Advertencia:** al activar la cadencia la sesión deja de ser atómica:
                un fallo a mitad deja committeados los lotes anteriores.
                **Nota:** Los valores recomendados son heurísticos; mide latencia en tu entorno.
            update_via_staging: Solo MySQL/MariaDB. Si True, ``bulk_update_from_df`` carga cada lote en una tabla
                temporal y aplica un único ``UPDATE ... JOIN`` en lugar de un UPDATE por fila. Medido de extremo a
                extremo: ~12,5× más rápido (1M filas en ~28 s frente a ~330–376 s). Mismo resultado final. Requiere
                el privilegio ``CREATE TEMPORARY TABLES``: si el servidor lo deniega, se registra un WARNING y se
                usa el UPDATE fila a fila (más lento) en esa y las siguientes llamadas de la instancia. Pasar False
                para no intentarlo. Por defecto True. Ignorado en otros motores.
            audit_strict: Qué hacer si no se puede escribir el CSV de auditoría (fichero abierto en Excel, disco lleno,
                permisos). Con False (default) la operación sigue, porque sus datos ya están en la BD: se registra un
                ERROR con los registros perdidos y se suman a :attr:`audit_failures`. Con True se propaga el error
                (``AuditError``/``OSError``); dentro de :meth:`bulk_session` la auditoría se escribe entonces antes
                del commit y el fallo deshace la sesión.
            warn_if_audit_disabled: Si True (default), sin ``audit_csv_path`` la instancia avisa una vez con un WARNING
                de que la auditoría está deshabilitada. Quien crea muchas instancias (``ParallelBulkLoader``, ``dump``)
                pasa False y avisa una sola vez por su cuenta.
            strip_strings: Si True (default), quita los espacios de los extremos de las cadenas antes de enviarlas,
                como :func:`normalize_sql_literal`. Con False se envían intactas; ``dump`` lo usa para copiar el
                origen sin alterarlo (PD-05).
            reflect_foreign_keys: Si True (default), la ``Table`` de :meth:`reflect_table` incluye las claves foráneas
                de la tabla. Las operaciones de ``BulkCrud`` no las usan: con False no se leen y la reflexión es más
                barata (SQL Server: ≈ 32 → 16 ms por tabla). ``dump`` lo usa (Q9).

        Raises:
            ValueError: Si engine es None.
            ValueError: Si ``commit_every_n_chunks`` no es None ni un entero ≥ 1.
            ValueError: Si ``chunk_size`` no es un entero ≥ 1.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.engine: Engine = validate_engine(engine)
        self._table_cache: dict[str, Table] = {}

        if commit_every_n_chunks is not None and commit_every_n_chunks < 1:
            raise ValueError(f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {commit_every_n_chunks}")

        # Auditoría de bulk 2026-09-24: con un valor negativo no se escribía nada y la auditoría registraba las filas.
        self.chunk_size: int = validate_chunk_size(chunk_size)
        self.audit_manager: AuditManager = AuditManager(audit_csv_path, warn_if_disabled=warn_if_audit_disabled)
        self._update_via_staging: bool = update_via_staging and self.engine.dialect.name in MYSQL_FAMILY
        self._strip_strings: bool = strip_strings
        self._reflect_foreign_keys: bool = reflect_foreign_keys

        # Inicializar db_info
        self.db_info: str = self.engine.dialect.name.upper()

        # Detectar driver específico para SQL Server
        self.__detectar_sqlserver_driver()

        # Validar y loguear configuración MySQL/MariaDB si aplica
        self.__validate_mysql_config()

        self._persistence: BulkPersistenceManager = BulkPersistenceManager(
            engine_url=str(self.engine.url),
            logger=self.logger,
            audit_manager=self.audit_manager,
            db_info=self.db_info,
            audit_strict=audit_strict,
        )
        # Conexión de bulk_session() y gancho de commit, compartidos por los dos ejecutores (R14).
        self._session: SessionScope = SessionScope()
        self._batch_statement_executor: BatchStatementExecutor = BatchStatementExecutor(
            engine=self.engine,
            chunk_size=self.chunk_size,
            enable_fast_executemany=enable_fast_executemany,
            insert_resolver=insert_resolver,
            commit_every_n_chunks=commit_every_n_chunks,
            session=self._session,
        )
        self._delete_batch_executor: DeleteBatchExecutor = DeleteBatchExecutor(
            engine=self.engine,
            chunk_size=self.chunk_size,
            commit_every_n_chunks=commit_every_n_chunks,
            session=self._session,
        )
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

    def __validate_mysql_config(self) -> None:
        """Valida y loguea configuración MySQL/MariaDB para bulk operations.

        Lee variables críticas (max_allowed_packet, innodb_buffer_pool_size)
        e identifica potenciales problemas antes de cargas masivas.

        Solo se ejecuta para motores 'mysql' o 'mariadb'; sin-op para otros.
        """
        if self.engine.dialect.name not in MYSQL_FAMILY:
            return

        try:
            from ..connection.mariadb import MySQLOptimalConfig, MySQLVariableValidator
        except ImportError:
            self.logger.debug("Módulos MySQL validation no disponibles; saltando validación")
            return

        try:
            # Crear conexión temporal para leer variables
            with self.engine.connect() as conn:
                validator = MySQLVariableValidator(conn)

                # Leer variables actuales
                current_vars = validator.read_variables()
                if current_vars:
                    # Log informativo
                    var_strs = [f"{k}={validator.format_bytes(v)}" for k, v in current_vars.items()]
                    self.logger.info(f"MySQL/MariaDB variables: {', '.join(var_strs)}")

                    # Obtener configuración recomendada
                    recommended_config = MySQLOptimalConfig.production()
                    required_vars = {
                        "max_allowed_packet": recommended_config.max_allowed_packet,
                        "innodb_buffer_pool_size": recommended_config.innodb_buffer_pool_size,
                    }

                    # Validar
                    is_valid = validator.validate(required_vars)
                    if not all(is_valid.values()):
                        invalid_vars = [k for k, v in is_valid.items() if not v]
                        self.logger.warning(
                            f"Variables MySQL por debajo de lo recomendado: {', '.join(invalid_vars)}. "
                            f"Para bulk operations, considera: "
                            f"SET GLOBAL max_allowed_packet = 67108864; "
                            f"SET GLOBAL innodb_buffer_pool_size = 1073741824; "
                            f"(requiere privilegio SUPER o SYSTEM_VARIABLES_ADMIN)"
                        )

        except Exception as exc:
            self.logger.debug(f"Error validando configuración MySQL: {exc}")

    def __validar_y_generar_path_sql(self, path_sql: Path | None, tabla_destino: str, operacion: str) -> Path:
        """
        Valida path_sql y genera el nombre dinámico combinado con la ruta proporcionada.

        Args:
            path_sql: Ruta base donde guardar el archivo SQL.
            tabla_destino: Nombre de la tabla.
            operacion: Tipo de operación (insert, update, delete).

        Returns:
            Path completa con el nombre dinámico.

        Raises:
            ValueError: Si path_sql es None o no es un Path válido.
        """
        return self._persistence.resolve_sql_output_path(path_sql, tabla_destino, operacion)

    @medir_tiempo("bulk_insert_from_df")
    def bulk_insert_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> None:
        """
        Inserta en bloque los datos del DataFrame en la tabla destino, o genera la SQL si se indica.

        Args:
            df: DataFrame con los datos.
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Si True, genera la sentencia SQL en texto.
            path_sql: Ruta donde guardar el archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.
            override_identity: Si True y el motor es PostgreSQL, genera INSERT con
                     OVERRIDING SYSTEM VALUE para columnas GENERATED ALWAYS AS IDENTITY.
                     Ignorado en otros motores. Por defecto False.
            exclude_autoincrement_pk: Si True, excluye la columna PK autoincremental/identity
                     del INSERT (tanto en ejecución como en generación SQL). El DataFrame original
                     no se modifica. Solo afecta a INSERT; no a UPDATE ni DELETE. Por defecto False.

        Raises:
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.
            ValueError: Si el DataFrame es vacío o si hay errores de SQL.
            ValueError: Si override_identity=False y el DataFrame incluye columnas
                     GENERATED ALWAYS AS IDENTITY en PostgreSQL.

        La operación se registra en auditoría si fue configurada.
        """
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="insert",
            override_identity=override_identity,
            exclude_autoincrement_pk=exclude_autoincrement_pk,
        )

    @medir_tiempo("bulk_update_from_df")
    def bulk_update_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
    ) -> None:
        """
        Actualiza en bloque los registros del DataFrame en la tabla destino.

        Args:
            df: DataFrame con los datos a actualizar.
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Si True, genera la sentencia SQL en texto.
            path_sql: Ruta donde guardar el archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.

        Raises:
            ValueError: Si no hay claves primarias o columnas actualizables.
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.

        La operación se registra en auditoría si fue configurada.
        """
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="update",
        )

    @medir_tiempo("bulk_delete_from_df")
    def bulk_delete_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
    ) -> None:
        """
        Borra en bloque registros del DataFrame desde la tabla destino.

        Args:
            df: DataFrame con los datos a borrar (debe contener claves primarias).
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Si True, genera la sentencia SQL en texto.
            path_sql: Ruta donde guardar el archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.

        Raises:
            ValueError: Si no hay columnas de clave primaria disponibles.
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.

        La operación se registra en auditoría si fue configurada.
        """
        self.__run_bulk_pipeline(
            df=df,
            tabla_destino=tabla_destino,
            generar_sql=generar_sql,
            path_sql=path_sql,
            strategy_key="delete",
        )

    @medir_tiempo("bulk_insert_from_chunks")
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
        tabla: Table = self.reflect_table(tabla_destino)
        total: int = 0
        resolved: tuple[Any, list[str]] | None = None

        with self.bulk_session():
            for chunk in chunks:
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

                records_sql: list[dict[str, Any]] = dataframe_to_sql_records(
                    working_df[insert_cols], strip_strings=self._strip_strings
                )
                restore_binary_values(records_sql, tabla)  # P-21
                numero_registros: int = len(records_sql)

                start: float = perf_counter()
                self.__ejecutar_batch_stmt(records_sql, stmt, numero_registros)
                elapsed: float = perf_counter() - start
                total += numero_registros

                self._persistence.register_operation(
                    table_name=tabla_destino,
                    operation="INSERT",
                    rowcount=numero_registros,
                    elapsed=elapsed,
                    generated_sql=False,
                )

        self.logger.info(f"✅ bulk INSERT (chunks) finalizado: {total} filas ({self.db_info}).")
        return total

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

    def __run_bulk_pipeline(
        self,
        *,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool,
        path_sql: Path | None,
        strategy_key: Literal["insert", "update", "delete"],
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> None:
        """Template Method para operaciones bulk con estrategia por operación."""
        if generar_sql:
            path_sql = self.__validar_y_generar_path_sql(path_sql, tabla_destino, strategy_key)
        else:
            path_sql = None

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
            if generar_sql:
                self.__guardar_fichero_sql(prepared_operation.generate_sql_lines(), path_sql)
            else:
                prepared_operation.execute()
            elapsed: float = perf_counter() - start

            self._persistence.register_operation(
                table_name=tabla_destino,
                operation=operation_name,
                rowcount=prepared_operation.rowcount,
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
            return self.__record_blocks(insert_df, tabla)

        def execute_blocks(stmt_exec: Any) -> None:
            with self.__blocks_transaction():
                for block in blocks():
                    self.__ejecutar_batch_stmt(block, stmt_exec, len(block))

        def sql_blocks() -> Iterator[SqlColumns]:
            return self.__sql_blocks(insert_df, tabla)

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

    def __record_blocks(self, df: pd.DataFrame, tabla: Table) -> Iterator[list[dict[str, Any]]]:
        """Registros de ``chunk_size`` en ``chunk_size`` filas, el lote del ejecutor (P-07).

        Antes se convertía todo el DataFrame a registros antes del primer lote: el pico de memoria era 3,8–4,7 veces
        el DataFrame al ejecutar y 8,9–9,5 veces al generar SQL (200K filas).
        """
        for start in range(0, len(df), self.chunk_size):
            records: list[dict[str, Any]] = dataframe_to_sql_records(
                df.iloc[start : start + self.chunk_size], strip_strings=self._strip_strings
            )
            restore_binary_values(records, tabla)  # P-21
            yield records

    def __sql_blocks(self, df: pd.DataFrame, tabla: Table) -> Iterator[SqlColumns]:
        """Como :meth:`__record_blocks`, por columnas, para generar SQL sin un diccionario por fila (P-34)."""
        for start in range(0, len(df), self.chunk_size):
            block = SqlColumns(
                *dataframe_to_sql_columns(df.iloc[start : start + self.chunk_size], strip_strings=self._strip_strings)
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
            for records in self.__record_blocks(update_df, tabla):
                for record in records:
                    for original_col, alias_col in update_plan.pk_param_map.items():
                        record[alias_col] = record[original_col]
                yield records

        def sql_blocks() -> Iterator[SqlColumns]:
            for block in self.__sql_blocks(update_df, tabla):
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
        staging: MySQLStagingUpdateStrategy | None = None
        if self._update_via_staging:
            staging = MySQLStagingUpdateStrategy(
                table=tabla,
                pk_cols=update_plan.pk_cols,
                update_cols=update_plan.update_cols,
                loader=executor.insert_strategy,
            )
        with self.__blocks_transaction():
            for block in blocks:
                executor.execute(records=block, stmt=stmt, strategy=staging)
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

    def __ejecutar_batch_stmt(self, records: Sequence[Mapping[str, Any]], stmt: Any, numero_registros: int) -> None:
        """Ejecuta un statement de SQLAlchemy por lotes.

        Args:
            records: lista de diccionarios con datos a procesar.
            stmt: Statement SQLAlchemy (Insert, Update, Delete).
            numero_registros: Total de registros (para logging).
        """
        self._batch_statement_executor.execute(records=records[:numero_registros], stmt=stmt)

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
        self._delete_batch_executor.execute(
            table=tabla,
            df=df,
            pk_cols=pk_cols,
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
        if self._reflect_foreign_keys:
            tabla = Table(tabla_normalizada, metadata, schema=schema, autoload_with=self.engine, resolve_fks=False)
        else:
            tabla = Table(tabla_normalizada, metadata, schema=schema)
            self._reflect_without_foreign_keys(tabla)
        self._table_cache[tabla_destino] = tabla
        return tabla

    def _reflect_without_foreign_keys(self, tabla: Table) -> None:
        """Rellena ``tabla`` desde la BD como ``Table(..., autoload_with=engine, resolve_fks=False)``, sin leer sus FK.

        Q9 (performance-audit de dump 2026-09-26): en SQL Server,
        ``get_foreign_keys`` es la mitad de la reflexión (≈ 17 de 32 ms por tabla) y ``BulkCrud`` no usa las FK.
        ``Table(autoload_with=...)`` crea su propio Inspector, así que se usa ``Inspector.reflect_table``, que pide las
        FK a ``get_multi_foreign_keys`` de la misma instancia. Si una versión de SQLAlchemy dejara de hacerlo, la
        sustitución no tendría efecto: se volverían a reflejar las FK (más lento, mismo resultado para ``BulkCrud``).
        """
        with self.engine.connect() as conn:
            insp: Inspector = inspect(conn)
            insp.get_multi_foreign_keys = _no_foreign_keys  # type: ignore[method-assign]
            insp.reflect_table(tabla, None, resolve_fks=False)

    @property
    def audit_failures(self) -> int:
        """Registros de auditoría que no se pudieron escribir en el CSV (solo con ``audit_strict=False``).

        Cada uno queda además en el log como ERROR, con tabla, operación, filas y tiempo.
        """
        return self._persistence.audit_failures

    @property
    def audited_rows(self) -> int:
        """Filas (``rowcount``) de los registros escritos en el CSV de auditoría por esta instancia.

        Con auditoría activa y sin incidencias coincide con las filas cargadas. La diferencia se explica con
        :attr:`audit_failures`, :attr:`unaudited_committed_rows` y :attr:`audit_uncommitted_records`. Incluye las
        operaciones con ``generar_sql=True``, que no tocan la BD.
        """
        return self._persistence.audited_rows

    @property
    def audit_uncommitted_records(self) -> int:
        """Registros escritos en el CSV antes de un commit que falló (solo con ``audit_strict=True``).

        En modo estricto la auditoría de :meth:`bulk_session` se escribe antes del commit; si el commit falla, esos
        registros quedan en el CSV sin datos en la BD. Cada caso queda además en el log como ERROR.
        """
        return self._persistence.audit_uncommitted_records

    @property
    def unaudited_committed_rows(self) -> int:
        """Filas confirmadas por commits periódicos que no constan en el CSV (``commit_every_n_chunks``).

        Si una sesión falla, la operación que tenía parte de sus lotes confirmados no se audita. Esas filas están en la
        BD (y en :attr:`rows_committed`) pero no en el CSV. Cuenta INSERT, UPDATE y DELETE (hasta v0.17.x era
        aproximado en sesiones con DELETE, que no sumaba a :attr:`rows_committed`).
        """
        return self._persistence.unaudited_committed_rows

    @property
    def rows_committed(self) -> int:
        """Filas durablemente comprometidas en BD por esta instancia hasta el momento.

        Cuenta las filas enviadas de INSERT, UPDATE y DELETE (``len(df)``, como el CSV de auditoría; no las que la BD dice
        haber modificado). Hasta v0.17.x no contaba las del DELETE.

        BLK-08 (AUDIT_CODE 2026-09-22): solo avanza cuando la instancia se construyó
        con ``commit_every_n_chunks`` — cada vez que se alcanza el commit periódico
        o el commit final de ``bulk_session()``. En modo atómico (default, sin
        ``commit_every_n_chunks``) permanece en 0: un fallo revierte toda la sesión,
        por lo que no hay filas parciales que reportar como comprometidas.

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

        Nota: si se construyó ``BulkCrud(commit_every_n_chunks=N)``, la sesión usa
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
                        yield
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
            with self.engine.begin() as conn, self._session.bind(conn):
                persistence.start_session_audit(conn)
                yield
                persistence.flush_audit_before_commit()
            persistence.flush_audit_after_commit()
        finally:
            persistence.end_session_audit(committed_rows=committed_rows)

    def get_columna_may_min(self, tabla: Table, nombre_col: str) -> Column | None:
        """Devuelve una columna de una tabla SQLAlchemy ignorando mayúsculas/minúsculas."""
        return get_column_case_insensitive(tabla, nombre_col)

    def obtener_valor_max_columna(self, tabla: Table, nombre_col: str) -> int:
        """Devuelve MAX(nombre_col)+1; retorna 1 si la columna está vacía o el máximo es negativo."""
        return get_max_column_value(self.engine, tabla, nombre_col)

    @contextmanager
    def maintenance_scope(
        self,
        tabla_destino: str,
        disable_constraints: bool = True,
        disable_indexes: bool = False,
        require_optimization: bool = False,
    ) -> Generator[MaintenanceScopeResult, None, None]:
        """Context manager que prepara la tabla para una carga de alto volumen (>1M).

        Deshabilita temporalmente las comprobaciones de integridad y (opcionalmente)
        los índices para maximizar el rendimiento (throughput).

        Soporte por motor:
        - **MariaDB/MySQL**: Deshabilita `FOREIGN_KEY_CHECKS` a nivel de sesión.
          Aplica `DISABLE KEYS` (aunque InnoDB suele ignorarlo; solo efectivo en MyISAM/Aria).
        - **Oracle**: Deshabilita cada FK, CHECK (no SYS_C) y UNIQUE con
          ``ALTER TABLE ... DISABLE CONSTRAINT``. Re-habilita con ``ENABLE VALIDATE``.
        - **PostgreSQL**: Ejecuta ``ALTER TABLE ... DISABLE TRIGGER ALL``. Requiere ser
          propietario de la tabla o superusuario; si no, opera sin optimización (se registra
          un aviso). Al restaurar, ejecuta un orphan-check de FK para detectar violaciones
          cargadas con los triggers desactivados (audit H-01, 2026-09-27).
        - **SQL Server**: Ejecuta ``ALTER TABLE ... NOCHECK CONSTRAINT ALL``. Persiste en
          catálogo pero se restaura al salir del bloque.
          Soporta ``ALTER INDEX ALL ON ... DISABLE`` si ``disable_indexes=True``
          (solo en tablas sin índice CLUSTERED).
        - **SQLite**: No soportado; opera sin optimización.

        Args:
            tabla_destino: Nombre de la tabla destino (acepta "esquema.tabla").
            disable_constraints: Deshabilita FKs y triggers. Por defecto True.
            disable_indexes: Deshabilita índices secundarios (MariaDB, MySQL y SQL Server).
                Por defecto False.
            require_optimization: Si True y la optimización no puede aplicarse (p.ej.
                PostgreSQL sin privilegios suficientes), lanza :exc:`RuntimeError` en lugar
                de continuar en silencio. Por defecto False.

        Yields:
            :class:`MaintenanceScopeResult` con ``optimization_applied`` y
            ``constraint_results`` (disponibles tras salir del bloque ``with``).

        Ejemplo::

            bulk = BulkCrud(engine)
            with bulk.bulk_session():
                with bulk.maintenance_scope("usuarios", disable_indexes=True) as ms:
                    bulk.bulk_insert_from_df(df, "usuarios")
            for r in ms.constraint_results:
                print(r.constraint_name, r.status)

        Raises:
            RuntimeError: Si se invoca fuera de un :meth:`bulk_session` activo, o si
                ``require_optimization=True`` y la optimización no puede aplicarse.
        """
        dialect: str = self.engine.dialect.name
        tabla = self.reflect_table(tabla_destino)
        quoted_name = self.engine.dialect.identifier_preparer.format_table(tabla)

        conn = self._session.connection
        if conn is None:
            raise RuntimeError(
                "maintenance_scope requiere una sesión activa. "
                "Úsalo siempre dentro de bulk_session(): "
                "'with bulk.bulk_session():\\n    with bulk.maintenance_scope(...):\\n        ...'"
            )

        pg_disabled = False
        mssql_constraints_disabled = False
        indexes_disabled = False
        oracle_disabled: list[str] = []
        result = MaintenanceScopeResult()

        def restore() -> list[MaintenanceScopeConstraintResult]:
            if disable_indexes:
                self.__maintenance_enable_indexes(conn, dialect, quoted_name, indexes_disabled)
            if disable_constraints:
                return self.__maintenance_enable_constraints(
                    conn, dialect, quoted_name, tabla, pg_disabled, mssql_constraints_disabled, oracle_disabled
                )
            return []

        try:
            if disable_constraints:
                pg_disabled, mssql_constraints_disabled, oracle_disabled = self.__maintenance_disable_constraints(
                    conn, dialect, quoted_name, tabla, tabla_destino, require_optimization
                )
                result.optimization_applied = (
                    pg_disabled or mssql_constraints_disabled or bool(oracle_disabled) or dialect in MYSQL_FAMILY
                )
            if disable_indexes:
                indexes_disabled = self.__maintenance_disable_indexes(conn, dialect, quoted_name, tabla, tabla_destino)
            self.logger.info(f"🛠️ Modo mantenimiento activado: {tabla_destino} ({dialect})")
            yield result
        except BaseException:
            self.__maintenance_restore_after_error(conn, restore, tabla_destino)
            raise
        result.constraint_results = restore()
        self.logger.debug(f"🛠️ Modo mantenimiento finalizado: {tabla_destino}")

    def __maintenance_restore_after_error(
        self, conn: Any, restore: Callable[[], list[MaintenanceScopeConstraintResult]], tabla_destino: str
    ) -> None:
        """Restaura constraints/índices tras un fallo dentro de ``maintenance_scope`` sin ocultar el error original.

        Auditoría de bulk 2026-09-24: la restauración se hacía en un ``finally`` sobre la misma transacción. En
        PostgreSQL, tras un error la transacción queda abortada, el ``ENABLE TRIGGER`` fallaba y el usuario recibía
        ``InFailedSqlTransaction`` en lugar del error real.

        - Sesión atómica: se intenta restaurar; si la transacción ya no lo admite, basta con el rollback de la sesión,
          que deshace también la desactivación (DDL transaccional en PostgreSQL y SQL Server). Se registra un aviso.
        - Con ``commit_every_n_chunks``: la desactivación pudo quedar confirmada por un commit periódico. Se deshace lo
          pendiente (el rollback de la sesión lo descartaría igual), se restaura y se confirma solo la restauración.
        """
        cadence = self._batch_statement_executor.cadence
        if cadence.every is None:
            try:
                restore()
            except Exception as exc:
                self.logger.warning(
                    f"⚠️ No se restauraron constraints/índices de {tabla_destino} tras el error: la transacción está "
                    f"abortada y su rollback deshace también la desactivación ({type(exc).__name__})."
                )
            return
        try:
            conn.rollback()
            cadence.discard_pending()
            restore()
            conn.commit()
        except Exception as exc:
            self.logger.error(
                f"❌ No se pudieron restaurar constraints/índices de {tabla_destino} tras el error; pueden haber quedado "
                f"deshabilitados por un commit periódico: {exc}"
            )

    def __maintenance_disable_constraints(
        self,
        conn: Any,
        dialect: str,
        quoted_name: str,
        tabla: Table,
        tabla_destino: str,
        require_optimization: bool = False,
    ) -> tuple[bool, bool, list[str]]:
        """Deshabilita constraints por motor; retorna (pg_disabled, mssql_disabled, oracle_names)."""
        if dialect in MYSQL_FAMILY:
            conn.execute(text("SET SESSION FOREIGN_KEY_CHECKS=0"))
            return False, False, []
        if dialect == "postgresql":
            if can_disable_pg_triggers(conn, tabla):
                conn.execute(text(disable_table_integrity_sql(dialect, quoted_name)))
                return True, False, []
            msg = (
                f"⚠️ El usuario actual no tiene privilegios suficientes en PostgreSQL "
                f"(requiere SUPERUSER o ser propietario de la tabla). "
                f"Se omite DISABLE TRIGGER en {tabla_destino}."
            )
            if require_optimization:
                raise RuntimeError(msg)
            self.logger.warning(msg)
            return False, False, []
        if dialect == "mssql":
            conn.execute(text(disable_table_integrity_sql(dialect, quoted_name)))
            return False, True, []
        if dialect == "oracle":
            all_names = self.__oracle_fetch_constraint_names(tabla)
            disabled: list[str] = []
            prep = self.engine.dialect.identifier_preparer
            for name in all_names:
                try:
                    conn.execute(text(f"ALTER TABLE {quoted_name} DISABLE CONSTRAINT {prep.quote_identifier(name)}"))
                    disabled.append(name)
                except SQLAlchemyError as exc:
                    self.logger.warning(f"⚠️ No se pudo deshabilitar constraint '{name}' en {tabla_destino}: {exc}")
            return False, False, disabled
        if require_optimization:
            raise RuntimeError(
                f"El dialecto '{dialect}' no soporta la desactivación de constraints "
                f"en maintenance_scope (tabla: {tabla_destino})."
            )
        return False, False, []

    def __maintenance_disable_indexes(
        self,
        conn: Any,
        dialect: str,
        quoted_name: str,
        tabla: Table,
        tabla_destino: str,
    ) -> bool:
        """Deshabilita índices secundarios por motor; retorna True si se deshabilitaron (hay que restaurarlos)."""
        if dialect in MYSQL_FAMILY:
            # DISABLE KEYS solo tiene efecto en MyISAM/Aria (no transaccionales). En InnoDB el servidor lo ignora, pero
            # como DDL provoca un commit implícito que rompía la atomicidad de la sesión (auditoría de bulk
            # 2026-09-24, hallazgo 8): solo se ejecuta cuando sirve.
            storage_engine = conn.execute(
                text(fetch_table_storage_engine_sql()),
                {"schema": tabla.schema, "tbl": tabla.name},
            ).scalar()
            if str(storage_engine or "").upper() in ("MYISAM", "ARIA"):
                conn.execute(text(f"ALTER TABLE {quoted_name} DISABLE KEYS"))
                return True
            self.logger.info(
                f"ℹ️ Se omite DISABLE KEYS en {tabla_destino}: motor {storage_engine} (solo tiene efecto en MyISAM/Aria "
                "y en InnoDB provocaría un commit implícito)."
            )
            return False
        if dialect == "mssql":
            has_clustered = conn.execute(
                text(fetch_clustered_index_count_sql()),
                {"tbl": tabla_destino},
            ).scalar()
            if has_clustered == 0:
                conn.execute(text(f"ALTER INDEX ALL ON {quoted_name} DISABLE"))
                return True
            self.logger.warning(
                f"⚠️ La tabla {tabla_destino} tiene un índice CLUSTERED. "
                "Se omite la desactivación masiva de índices para mantener la tabla accesible."
            )
        return False

    def __maintenance_enable_indexes(
        self,
        conn: Any,
        dialect: str,
        quoted_name: str,
        disabled: bool,
    ) -> None:
        """Restaura los índices deshabilitados por ``__maintenance_disable_indexes``."""
        if not disabled:
            return
        if dialect in MYSQL_FAMILY:
            conn.execute(text(f"ALTER TABLE {quoted_name} ENABLE KEYS"))
        elif dialect == "mssql":
            conn.execute(text(f"ALTER INDEX ALL ON {quoted_name} REBUILD"))

    def __maintenance_enable_constraints(
        self,
        conn: Any,
        dialect: str,
        quoted_name: str,
        tabla: Table,
        pg_disabled: bool,
        mssql_disabled: bool,
        oracle_disabled: list[str],
    ) -> list[MaintenanceScopeConstraintResult]:
        """Restaura constraints deshabilitadas por motor; retorna resultado por constraint."""
        if dialect in MYSQL_FAMILY:
            conn.execute(text("SET SESSION FOREIGN_KEY_CHECKS=1"))
            return [
                MaintenanceScopeConstraintResult(
                    constraint_name="FOREIGN_KEY_CHECKS",
                    status="unverified",
                    error_msg="FK_CHECKS restaurado; no hay validación retroactiva de integridad.",
                )
            ]
        if dialect == "postgresql" and pg_disabled:
            conn.execute(text(enable_table_integrity_sql(dialect, quoted_name)))
            return self.__pg_check_fk_orphans(conn, tabla, quoted_name)
        if dialect == "mssql" and mssql_disabled:
            conn.execute(text(enable_table_integrity_sql(dialect, quoted_name)))
            return [MaintenanceScopeConstraintResult(constraint_name="ALL", status="enabled")]
        if dialect == "oracle" and oracle_disabled:
            prep = self.engine.dialect.identifier_preparer
            results: list[MaintenanceScopeConstraintResult] = []
            for name in oracle_disabled:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {quoted_name} ENABLE VALIDATE CONSTRAINT {prep.quote_identifier(name)}")
                    )
                    results.append(MaintenanceScopeConstraintResult(constraint_name=name, status="enabled"))
                except SQLAlchemyError as exc:
                    self.logger.warning(f"⚠️ No se pudo rehabilitar constraint '{name}': {exc}")
                    results.append(
                        MaintenanceScopeConstraintResult(constraint_name=name, status="failed", error_msg=str(exc))
                    )
            return results
        return []

    def __pg_check_fk_orphans(
        self, conn: Any, tabla: Table, quoted_name: str
    ) -> list[MaintenanceScopeConstraintResult]:
        """Audit H-01 (2026-09-27): DISABLE TRIGGER no marca FK como NOT VALID; verifica huérfanos explícitamente."""
        try:
            insp = inspect(self.engine)
            fks = insp.get_foreign_keys(tabla.name, schema=tabla.schema)
        except Exception:  # NoInspectionAvailable en mocks de test o motores sin inspector
            self.logger.debug(f"⚠️ orphan-check omitido en '{tabla.name}': inspect() no disponible para este engine.")
            return [
                MaintenanceScopeConstraintResult(
                    constraint_name="*",
                    status="unverified",
                    error_msg="orphan-check omitido: inspect() no disponible para el engine actual.",
                )
            ]
        results: list[MaintenanceScopeConstraintResult] = []
        prep = self.engine.dialect.identifier_preparer
        for fk in fks:
            child_cols: list[str] = fk.get("constrained_columns", [])
            parent_table: str = fk.get("referred_table", "")
            parent_cols: list[str] = fk.get("referred_columns", [])
            if not child_cols or not parent_cols or not parent_table:
                continue
            if len(child_cols) != len(parent_cols):
                continue  # metadata FK malformada
            # MATCH SIMPLE: NULL en alguna columna FK exime la fila de la comprobación
            not_null = " AND ".join(f"c.{prep.quote(col)} IS NOT NULL" for col in child_cols)
            match_cond = " AND ".join(
                f"p.{prep.quote(pc)} = c.{prep.quote(cc)}" for cc, pc in zip(child_cols, parent_cols, strict=True)
            )
            parent_schema: str | None = fk.get("referred_schema")
            parent_ref = (
                f"{prep.quote_identifier(parent_schema)}.{prep.quote_identifier(parent_table)}"
                if parent_schema
                else prep.quote_identifier(parent_table)
            )
            fk_name = fk.get("name") or "?"
            try:
                orphan = conn.execute(
                    text(
                        f"SELECT 1 FROM {quoted_name} c "
                        f"WHERE {not_null} "
                        f"AND NOT EXISTS (SELECT 1 FROM {parent_ref} p WHERE {match_cond}) LIMIT 1"
                    )
                ).first()
            except SQLAlchemyError:
                continue
            if orphan is not None:
                msg = (
                    f"FK '{fk_name}' en '{tabla.name}': hay filas sin fila referenciada "
                    f"en '{parent_table}'. La FK está marcada como válida pero contiene violaciones. "
                    "Verificar integridad manualmente o hacer rollback."
                )
                self.logger.warning(f"⚠️ {msg}")
                results.append(
                    MaintenanceScopeConstraintResult(constraint_name=fk_name, status="failed", error_msg=msg)
                )
            else:
                results.append(MaintenanceScopeConstraintResult(constraint_name=fk_name, status="enabled"))
        return results

    def __oracle_fetch_constraint_names(self, tabla: Table) -> list[str]:
        """Retorna nombres de FK, CHECK (no SYS_C) y UNIQUE constraints de la tabla para Oracle."""
        try:
            insp = inspect(self.engine)
            schema = tabla.schema
            name = tabla.name
            names: list[str] = []
            names += [str(fk["name"]) for fk in insp.get_foreign_keys(name, schema=schema) if fk.get("name")]
            names += [
                str(c["name"])
                for c in insp.get_check_constraints(name, schema=schema)
                if c.get("name") and not str(c["name"]).upper().startswith("SYS_C")
            ]
            names += [str(u["name"]) for u in insp.get_unique_constraints(name, schema=schema) if u.get("name")]
            return names
        except Exception:  # NoInspectionAvailable en mocks de test o conexión sin permisos
            return []

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


# Alias retrocompatible — la API pública histórica usaba snake_case.
bulk_crud = BulkCrud
