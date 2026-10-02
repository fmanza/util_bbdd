"""Implementaciones de fetching de routines (procedures/functions) por motor de BD.

Cada método estático de ``RoutineFetcherRegistry`` encapsula la lógica de
introspección de DDL para un dialect concreto.  El registro en
``SchemaComparator._ROUTINE_FETCHERS`` se realiza al final de
``comparator.py`` (patrón OCP: extensible sin modificar la clase comparadora).

Para añadir soporte de un nuevo motor::

    from util_bbdd.comparar._routine_fetchers import RoutineFetcherRegistry
    from util_bbdd.comparar import SchemaComparator

    @staticmethod
    def my_fetcher(inspector, schema):
        ...

    SchemaComparator._ROUTINE_FETCHERS["mydialect"] = my_fetcher
"""

from __future__ import annotations

import logging

from collections import Counter
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, OperationalError

from util_bbdd._core.exceptions import MetadataIntrospectionError
from util_bbdd.metadata.mariadb.common import quote_mariadb_identifier
from util_bbdd.metadata.oracle.tables import fetch_standalone_routine_sources_for_schema_sql
from util_bbdd.metadata.postgresql.routines import fetch_routines_with_definition_for_schema_sql
from util_bbdd.metadata.sqlserver.tables import (
    fetch_routines_with_definition_for_schema_sql as fetch_sqlserver_routines_with_definition_sql,
)

if TYPE_CHECKING:
    from sqlalchemy import CursorResult, RowMapping
    from sqlalchemy.engine import Connection, Inspector
    from sqlalchemy.engine.base import Engine

logger: logging.Logger = logging.getLogger(__name__)

_MIN_PRINTABLE_ORD: int = 0x20  # primer carácter ASCII imprimible (espacio)

#: Tipos de ``sys.objects`` que son funciones T-SQL (escalar, inline y multi-statement); el resto, procedures.
_MSSQL_FUNCTION_TYPES: frozenset[str] = frozenset({"FN", "IF", "TF"})


def _is_safe_identifier(name: str) -> bool:
    """Verifica que un nombre de objeto de BD no contenga caracteres de control.

    Previene inyección SQL en consultas que usan el nombre dentro de un
    template de cadena (p.ej. ``SHOW CREATE PROCEDURE `{name}```).
    Rechaza: cadenas vacías, NUL bytes (\\x00) y cualquier carácter ASCII < 0x20.
    """
    return bool(name) and "\x00" not in name and all(ord(c) >= _MIN_PRINTABLE_ORD for c in name)


def _mariadb_ddl_from_row(row_or_none: RowMapping | None, col: str) -> str:
    """Extrae el DDL de una fila de SHOW CREATE PROCEDURE/FUNCTION, o retorna '' si no hay fila."""
    if row_or_none is None:
        return ""
    return str(row_or_none[col] or "")


def _listing_error(engine_label: str, schema: str | None, exc: Exception | None = None) -> MetadataIntrospectionError:
    """Error de un fetcher que no ha podido listar las routines del schema.

    ``SchemaComparator`` lo captura y omite la comparación de routines: una lista vacía o parcial produciría falsos
    "added"/"removed" con las routines del otro lado.
    """
    cause: str = f": {exc}" if exc is not None else ""
    return MetadataIntrospectionError(
        f"No se pudieron listar las routines {engine_label}",
        operation="get_routines",
        details=f"schema={schema}{cause}",
    )


def _mariadb_show_create(conn: Connection, kind: str, db_name: str, name: str) -> str:
    """DDL de una routine MariaDB/MySQL vía ``SHOW CREATE``; ``""`` (con warning) si falla solo esa routine.

    El nombre va calificado con el schema: sin él, ``SHOW CREATE`` busca en la base de datos de la conexión, que no
    tiene por qué ser ``db_name``. Los ``:`` se escapan para que ``text()`` no los tome por parámetros.

    Si la conexión se ha perdido (``connection_invalidated``) el error se propaga: el fetcher lo convierte en error
    de listado, en lugar de devolver ``""`` para esta y todas las routines restantes.
    """
    qualified: str = quote_mariadb_identifier(name)
    if db_name:
        qualified = f"{quote_mariadb_identifier(db_name)}.{qualified}"
    sql: str = f"SHOW CREATE {kind} {qualified}".replace(":", r"\:")
    try:
        result: CursorResult[Any] = conn.execute(text(sql))
    except DatabaseError as exc:  # sin permisos sobre la routine, o eliminada entre el listado y el SHOW CREATE
        if exc.connection_invalidated:
            raise
        logger.warning("No se pudo obtener el DDL de %s %s.%s: %s", kind, db_name, name, exc)
        return ""
    return _mariadb_ddl_from_row(result.mappings().first(), f"Create {kind.capitalize()}")


class RoutineFetcherRegistry:
    """Implementaciones estáticas de fetching de DDL de routines por dialect SQLAlchemy.

    Esta clase solo agrupa métodos estáticos — no tiene estado de instancia.
    Los métodos son registrados en ``SchemaComparator._ROUTINE_FETCHERS`` al
    cargar el módulo ``comparator``, siguiendo el patrón OCP.

    Si un fetcher no puede listar las routines del schema lanza ``MetadataIntrospectionError`` (el comparador
    omite entonces la comparación de routines); si solo falla el DDL de una routine, la devuelve con
    ``definition=""``.

    Attributes:
        _PROCEDURE_KIND_MAP: Mapa de códigos ``prokind`` de PostgreSQL a labels DDL.

    Example:
        >>> from util_bbdd.comparar._routine_fetchers import RoutineFetcherRegistry
        >>> fetcher = RoutineFetcherRegistry.get_routines_mariadb
        >>> # routines = fetcher(inspector, schema="mydb")
    """

    _PROCEDURE_KIND_MAP: ClassVar[dict[str, str]] = {
        "f": "FUNCTION",
        "p": "PROCEDURE",
        "w": "FUNCTION",  # función de ventana: se crea y se borra como FUNCTION
    }

    @staticmethod
    def get_routines_mariadb(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de MariaDB/MySQL via SHOW PROCEDURE STATUS / SHOW CREATE PROCEDURE.

        **Performance note**: SHOW PROCEDURE STATUS is relatively fast, but large databases
        benefit from pagination or result limiting. For performance-critical scenarios,
        consider: ``SchemaComparator.compare(..., include_routines=False)``.
        """
        routines: list[dict[str, str]] = []
        engine: Engine = inspector.engine
        if engine is None:
            return routines

        db_name: str = schema or str(getattr(getattr(engine, "url", None), "database", "") or "")

        try:
            with engine.connect() as conn:
                for kind in ("PROCEDURE", "FUNCTION"):
                    status: CursorResult[Any] = conn.execute(text(f"SHOW {kind} STATUS WHERE Db=:db"), {"db": db_name})
                    names: list[str] = [str(row["Name"]) for row in status.mappings()]
                    for name in names:
                        if not _is_safe_identifier(name):
                            logger.warning("Nombre de %s no seguro, se omite: %r", kind.lower(), name)
                            continue
                        definition: str = _mariadb_show_create(conn, kind, db_name, name)
                        routines.append({"name": name, "type": kind, "definition": definition})
        except (OperationalError, DatabaseError) as exc:  # conexión rechazada o sin permisos para listar
            raise _listing_error("MariaDB/MySQL", schema, exc) from exc

        return routines

    @staticmethod
    def get_routines_oracle(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Procedures y functions sueltas de Oracle con su código, en una consulta sobre ``ALL_SOURCE``.

        ``definition`` es ``CREATE OR REPLACE`` + el código de ``ALL_SOURCE``: sin el owner delante, dos schemas con
        el mismo código se comparan iguales. Antes se usaba ``DBMS_METADATA.GET_DDL``, una consulta por routine con el
        nombre calificado (``"OWNER"."NOMBRE"``), que marcaba como modificadas todas las routines de dos schemas.
        """
        engine: Engine = inspector.engine
        if engine is None:
            return []
        if not schema:
            raise _listing_error("Oracle", schema, ValueError("get_routines_oracle requiere 'schema'"))

        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(fetch_standalone_routine_sources_for_schema_sql()), {"owner": schema.upper()}
                ).all()
        except (OperationalError, DatabaseError) as exc:  # Oracle rechaza la conexión o falla la consulta
            raise _listing_error("Oracle", schema, exc) from exc

        # Filas (name, type, line, text) ordenadas por nombre, tipo y línea: se concatenan por routine.
        sources: dict[tuple[str, str], list[str]] = {}
        for name, obj_type, _line, line_text in rows:
            sources.setdefault((str(name), str(obj_type)), []).append(str(line_text or ""))
        return [
            {"name": name, "type": obj_type, "definition": f"CREATE OR REPLACE {''.join(lines).rstrip()}"}
            for (name, obj_type), lines in sources.items()
        ]

    @staticmethod
    def get_routines_mssql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Procedures y functions de SQL Server con su código, en una consulta (``sys.objects`` + ``sys.sql_modules``).

        ``definition`` vacía si el módulo está cifrado o no es T-SQL (CLR, procedimiento extendido).
        """
        engine: Engine = inspector.engine
        if engine is None:
            return []

        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(fetch_sqlserver_routines_with_definition_sql()), {"schema": schema or "dbo"}
                ).all()
        except (OperationalError, DatabaseError) as exc:  # SQL Server rechaza la conexión o falla la consulta
            raise _listing_error("SQL Server", schema, exc) from exc

        return [
            {
                "name": str(name),
                "type": "FUNCTION" if str(obj_type) in _MSSQL_FUNCTION_TYPES else "PROCEDURE",
                "definition": str(definition or ""),
            }
            for name, obj_type, definition in rows
        ]

    @staticmethod
    def get_routines_postgresql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene functions y procedures de PostgreSQL con su DDL en una sola consulta.

        La consulta (``metadata.postgresql.routines.fetch_routines_with_definition_for_schema_sql``) excluye los
        agregados, con los que ``pg_get_functiondef`` falla y deja abortada la transacción.

        Cada routine lleva ``signature`` = ``nombre(argumentos)``, que el comparador usa para emparejar sobrecargas
        aunque solo un lado las tenga. ``name`` incluye los argumentos solo si hay sobrecargas en este lado.
        """
        routines: list[dict[str, str]] = []
        engine: Engine = inspector.engine
        if engine is None:
            return routines

        schema_name: str = schema or "public"

        try:
            with engine.connect() as conn:
                result: CursorResult[Any] = conn.execute(
                    text(fetch_routines_with_definition_for_schema_sql()), {"schema": schema_name}
                )
                rows_list: list[RowMapping] = list(result.mappings())
        except (OperationalError, DatabaseError) as exc:  # PostgreSQL rechaza la conexión o falla la consulta
            raise _listing_error("PostgreSQL", schema, exc) from exc

        name_counts: Counter[str] = Counter(str(row["proname"]) for row in rows_list)
        for row in rows_list:
            func_name: str = str(row["proname"])
            signature: str = f"{func_name}({row.get('identity_args') or ''})"
            routines.append(
                {
                    "name": signature if name_counts[func_name] > 1 else func_name,
                    "type": RoutineFetcherRegistry._PROCEDURE_KIND_MAP.get(str(row["prokind"]), "FUNCTION"),
                    "definition": str(row.get("definition") or ""),
                    "signature": signature,
                },
            )
        return routines

    @staticmethod
    def get_routines_hsqldb(_inspector: Inspector, _schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de HSQLDB (sin soporte de DDL; retorna lista vacía con warning).

        **Limitación**: HSQLDB soporta ``INFORMATION_SCHEMA.ROUTINES``, pero no proporciona
        una forma portable de extraer el DDL de procedures/functions via JDBC.
        Retorna lista vacía de forma segura, evitando falsos negativos en comparaciones.

        **Performance note**: This method returns immediately (O(1)). No database queries are issued.
        """
        logger.warning(
            "HSQLDB no soporta extracción de DDL de routines; se omite la comparación. "
            "Consulte SchemaComparator.compare(..., include_routines=True) docs para detalles.",
        )
        return []
