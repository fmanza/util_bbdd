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

from collections.abc import Callable, Hashable
from datetime import date, datetime, time
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from sqlalchemy import (
    Column,
    ColumnElement,
    Delete,
    Engine,
    Insert,
    MetaData,
    Table,
    Update,
    and_,
    bindparam,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .audit import AuditManager
from .normalize import normalize_records_for_sql

# Importar HSQLDB dinámicamente si está disponible
try:
    from sqlalchemy.dialects import hsqldb  # type: ignore
except ImportError:
    hsqldb = None

# Importar SQLite dinámicamente si está disponible
try:
    from sqlalchemy.dialects import sqlite  # type: ignore
except ImportError:
    sqlite = None

try:
    from util.medir_tiempo import medir_tiempo as _medir_tiempo
except ImportError:

    def _medir_tiempo(proceso: str = "") -> Callable[[Any], Any]:
        _ = proceso

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

        if engine is not None:
            self.engine: Engine = engine
        else:
            raise ValueError("❌ 'engine' no puede ser None")

        self.chunk_size: int = chunk_size
        self.audit_manager: AuditManager = AuditManager(audit_csv_path)

        # Inicializar db_info
        self.db_info: str = self.engine.dialect.name.upper()

        # Detectar driver específico para SQL Server
        self.__detectar_sqlserver_driver()

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

    def __generar_nombre_sql_dinamico(self, tabla: str, operacion: str) -> Path:
        """
        Genera un nombre dinámico para archivo SQL.

        Estructura: db_tabla_operacion_YYYYMMDD_HHMMSS.sql

        Args:
            tabla: Nombre de la tabla
            operacion: Tipo de operación (insert, update, delete)

        Returns:
            Path con el nombre dinámico completo

        Raises:
            ValueError: Si no se puede extraer el nombre de base de datos
        """
        try:
            # Extraer nombre de BD de la URL del engine
            # URLs típicas: mysql://user:pass@host/dbname, oracle://user:pass@host:port/dbname
            url_str = str(self.engine.url)
            db_name: str = url_str.split("/")[-1].split("?")[0]

            if not db_name:
                raise ValueError("No se pudo extraer nombre de BD de engine.url")
        except Exception as e:
            raise ValueError(f"No se pudo extraer nombre de BD de engine.url: {self.engine.url}") from e

        # Generar timestamp YYYYMMDD_HHMMSS
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Normalizar operación a minúsculas
        operacion_lower: str = operacion.lower()

        # Construir nombre: db_tabla_operacion_timestamp.sql
        nombre_archivo: str = f"{db_name}-{tabla}-{operacion_lower}_{timestamp}.sql"

        self.logger.debug(f"🟢 Nombre SQL generado: {nombre_archivo}")
        return Path(nombre_archivo)

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
        if path_sql is None:
            raise ValueError("❌ path_sql es obligatorio cuando generar_sql=True")

        # Validar que sea una instancia de Path
        if not isinstance(path_sql, Path):
            raise ValueError(f"❌ path_sql debe ser una instancia de Path, se recibió {type(path_sql).__name__}")

        # Generar nombre dinámico
        nombre_dinamico: Path = self.__generar_nombre_sql_dinamico(tabla_destino, operacion)

        # Combinar path_sql con el nombre dinámico
        ruta_completa: Path = path_sql / nombre_dinamico
        self.logger.debug(f"📄 Path SQL generado: {ruta_completa}")

        return ruta_completa

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
        tabla_cols: set[str] = {col.name for col in tabla.columns}
        insert_cols: list[str] = [c for c in df.columns if c in tabla_cols]
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
            self.audit_manager.registrar_operacion(
                tabla_destino, self.db_info, "INSERT", numero_registros, elapsed, generar_sql
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
        tabla_cols: set[str] = {col.name for col in tabla.columns}
        pk_cols: list[str] = [col.name for col in tabla.primary_key.columns if col.name in df.columns]

        if not pk_cols:
            self.logger.error(f"❌ La tabla '{tabla_destino}' no tiene claves primarias presentes en el DataFrame.")
            raise ValueError(f"❌ La tabla '{tabla_destino}' no tiene claves primarias presentes en el DataFrame.")

        update_cols: list[str] = [col for col in df.columns if col in tabla_cols and col not in pk_cols]
        if not update_cols:
            self.logger.error(f"❌ No hay columnas actualizables válidas. Tabla destino: {tabla_destino}")
            raise ValueError("❌ No hay columnas actualizables válidas.")

        pk_param_map: dict[str, str] = {col: f"pk_{col}" for col in pk_cols}

        records: list[dict[Hashable, Any]] = df.to_dict(orient="records")
        records_sql: list[dict] = normalize_records_for_sql(records)

        for r in records_sql:
            for orig, alias in pk_param_map.items():
                r[alias] = r[orig]

        try:
            numero_registros: int = len(records_sql)
            start: float = perf_counter()

            if generar_sql:
                sql_lines: list = self.__generar_sql_update(tabla, records_sql, update_cols, pk_param_map, pk_cols)
                self.__guardar_fichero_sql(sql_lines, path_sql)
            else:
                where_clause: ColumnElement[bool] = and_(
                    *(tabla.c[col] == bindparam(pk_param_map[col]) for col in pk_cols)
                )
                stmt: Update = update(tabla).where(where_clause).values({col: bindparam(col) for col in update_cols})
                self.__ejecutar_batch_stmt(records_sql, stmt, numero_registros)

            elapsed: float = perf_counter() - start

            # Registrar operación finalizada
            self.audit_manager.registrar_operacion(
                tabla_destino, self.db_info, "UPDATE", numero_registros, elapsed, generar_sql
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
            self.audit_manager.registrar_operacion(
                tabla_destino, self.db_info, "DELETE", numero_registros, elapsed, generar_sql
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
        with self.engine.begin() as conn:
            for i in range(0, numero_registros, self.chunk_size):
                batch: list[dict[Hashable, Any]] = records[i : i + self.chunk_size]
                conn.execute(stmt, batch)  # type: ignore

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
        pk_cols: list[str] = [col.name for col in tabla.primary_key.columns if col.name in df_cols]
        if not pk_cols:
            raise ValueError("❌ La tabla no tiene claves primarias presentes en el DataFrame.")
        return pk_cols

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
        is_sql_based: bool = self.engine.dialect.name in ("mysql", "mariadb", "mssql", "hsqldb")

        with self.engine.begin() as conn:
            for i in range(0, numero_registros, self.chunk_size):
                batch_df: pd.DataFrame = df[pk_cols].iloc[i : i + self.chunk_size]

                if batch_df.empty:
                    continue

                if is_sql_based:
                    self.__execute_sql_based_delete_batch(conn, tabla_destino, batch_df, pk_cols)
                else:
                    self.__execute_generic_delete_batch(conn, tabla, batch_df, pk_cols)

    def __execute_sql_based_delete_batch(self, conn, tabla_destino: str, batch_df: pd.DataFrame, pk_cols: list[str]):
        """Ejecuta un DELETE en bloque usando la sintaxis WHERE (pk1, pk2) IN ((..), (..)).

        Genera la consulta con placeholders y aplana los valores antes de ejecutar con
        `exec_driver_sql` para drivers compatibles con MySQL/MariaDB/HSQLDB que soportan
        la sintaxis (col1, col2) IN (valores).
        """
        if batch_df.empty:
            return

        values = [tuple(row[col] for col in pk_cols) for _, row in batch_df.iterrows()]

        if not values:
            return

        if not all(isinstance(v, tuple) for v in values):
            raise ValueError("❌ Los valores deben ser tuplas.")

        placeholder: str = "(" + ", ".join(["%s"] * len(pk_cols)) + ")"
        placeholders: str = ", ".join([placeholder] * len(values))
        pk_tuple: str = ", ".join(pk_cols)
        sql: str = f"DELETE FROM {tabla_destino} WHERE ({pk_tuple}) IN ({placeholders})"

        flat_values: list[Any] = [val for tup in values for val in tup]
        conn.exec_driver_sql(sql, tuple(flat_values))

    def __execute_generic_delete_batch(self, conn, tabla: Table, batch_df: pd.DataFrame, pk_cols: list[str]):
        """Ejecuta borrado por lotes usando sentencias parametrizadas de SQLAlchemy.

        Convierte el DataFrame del batch a una lista de dicts y ejecuta un DELETE
        con `bindparam` para cada columna PK.
        """
        if batch_df.empty:
            return

        stmt: Delete = delete(tabla).where(and_(*(tabla.c[col] == bindparam(col) for col in pk_cols)))
        records: list[dict[Hashable, Any]] = batch_df.to_dict(orient="records")
        conn.execute(stmt, records)  # type: ignore

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
        # 0. Convertir a mayúsculas o minúsculas el Nombre de las columnas según el dialecto de BBDD
        if self.engine.dialect.name in ("oracle", "postgresql", "sqlite"):
            df.columns = df.columns.str.lower()
        elif self.engine.dialect.name in ("mysql", "mariadb", "mssql", "hsqldb"):
            df.columns = df.columns.str.upper()
        else:
            self.logger.warning(f"⚠️ Dialecto no reconocido: {self.engine.dialect.name}")

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
        sql_lines: list[str] = []
        for record in records:
            sql: str = self.__compilar_stmt_con_binarios(stmt.values(record))
            sql_lines.append(sql)
        return sql_lines

    def __generar_sql_update(
        self,
        tabla: Table,
        records: list[dict],
        update_cols: list[str],
        pk_param_map: dict[str, str],
        pk_cols: list[str],
    ) -> list[str]:
        sql_lines: list[str] = []
        for record in records:
            valores_update: dict[str, Any] = {col: record[col] for col in update_cols}
            condiciones_pk: dict[str, Any] = {pk_param_map[col]: record[pk_param_map[col]] for col in pk_cols}
            stmt: Update = (
                update(tabla)
                .where(and_(*(tabla.c[col] == condiciones_pk[pk_param_map[col]] for col in pk_cols)))
                .values(valores_update)
            )
            sql: str = self.__compilar_stmt_con_binarios(stmt)
            sql_lines.append(sql)
        return sql_lines

    def __generar_sql_delete(self, df: pd.DataFrame, tabla: Table, pk_cols: list[str]) -> list[str]:
        sql_lines: list[str] = []
        for record in df[pk_cols].to_dict(orient="records"):
            condiciones: list = [tabla.c[col] == record[col] for col in pk_cols]
            stmt: Delete = delete(tabla).where(and_(*condiciones))
            sql: str = self.__compilar_stmt_con_binarios(stmt)
            sql_lines.append(sql)
        return sql_lines

    def __compilar_stmt_con_binarios(self, stmt) -> str:
        """Compila un statement con manejo especial para valores binarios.

        Primero intenta compilar normalmente, si falla por BLOB,
        se recompila sin literal_binds y se procesan binarios manualmente.
        """
        try:
            # Intentar compilación normal con literal_binds
            compiled = stmt.compile(dialect=self.engine.dialect, compile_kwargs={"literal_binds": True})
            return f"{compiled};"
        except Exception as e:
            # Si falla por binarios, recompilar sin literal_binds y procesar parámetros
            if "BLOB" in str(e) or "binary" in str(e).lower():
                compiled = stmt.compile(dialect=self.engine.dialect)
                sql_str = str(compiled)
                params = compiled.params or {}

                if not params:
                    return f"{sql_str};"

                # Convertir parámetros a literales SQL en una lista ordenada
                # Los placeholders %s se reemplazan en orden
                param_values = []
                for param_value in params.values():
                    param_values.append(self.__format_param_value(param_value))

                # Reemplazar %s por los valores reales
                sql_result: str = sql_str
                for value in param_values:
                    sql_result = sql_result.replace("%s", value, 1)

                return f"{sql_result};"
            else:
                # Si es otro error, re-lanzar
                raise

    def __format_param_value(self, value: Any) -> str:
        """Convierte un valor de parámetro a su representación literal SQL.

        Args:
            value: El valor a convertir.

        Returns:
            String con la representación literal SQL.
        """
        if value is None:
            return "NULL"
        elif isinstance(value, bytes):
            # Datos binarios: convertir a hexadecimal
            return f"0x{value.hex().upper()}"
        elif isinstance(value, bool):
            # Boolean: 1 o 0
            return "1" if value else "0"
        elif isinstance(value, (datetime, date, time)):
            # Datetime/Date/Time: convertir a string y escapar con comillas
            return f"'{str(value)}'"
        elif isinstance(value, str):
            # String: escapar comillas simples y envolver en comillas
            escaped: str = value.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(value, (int, float)):
            # Números: convertir a string directo
            return str(value)
        else:
            # Para otros tipos, convertir a string y escapar como string
            str_value = str(value)
            escaped = str_value.replace("'", "''")
            return f"'{escaped}'"

    def __guardar_fichero_sql(self, sql_lines: list, fichero_sql: Path | None):
        """Guarda las líneas SQL en un archivo o las imprime en log.

        Args:
            sql_lines: lista de líneas SQL.
            fichero_sql: Ruta del archivo destino. Si es None, imprime en log.
        """
        if fichero_sql:
            with open(fichero_sql, "w", encoding="utf-8") as f:
                f.write("\n".join(sql_lines))
            self.logger.info(f"💾 SQL guardada en: {fichero_sql}")
        else:
            self.logger.info("\n".join(sql_lines))
            self.logger.info("📄 SQL generada en log.")
