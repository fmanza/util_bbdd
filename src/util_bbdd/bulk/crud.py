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

import logging

from collections.abc import Callable, Hashable, Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from sqlalchemy import (
    Column,
    ColumnElement,
    Engine,
    Insert,
    MetaData,
    Table,
    Update,
    and_,
    bindparam,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ._batch_execution import (
    execute_batch_statement,
    execute_delete_batch,
)
from ._persistence import BulkPersistenceManager
from ._sql_helpers import (
    generate_delete_sql,
    generate_insert_sql,
    generate_update_sql,
)
from ._validation import (
    build_update_plan,
    get_insert_columns,
    get_pk_columns,
    normalize_dataframe_columns,
    validate_engine,
)
from .audit import AuditManager
from .normalize import normalize_records_for_sql

try:
    from util.medir_tiempo import medir_tiempo as _medir_tiempo
except ImportError:

    def _medir_tiempo(proceso: str = "") -> Callable[[Any], Any]:
        _: str = proceso

        def _decorator(function: Any) -> Any:
            return function

        return _decorator


medir_tiempo: Any = _medir_tiempo


class bulk_crud:
    """Realiza operaciones CRUD en lote sobre bases de datos usando SQLAlchemy."""

    def __init__(self, engine: Engine | None, chunk_size: int = 5000, audit_csv_path: Path | None = None):
        """
        Constructor de la clase bulk_crud.

        Args:
            engine: Engine de SQLAlchemy para las operaciones. Obligatorio.
            chunk_size: Tamaño del lote para procesar. Por defecto es 5000.
            audit_csv_path: Ruta del archivo CSV para auditoría. Por defecto es None.

        Raises:
            ValueError: Si engine es None.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        self.engine: Engine = validate_engine(engine)

        self.chunk_size: int = chunk_size
        self.audit_manager: AuditManager = AuditManager(audit_csv_path)

        # Inicializar db_info
        self.db_info: str = self.engine.dialect.name.upper()

        # Detectar driver específico para SQL Server
        self.__detectar_sqlserver_driver()
        self._persistence: BulkPersistenceManager = BulkPersistenceManager(
            engine_url=str(self.engine.url),
            logger=self.logger,
            audit_manager=self.audit_manager,
            db_info=self.db_info,
        )

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
    ):
        """
        Inserta en bloque los datos del DataFrame en la tabla destino, o genera la SQL si se indica.

        Args:
            df: DataFrame con los datos.
            tabla_destino: Nombre de la tabla destino.
            generar_sql: Si True, genera la sentencia SQL en texto.
            path_sql: Ruta donde guardar el archivo SQL. Es obligatorio si generar_sql=True.
                     El nombre del archivo se genera dinámicamente y se combina con esta ruta.

        Raises:
            ValueError: Si generar_sql=True y path_sql no es proporcionado o no es válido.
            ValueError: Si el DataFrame es vacío o si hay errores de SQL.

        La operación se registra en auditoría si fue configurada.
        """
        # Validar y generar ruta completa si se genera SQL
        if generar_sql:
            path_sql = self.__validar_y_generar_path_sql(path_sql, tabla_destino, "insert")
        else:
            path_sql = None

        self.__actualizar_df(df)
        tabla: Table = self.reflect_table(tabla_destino)
        insert_cols: list[str] = get_insert_columns(list(df.columns), tabla)
        records: list[dict[Hashable, Any]] = df[insert_cols].to_dict(orient="records")

        try:
            numero_registros: int = len(records)
            stmt: Insert = insert(tabla)
            records_sql: list[dict] = normalize_records_for_sql(records)

            # Medir tiempo de ejecución
            start: float = perf_counter()

            # Generar SQL
            if generar_sql:
                sql_lines: list = self.__generar_sql_insert(stmt, records_sql)
                self.__guardar_fichero_sql(sql_lines, path_sql)

            # Ejecutar SQL
            else:
                self.__ejecutar_batch_stmt(records_sql, stmt, numero_registros)

            elapsed: float = perf_counter() - start

            # Registrar operación finalizada
            self._persistence.register_operation(
                table_name=tabla_destino,
                operation="INSERT",
                rowcount=numero_registros,
                elapsed=elapsed,
                generated_sql=generar_sql,
            )
            self.logger.info(f"✅ bulk INSERT finalizado ({self.db_info}).")
        except SQLAlchemyError as e:
            self.logger.error(f"❌ Error en bulk INSERT: {e}")
            raise
        finally:
            df.columns = df.columns.str.upper()

    @medir_tiempo("bulk_update_from_df")
    def bulk_update_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
    ):
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
        # Validar y generar ruta completa si se genera SQL
        if generar_sql:
            path_sql = self.__validar_y_generar_path_sql(path_sql, tabla_destino, "update")
        else:
            path_sql = None

        self.__actualizar_df(df)
        tabla: Table = self.reflect_table(tabla_destino)
        try:
            update_plan = build_update_plan(tabla, list(df.columns), tabla_destino)
        except ValueError as error:
            self.logger.error(str(error))
            raise

        records: list[dict[Hashable, Any]] = df.to_dict(orient="records")
        records_sql: list[dict] = normalize_records_for_sql(records)

        for r in records_sql:
            for orig, alias in update_plan.pk_param_map.items():
                r[alias] = r[orig]

        try:
            numero_registros: int = len(records_sql)
            start: float = perf_counter()

            if generar_sql:
                sql_lines: list = self.__generar_sql_update(
                    tabla,
                    records_sql,
                    update_plan.update_cols,
                    update_plan.pk_param_map,
                    update_plan.pk_cols,
                )
                self.__guardar_fichero_sql(sql_lines, path_sql)
            else:
                where_clause: ColumnElement[bool] = and_(
                    *(tabla.c[col] == bindparam(update_plan.pk_param_map[col]) for col in update_plan.pk_cols)
                )
                stmt: Update = (
                    update(tabla).where(where_clause).values({col: bindparam(col) for col in update_plan.update_cols})
                )
                self.__ejecutar_batch_stmt(records_sql, stmt, numero_registros)

            elapsed: float = perf_counter() - start

            # Registrar operación finalizada
            self._persistence.register_operation(
                table_name=tabla_destino,
                operation="UPDATE",
                rowcount=numero_registros,
                elapsed=elapsed,
                generated_sql=generar_sql,
            )
            self.logger.info(f"✅ bulk UPDATE finalizado ({self.db_info}).")
        except SQLAlchemyError as e:
            self.logger.error(f"❌ Error en bulk UPDATE: {e}")
            raise
        finally:
            df.columns = df.columns.str.upper()

    @medir_tiempo("bulk_delete_from_df")
    def bulk_delete_from_df(
        self,
        df: pd.DataFrame,
        tabla_destino: str,
        generar_sql: bool = True,
        path_sql: Path | None = None,
    ):
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
        # Validar y generar ruta completa si se genera SQL
        if generar_sql:
            path_sql = self.__validar_y_generar_path_sql(path_sql, tabla_destino, "delete")
        else:
            path_sql = None

        # Actualizar DataFrame para que las columnas sean mayúsculas
        self.__actualizar_df(df)
        # Obtener tabla reflejada con SQLAlchemy
        tabla: Table = self.reflect_table(tabla_destino)
        # Obtener columnas PK de la tabla
        pk_cols: list[str] = self.__obtener_pk_cols(tabla, df.columns)

        try:
            # Numero de registros a borrar
            numero_registros: int = len(df)
            start: float = perf_counter()

            if generar_sql:
                # Generar sentencia SQL y guardar en archivo
                self.__generar_y_guardar_sql_delete(df, tabla, pk_cols, path_sql)
            else:
                # Ejecutar en bloque
                self.__ejecutar_delete_batch(df, tabla, tabla_destino, pk_cols, numero_registros)

            elapsed: float = perf_counter() - start

            # Registrar ejecución finalizada de operación
            self._persistence.register_operation(
                table_name=tabla_destino,
                operation="DELETE",
                rowcount=numero_registros,
                elapsed=elapsed,
                generated_sql=generar_sql,
            )
            self.logger.info(f"✅ bulk DELETE finalizado ({self.db_info}).")
        except SQLAlchemyError as e:
            # Registrar error
            self.logger.error(f"❌ Error en bulk DELETE: {e}")
            raise
        finally:
            # Actualizar DataFrame para que las columnas sean mayúsculas
            df.columns = df.columns.str.upper()

    def __ejecutar_batch_stmt(self, records: list[dict[Hashable, Any]], stmt, numero_registros: int):
        """Ejecuta un statement de SQLAlchemy por lotes.

        Args:
            records: lista de diccionarios con datos a procesar.
            stmt: Statement SQLAlchemy (Insert, Update, Delete).
            numero_registros: Total de registros (para logging).
        """
        records_to_execute: Sequence[Mapping[str, Any]] = [
            {str(key): value for key, value in record.items()} for record in records[:numero_registros]
        ]
        execute_batch_statement(
            engine=self.engine,
            records=records_to_execute,
            stmt=stmt,
            chunk_size=self.chunk_size,
        )

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

    def __generar_y_guardar_sql_delete(
        self, df: pd.DataFrame, tabla: Table, pk_cols: list[str], fichero_sql: Path | None
    ):
        """Genera y guarda el SQL de DELETE."""
        sql_lines: list = self.__generar_sql_delete(df, tabla, pk_cols)
        self.__guardar_fichero_sql(sql_lines, fichero_sql)

    def __ejecutar_delete_batch(
        self,
        df: pd.DataFrame,
        tabla: Table,
        tabla_destino: str,
        pk_cols: list[str],
        numero_registros: int,
    ):
        """Ejecuta borrado por lotes en la base de datos."""
        del numero_registros
        execute_delete_batch(
            engine=self.engine,
            table=tabla,
            table_name=tabla_destino,
            df=df,
            pk_cols=pk_cols,
            chunk_size=self.chunk_size,
        )

    def __actualizar_df(self, df: pd.DataFrame):
        """Normaliza nombres de columnas según el dialecto de BBDD.

        Args:
            df: DataFrame a normalizar.

        Comportamiento de dialectos:
            - oracle: Minúsculas (identifiers sin comillas se tratan como minúsculas)
            - postgresql: Minúsculas (identifiers sin comillas se tratan como minúsculas)
            - sqlite: Minúsculas (comportamiento nativo de SQLite)
            - mysql/mariadb: Mayúsculas (comportamiento nativo de MySQL)
            - mssql: Mayúsculas (identifiers por defecto en SQL Server)
            - hsqldb: Mayúsculas (comportamiento nativo de HSQLDB)
        """
        normalize_dataframe_columns(df, self.engine.dialect.name, self.logger)
        df = df.replace({np.nan: None})

    def reflect_table(self, tabla_destino: str) -> Table:
        """
        Refleja una tabla desde la base de datos y devuelve el objeto `Table` correspondiente.

        Args:
            tabla_destino: Nombre lógico de la tabla (no se tiene en cuenta el caso).

        Returns:
            El objeto `Table` reflejado.
        """
        metadata = MetaData()
        tabla_destino = tabla_destino.lower()
        tabla = Table(tabla_destino, metadata, autoload_with=self.engine)
        return tabla

    def get_columna_may_min(self, tabla: Table, nombre_col: str) -> Column | None:
        """
        Devuelve una columna de una tabla SQLAlchemy ignorando mayúsculas/minúsculas.

        Args:
            tabla: Objeto `Table` de SQLAlchemy.
            nombre_col: Nombre lógico de la columna (sin preocuparse por el caso).

        Returns:
            La columna si se encuentra; None en caso contrario.
        """
        # Crear un diccionario con nombres en minúsculas como claves
        # para evitar que se tengan en cuenta el caso
        columnas: dict[str, Column[Any]] = {col.name.lower(): col for col in tabla.columns}

        # Buscar la columna en el diccionario
        # y devolverla si se encuentra
        return columnas.get(nombre_col.lower())

    def obtener_valor_max_columna(self, tabla: Table, nombre_col: str) -> int:
        """
        Obtiene el valor máximo de una columna en una tabla SQLAlchemy.

        Parameters
        ----------
        tabla : Table
            Objeto Table reflejado o definido con SQLAlchemy
        nombre_col : str
            Nombre de la columna (insensible a mayúsculas)

        Returns
        -------
        int
            Valor máximo como entero, controlando si es None o negativo
        """
        # Obtener columna de la tabla
        col: Column[Any] | None = next((c for c in tabla.columns if c.name.lower() == nombre_col.lower()), None)
        if col is None:
            # Lanzar excepción si no se encuentra la columna
            raise ValueError(f"Columna '{nombre_col}' no encontrada en la tabla '{tabla.name}'")

        # Crear sentencia SQL para obtener el valor máximo de la columna
        stmt = select(func.max(col))
        # Ejecutar sentencia SQL y obtener el valor máximo
        with Session(self.engine) as session:
            # Obtener el valor máximo de la columna
            max_val: int | None = session.execute(stmt).scalar_one_or_none()

        # Controlar que el valor no sea None o negativo
        if max_val is None or max_val < 0:
            # Si es None o negativo, establecer en 1
            max_val = 1
        else:
            # Incrementar en 1 el valor máximo
            max_val = max_val + 1

        # Devolver el valor máximo
        return max_val

    def __generar_sql_insert(self, stmt: Insert, records: list[dict]) -> list:
        """Genera SQL INSERT desde un statement y una lista de registros.

        Maneja valores binarios convirtiendo a hexadecimal.
        """
        return generate_insert_sql(stmt, records, self.engine.dialect)

    def __generar_sql_update(
        self,
        tabla: Table,
        records: list[dict],
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

    def __guardar_fichero_sql(self, sql_lines: list, fichero_sql: Path | None):
        """Guarda las líneas SQL en un archivo o las imprime en log.

        Args:
            sql_lines: lista de líneas SQL.
            fichero_sql: Ruta del archivo destino. Si es None, imprime en log.
        """
        self._persistence.persist_sql(sql_lines, fichero_sql)
