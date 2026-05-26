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

from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, OperationalError, ProgrammingError

if TYPE_CHECKING:
    from sqlalchemy import CursorResult, Row, RowMapping
    from sqlalchemy.engine import Inspector
    from sqlalchemy.engine.base import Engine

logger: logging.Logger = logging.getLogger(__name__)

_MIN_PRINTABLE_ORD: int = 0x20  # primer carácter ASCII imprimible (espacio)


def _is_safe_identifier(name: str) -> bool:
    """Verifica que un nombre de objeto de BD no contenga caracteres de control.

    Previene inyección SQL en consultas que usan el nombre dentro de un
    template de cadena (p.ej. ``SHOW CREATE PROCEDURE `{name}```).
    Rechaza: cadenas vacías, NUL bytes (\\x00) y cualquier carácter ASCII < 0x20.
    """
    return bool(name) and "\x00" not in name and all(ord(c) >= _MIN_PRINTABLE_ORD for c in name)


class RoutineFetcherRegistry:
    """Implementaciones estáticas de fetching de DDL de routines por dialect SQLAlchemy.

    Esta clase solo agrupa métodos estáticos — no tiene estado de instancia.
    Los métodos son registrados en ``SchemaComparator._ROUTINE_FETCHERS`` al
    cargar el módulo ``comparator``, siguiendo el patrón OCP.

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
        "w": "WINDOW",
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

        db_name: str = schema or str((getattr(engine, "url", None) and getattr(engine.url, "database", "")) or "")

        try:
            with engine.connect() as conn:
                # Procedures
                proc_result: CursorResult[Any] = conn.execute(
                    text("SHOW PROCEDURE STATUS WHERE Db=:db"),
                    {"db": db_name},
                )
                for row in proc_result.mappings():
                    proc_name = str(row["Name"])
                    if not _is_safe_identifier(proc_name):
                        logger.warning("Nombre de procedure no seguro, se omite: %r", proc_name)
                        continue
                    proc_safe_name = proc_name.replace("`", "``")
                    proc_create_result = conn.execute(text(f"SHOW CREATE PROCEDURE `{proc_safe_name}`"))
                    proc_create_row = proc_create_result.mappings().first()
                    proc_definition = str(proc_create_row["Create Procedure"] or "") if proc_create_row else ""
                    routines.append({"name": proc_name, "type": "PROCEDURE", "definition": proc_definition})
                # Functions
                func_result: CursorResult[Any] = conn.execute(
                    text("SHOW FUNCTION STATUS WHERE Db=:db"),
                    {"db": db_name},
                )
                for row in func_result.mappings():
                    func_name = str(row["Name"])
                    if not _is_safe_identifier(func_name):
                        logger.warning("Nombre de function no seguro, se omite: %r", func_name)
                        continue
                    func_safe_name: str = func_name.replace("`", "``")
                    func_create_result: CursorResult[Any] = conn.execute(
                        text(f"SHOW CREATE FUNCTION `{func_safe_name}`"),
                    )
                    func_create_row: RowMapping | None = func_create_result.mappings().first()
                    func_definition: str = str(func_create_row["Create Function"] or "") if func_create_row else ""
                    routines.append({"name": func_name, "type": "FUNCTION", "definition": func_definition})
        except (
            OperationalError,
            DatabaseError,
        ) as exc:  # M1: Fallback si MariaDB rechaza conexión o permisos insuficientes
            logger.warning("No se pudieron obtener routines MariaDB para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def get_routines_oracle(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de Oracle via ALL_PROCEDURES + DBMS_METADATA.

        **Performance note**: DBMS_METADATA.GET_DDL() can be slow on large catalogs (5k+ procedures).
        For performance-critical workloads, disable routine introspection:
        ``SchemaComparator.compare(..., include_routines=False)``.
        """
        routines: list[dict[str, str]] = []
        engine: Engine = inspector.engine
        if engine is None:
            return routines
        if not schema:
            logger.warning("get_routines_oracle requiere 'schema'; se omite la comparación de routines Oracle.")
            return routines

        try:
            with engine.connect() as conn:
                result: CursorResult[Any] = conn.execute(
                    text(
                        "SELECT object_name, object_type FROM all_procedures "
                        "WHERE owner=:schema AND object_type IN ('PROCEDURE','FUNCTION')",
                    ),
                    {"schema": schema.upper()},
                )
                for row in result.mappings():
                    obj_name = str(row["object_name"])
                    obj_type = str(row["object_type"])
                    try:
                        ddl_result: CursorResult[Any] = conn.execute(
                            text("SELECT DBMS_METADATA.GET_DDL(:obj_type, :obj_name, :schema) AS ddl FROM dual"),
                            {"obj_type": obj_type, "obj_name": obj_name, "schema": schema.upper()},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        ddl_val: Any = ddl_row[0] if ddl_row else ""
                        definition: Any | str = ddl_val.read() if hasattr(ddl_val, "read") else str(ddl_val)
                    except (
                        ProgrammingError,
                        DatabaseError,
                    ):  # M1: DBMS_METADATA falla por permisos o objeto corrompido
                        definition = ""
                    routines.append({"name": obj_name, "type": obj_type, "definition": definition})
        except (
            OperationalError,
            DatabaseError,
        ) as exc:  # M1: Fallback si Oracle rechaza conexión o query a all_procedures falla
            logger.warning("No se pudieron obtener routines Oracle para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def get_routines_mssql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de SQL Server via sys.procedures + sys.sql_modules.

        **Performance note**: On large schemas (10k+ procedures), this may be slow.
        Consider disabling routine introspection for performance-critical scenarios:
        ``SchemaComparator.compare(..., include_routines=False)``.
        """
        routines: list[dict[str, str]] = []
        engine: Engine = inspector.engine
        if engine is None:
            return routines

        schema_name: str = schema or "dbo"

        try:
            with engine.connect() as conn:
                result: CursorResult[Any] = conn.execute(
                    text("SELECT name FROM sys.procedures WHERE schema_id = SCHEMA_ID(:schema) ORDER BY name"),
                    {"schema": schema_name},
                )
                for row in result.mappings():
                    proc_name = str(row["name"])
                    try:
                        ddl_result: CursorResult[Any] = conn.execute(
                            text(
                                "SELECT definition FROM sys.sql_modules "
                                "WHERE object_id = OBJECT_ID(CONCAT(:schema_name, '.', :proc_name))",
                            ),
                            {"schema_name": schema_name, "proc_name": proc_name},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        definition: str = str(ddl_row[0]) if ddl_row else ""
                    except (
                        ProgrammingError,
                        DatabaseError,
                    ):  # M1: sys.sql_modules falla por permisos o procedure encriptada
                        definition = ""
                    routines.append({"name": proc_name, "type": "PROCEDURE", "definition": definition})
                # Funciones escalares, inline y multi-statement (FN, IF, TF)
                func_result: CursorResult[Any] = conn.execute(
                    text(
                        "SELECT o.name FROM sys.objects o "
                        "WHERE o.schema_id = SCHEMA_ID(:schema) "
                        "AND o.type IN ('FN', 'IF', 'TF') "
                        "ORDER BY o.name",
                    ),
                    {"schema": schema_name},
                )
                for row in func_result.mappings():
                    func_name = str(row["name"])
                    try:
                        func_ddl_result: CursorResult[Any] = conn.execute(
                            text(
                                "SELECT definition FROM sys.sql_modules "
                                "WHERE object_id = OBJECT_ID(CONCAT(:schema_name, '.', :func_name))",
                            ),
                            {"schema_name": schema_name, "func_name": func_name},
                        )
                        func_ddl_row: Row[Any] | None = func_ddl_result.first()
                        func_definition: str = str(func_ddl_row[0]) if func_ddl_row else ""
                    except (
                        ProgrammingError,
                        DatabaseError,
                    ):  # M1: sys.sql_modules falla por permisos o función encriptada
                        func_definition = ""
                    routines.append({"name": func_name, "type": "FUNCTION", "definition": func_definition})
        except (
            OperationalError,
            DatabaseError,
        ) as exc:  # M1: Fallback si SQL Server rechaza conexión o query a sys.procedures falla
            logger.warning("No se pudieron obtener routines SQL Server para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def get_routines_postgresql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de PostgreSQL via pg_proc + pg_get_functiondef.

        **Performance note**: Uses pg_get_functiondef() which materializes full DDL.
        On schemas with 10k+ functions, this may consume significant memory.
        Consider caching results or disabling routine introspection for large catalogs.
        """
        routines: list[dict[str, str]] = []
        engine: Engine = inspector.engine
        if engine is None:
            return routines

        schema_name: str = schema or "public"

        try:
            with engine.connect() as conn:
                result: CursorResult[Any] = conn.execute(
                    text(
                        "SELECT p.oid, p.proname, p.prokind, "
                        "pg_catalog.pg_get_function_arguments(p.oid) AS proargs "
                        "FROM pg_proc p "
                        "JOIN pg_namespace n ON p.pronamespace = n.oid "
                        "WHERE n.nspname = :schema "
                        "ORDER BY p.proname, proargs",
                    ),
                    {"schema": schema_name},
                )
                rows_list = list(result.mappings())
                # Detectar nombres con overloads para asignar clave única solo cuando es necesario
                name_counts: dict[str, int] = {}
                for row in rows_list:
                    name_counts[str(row["proname"])] = name_counts.get(str(row["proname"]), 0) + 1

                for row in rows_list:
                    func_oid = row["oid"]
                    func_name = str(row["proname"])
                    proc_kind = str(row["prokind"])  # M1: 'f' = function, 'p' = procedure, 'w' = window
                    kind_label: str = RoutineFetcherRegistry._PROCEDURE_KIND_MAP.get(proc_kind, "PROCEDURE")
                    proargs: str = str(row.get("proargs") or "")
                    # Nombre único: incluye firma de argumentos solo si hay overloads con el mismo nombre
                    unique_name: str = f"{func_name}({proargs})" if name_counts[func_name] > 1 else func_name

                    try:
                        # Usar OID directamente evita el fallo de ::regprocedure con overloads
                        ddl_result: CursorResult[Any] = conn.execute(
                            text("SELECT pg_get_functiondef(:oid) AS definition"),
                            {"oid": func_oid},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        definition: str = str(ddl_row[0]) if ddl_row and ddl_row[0] else ""
                    except (
                        ProgrammingError,
                        DatabaseError,
                    ):  # M1: pg_get_functiondef() falla en C, trigger o lenguaje no soportado
                        definition = ""
                    routines.append({"name": unique_name, "type": kind_label, "definition": definition})
        except (
            OperationalError,
            DatabaseError,
        ) as exc:  # M1: Fallback si PostgreSQL rechaza conexión o query a pg_proc falla
            logger.warning("No se pudieron obtener routines PostgreSQL para schema=%s: %s", schema, exc)

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
