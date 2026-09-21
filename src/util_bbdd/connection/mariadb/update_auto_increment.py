"""Generación de sentencias ``ALTER TABLE ... AUTO_INCREMENT`` para MariaDB/MySQL.

Tras una carga masiva con valores explícitos en la clave primaria, el contador ``AUTO_INCREMENT`` de una tabla puede
quedar por detrás de su valor máximo real y el siguiente ``INSERT`` colisiona. ``UpdateAutoIncrement`` lee ese máximo y
devuelve las sentencias que reajustan cada contador **sin ejecutarlas**, para revisarlas o incorporarlas a un script.

Para reajustar los contadores directamente existe ``BulkCrud.sync_pk_sequences()``, que sí ejecuta el cambio.

Regla #6: este módulo vive en ``connection/`` y solo depende de SQLAlchemy y de ``_core``. Recibe el ``Engine`` por
parámetro; no importa ``factory/`` (capa superior) ni ``managers/``.

Excepción documentada a la Regla #2 (``architecture.instructions.md``): las columnas ``AUTO_INCREMENT`` se descubren con
el Inspector de SQLAlchemy, como hace ``comparar/``, porque el módulo opera sobre un ``Engine`` recibido por parámetro y
no sobre un ``SyncMetadataProvider``. No contiene SQL de introspección propio (Reglas #1 y #3).
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from sqlalchemy import Integer, column, func, inspect, select, table
from sqlalchemy.exc import SQLAlchemyError

from ..._core.exceptions import DatabaseOperationError, InvalidDatabaseType

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine
    from sqlalchemy.engine.interfaces import ReflectedColumn
    from sqlalchemy.engine.reflection import Inspector

_SUPPORTED_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb"})


class UpdateAutoIncrement:
    """Genera las sentencias que reajustan ``AUTO_INCREMENT`` al máximo real de cada tabla (MariaDB/MySQL).

    Recorre las tablas base del esquema, localiza su columna ``AUTO_INCREMENT`` y devuelve, por cada una,
    ``ALTER TABLE ... AUTO_INCREMENT = MAX + 1``. No ejecuta ninguna sentencia de modificación y no cierra el ``Engine``:
    su ciclo de vida es de quien lo crea.

    Ejemplo::

        engine = SQLAlchemyEngineFactory.create_engine("mariadb", conn_params, "tienda")
        for sentencia in UpdateAutoIncrement(engine).salida_sql():
            print(sentencia)

    El script refleja el máximo en el momento de generarlo: con escrituras concurrentes puede quedar corto. Conviene
    ejecutarlo en una ventana sin escrituras.

    Args:
        engine: ``Engine`` de SQLAlchemy con dialecto ``mysql`` o ``mariadb``.
        schema: Esquema (base de datos) a recorrer. Si es ``None``, el de la conexión.

    Raises:
        TypeError: Si se pasa un ``dict`` de configuración (firma anterior a la Regla #6).
        InvalidDatabaseType: Si el dialecto del ``Engine`` no es MariaDB/MySQL.
    """

    def __init__(self, engine: Engine, schema: str | None = None) -> None:
        if isinstance(engine, dict):
            raise TypeError(
                "UpdateAutoIncrement ya no recibe un dict de configuración: pasa un Engine de SQLAlchemy "
                "(p. ej. SQLAlchemyEngineFactory.create_engine(...) o SyncDatabaseManager.get_sqlalchemy_engine())."
            )
        dialect_name: str = engine.dialect.name
        if dialect_name not in _SUPPORTED_DIALECTS:
            raise InvalidDatabaseType(
                f"UpdateAutoIncrement solo admite MariaDB/MySQL; el dialecto del Engine es '{dialect_name}'.",
                operation="update_auto_increment",
                db_type=dialect_name,
            )
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._engine: Engine = engine
        self._schema: str | None = schema

    def salida_sql(self) -> list[str]:
        """Devuelve las sentencias ``ALTER TABLE ... AUTO_INCREMENT = n;`` ordenadas por tabla, sin ejecutarlas.

        Solo genera sentencia para las tablas base con una columna ``AUTO_INCREMENT`` de tipo entero. El valor es
        ``MAX(columna) + 1`` (``1`` si la tabla está vacía o el máximo no es positivo).

        Raises:
            DatabaseOperationError: Si falla la lectura del catálogo o del máximo de alguna tabla.
        """
        self.logger.info("ℹ️ Update Auto Increment: %s", self._schema or self._engine.url.database)
        try:
            with self._engine.connect() as connection:
                inspector: Inspector = inspect(connection)
                statements: list[str] = []
                for table_name in sorted(inspector.get_table_names(schema=self._schema)):
                    statement = self._statement_for(connection, inspector, table_name)
                    if statement is not None:
                        statements.append(statement)
        except SQLAlchemyError as exc:
            raise DatabaseOperationError(
                f"No se pudieron generar las sentencias AUTO_INCREMENT: {exc}",
                operation="update_auto_increment",
                db_type=self._engine.dialect.name,
                details=str(exc),
            ) from exc
        return statements

    def _statement_for(self, connection: Connection, inspector: Inspector, table_name: str) -> str | None:
        """Sentencia de una tabla, o ``None`` si no tiene columna ``AUTO_INCREMENT`` utilizable."""
        auto_increment = self._auto_increment_column(inspector, table_name)
        if auto_increment is None:
            return None
        column_name: str = auto_increment["name"]
        if not isinstance(auto_increment["type"], Integer):
            self.logger.warning(
                "⚠️ %s.%s omitida: AUTO_INCREMENT sobre un tipo no entero (%s)",
                table_name,
                column_name,
                auto_increment["type"],
            )
            return None

        max_value = connection.execute(
            select(func.max(column(column_name))).select_from(table(table_name, schema=self._schema))
        ).scalar()
        next_value: int = 1 if max_value is None else max(1, int(max_value) + 1)
        return f"ALTER TABLE {self._qualified(table_name)} AUTO_INCREMENT = {next_value};"

    def _auto_increment_column(self, inspector: Inspector, table_name: str) -> ReflectedColumn | None:
        """Columna ``AUTO_INCREMENT`` de la tabla (MariaDB/MySQL admiten una por tabla), o ``None``."""
        for column_info in inspector.get_columns(table_name, schema=self._schema):
            if column_info.get("autoincrement") is True:
                return column_info
        return None

    def _qualified(self, table_name: str) -> str:
        """Nombre de tabla entrecomillado con backticks (los backticks internos se duplican)."""
        preparer = self._engine.dialect.identifier_preparer
        quoted: str = preparer.quote_identifier(table_name)
        if self._schema:
            return f"{preparer.quote_identifier(self._schema)}.{quoted}"
        return quoted
