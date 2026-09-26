"""Gestión dialect-specific de constraints para volcado de datos.

Soporta: SQL Server (mssql), MariaDB/MySQL, PostgreSQL, Oracle.
Otros dialectos: no-op con advertencia.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sqlalchemy import Engine, Inspector, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .._core.exceptions import DumpConstraintError
from ..bulk._support.dialect import MYSQL_FAMILY
from ._models import ConstraintResult
from ._sql_utils import quote_identifier, quote_table

_log = logging.getLogger(__name__)

_SUPPORTED_DIALECTS = frozenset({"mssql", "mariadb", "mysql", "oracle", "postgresql"})


class ConstraintManager:
    """Gestiona la desactivación/reactivación de constraints en el motor destino.

    Usar como context manager garantiza que ``enable_all()`` se llama incluso
    si la carga lanza una excepción. Los resultados quedan en
    ``constraint_results`` tras salir del bloque ``with``.

    Ejemplo::

        mgr = ConstraintManager(target_engine, schema="dbo")
        with mgr:
            mgr.disable_all(tables=load_order)
            # ... cargar datos ...
        print(mgr.constraint_results)
    """

    def __init__(self, engine: Engine, schema: str | None = None) -> None:
        self._engine = engine
        self._schema = schema
        self._dialect = engine.dialect.name
        # Oracle / PostgreSQL: (tabla, nombre_constraint) desactivadas
        self._disabled: list[tuple[str, str]] = []
        # PostgreSQL: tablas con triggers desactivados (para re-activar solo las afectadas)
        self._disabled_pg: list[str] = []
        # SQL Server: tablas con NOCHECK aplicado
        self._nocheck_tables: list[str] = []
        # MariaDB: listeners checkout/checkin almacenados para poder eliminarlos
        self._mariadb_checkout: Callable[..., None] | None = None
        self._mariadb_checkin: Callable[..., None] | None = None
        # Resultados accesibles tras __exit__
        self.constraint_results: list[ConstraintResult] = []

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> ConstraintManager:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            self.constraint_results = self.enable_all()
        except Exception:  # noqa: BLE001
            _log.exception("Error al rehabilitar constraints — la excepción original no se enmascara")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def disable_all(self, tables: list[str]) -> None:
        """Desactiva constraints en las tablas indicadas del motor destino.

        Los fallos por constraint/tabla individual se degradan a warning (best-effort,
        ver los métodos `_disable_*`); un fallo real que impida desactivar constraints
        en absoluto (p.ej. conexión perdida a mitad de la operación) se relanza como
        `DumpConstraintError` en vez de propagar la excepción cruda de SQLAlchemy.

        Raises:
            DumpConstraintError: Si falla la desactivación de forma no recuperable.
        """
        dialect = self._dialect
        if dialect not in _SUPPORTED_DIALECTS:
            _log.warning("Dialect '%s' no soportado para gestión de constraints. Se continúa sin desactivar.", dialect)
            return

        try:
            if dialect in MYSQL_FAMILY:
                self._disable_mariadb()
            elif dialect == "mssql":
                self._disable_sqlserver(tables)
            elif dialect == "postgresql":
                self._disable_postgresql(tables)
            elif dialect == "oracle":
                self._disable_oracle(tables)
        except SQLAlchemyError as exc:
            raise DumpConstraintError(f"Error desactivando constraints en destino ({dialect}): {exc}") from exc

    def enable_all(self) -> list[ConstraintResult]:
        """Reactiva todas las constraints desactivadas. Retorna resultado por constraint.

        Igual que `disable_all`: fallos por constraint individual se reflejan en el
        `ConstraintResult` correspondiente (status="failed"); un fallo real no
        recuperable se relanza como `DumpConstraintError`.

        Raises:
            DumpConstraintError: Si falla la reactivación de forma no recuperable.
        """
        dialect = self._dialect
        if dialect not in _SUPPORTED_DIALECTS:
            return []

        try:
            if dialect in MYSQL_FAMILY:
                return self._enable_mariadb()
            if dialect == "mssql":
                return self._enable_sqlserver()
            if dialect == "postgresql":
                return self._enable_postgresql()
            if dialect == "oracle":
                return self._enable_oracle()
            return []
        except SQLAlchemyError as exc:
            raise DumpConstraintError(f"Error reactivando constraints en destino ({dialect}): {exc}") from exc

    # ------------------------------------------------------------------
    # MariaDB / MySQL  (event listener sobre el engine pool)
    # ------------------------------------------------------------------

    @staticmethod
    def _exec_session_var(dbapi_conn: Any, sql: str) -> None:
        """Ejecuta una sentencia SET de sesión sobre la conexión DBAPI cruda.

        PD-09 (performance-audit de dump 2026-09-25): una conexión invalidada (p. ej. tras un error en la carga) vuelve al
        pool con ``dbapi_conn=None``; el ``AttributeError`` de ``None.cursor()`` sustituía a la excepción original. No hay
        nada que restaurar: el pool descarta esa conexión y no se reutiliza con ``FOREIGN_KEY_CHECKS = 0``.
        """
        if dbapi_conn is None:
            return
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute(sql)
        finally:
            cursor.close()

    def _disable_mariadb(self) -> None:
        # Aplicar FK=0 en cada checkout del pool (cubre también conexiones ya creadas,
        # sin necesidad de reciclar el pool con dispose()) y restaurar FK=1 en cada
        # checkin, para no dejar conexiones con FK desactivado al devolverlas al pool.
        # A diferencia de dispose(), no cierra conexiones activas, por lo que es seguro
        # con un engine compartido entre hilos (paralelización del volcado).
        def _fk_off(dbapi_conn: Any, _rec: Any, _proxy: Any) -> None:
            self._exec_session_var(dbapi_conn, "SET SESSION FOREIGN_KEY_CHECKS = 0")

        def _fk_on(dbapi_conn: Any, _rec: Any) -> None:
            self._exec_session_var(dbapi_conn, "SET SESSION FOREIGN_KEY_CHECKS = 1")

        self._mariadb_checkout = _fk_off
        self._mariadb_checkin = _fk_on
        event.listen(self._engine, "checkout", _fk_off)
        event.listen(self._engine, "checkin", _fk_on)

    def _enable_mariadb(self) -> list[ConstraintResult]:
        if self._mariadb_checkout is None:
            return []
        event.remove(self._engine, "checkout", self._mariadb_checkout)
        if self._mariadb_checkin is not None:
            event.remove(self._engine, "checkin", self._mariadb_checkin)
        self._mariadb_checkout = None
        self._mariadb_checkin = None
        # MariaDB no valida integridad retroactiva al reactivar FK checks
        return [
            ConstraintResult(
                table_name="*",
                constraint_name="FOREIGN_KEY_CHECKS",
                dialect=self._dialect,
                status="unverified",
                error_msg="MariaDB no valida integridad retroactiva al reactivar FK checks.",
            ),
        ]

    # ------------------------------------------------------------------
    # SQL Server  (NOCHECK / WITH CHECK por tabla — catalog-level)
    # ------------------------------------------------------------------

    def _disable_sqlserver(self, tables: list[str]) -> None:
        self._nocheck_tables = list(tables)
        if not tables:
            return
        with self._engine.begin() as conn:
            for table in tables:
                conn.execute(text(f"ALTER TABLE {self._qt(table)} NOCHECK CONSTRAINT ALL"))

    def _enable_sqlserver(self) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        with self._engine.connect() as conn:
            for table in self._nocheck_tables:
                try:
                    conn.execute(text(f"ALTER TABLE {self._qt(table)} WITH CHECK CHECK CONSTRAINT ALL"))
                    conn.commit()
                    results.append(
                        ConstraintResult(
                            table_name=table,
                            constraint_name="ALL",
                            dialect=self._dialect,
                            status="enabled",
                        ),
                    )
                except SQLAlchemyError as exc:
                    conn.rollback()
                    results.append(
                        ConstraintResult(
                            table_name=table,
                            constraint_name="ALL",
                            dialect=self._dialect,
                            status="failed",
                            error_msg=str(exc),
                        ),
                    )
        return results

    # ------------------------------------------------------------------
    # PostgreSQL  (DISABLE TRIGGER ALL — catalog-level, requiere OWNER)
    # ------------------------------------------------------------------

    def _disable_postgresql(self, tables: list[str]) -> None:
        self._disabled_pg = []
        with self._engine.connect() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"ALTER TABLE {self._qt(table)} DISABLE TRIGGER ALL"))
                    conn.commit()
                    self._disabled_pg.append(table)
                except SQLAlchemyError as exc:
                    conn.rollback()
                    _log.warning("No se pudo deshabilitar triggers en '%s' (¿falta permiso?): %s", table, exc)

    def _enable_postgresql(self) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        # Usar solo las tablas que fueron desactivadas (no todas las del schema)
        tables = list(self._disabled_pg)
        insp: Inspector = inspect(self._engine)
        # Tablas donde ENABLE TRIGGER falló — no intentar VALIDATE CONSTRAINT en ellas (C3)
        failed_trigger: set[str] = set()

        with self._engine.connect() as conn:
            # Fase A: reactivar triggers
            for table in tables:
                try:
                    conn.execute(text(f"ALTER TABLE {self._qt(table)} ENABLE TRIGGER ALL"))
                    conn.commit()
                except SQLAlchemyError as exc:
                    conn.rollback()
                    failed_trigger.add(table)
                    _log.warning("Error reactivando triggers en '%s': %s", table, exc)

            # Fase B: validar FKs usando savepoints para aislar errores por constraint
            for table in tables:
                if table in failed_trigger:
                    continue
                try:
                    fks = insp.get_foreign_keys(table, schema=self._schema)
                except SQLAlchemyError:
                    continue
                self._validate_fks_pg(conn, table, fks, results)
            conn.commit()
        return results

    def _validate_fks_pg(
        self,
        conn: Any,
        table: str,
        fks: Sequence[Mapping[str, Any]],
        results: list[ConstraintResult],
    ) -> None:
        """Valida cada FK de una tabla PostgreSQL con savepoints para aislar fallos."""
        for fk in fks:
            fk_name: str | None = fk.get("name")
            if not fk_name:
                continue
            try:
                conn.execute(text("SAVEPOINT sp_validate"))
                conn.execute(
                    text(f"ALTER TABLE {self._qt(table)} VALIDATE CONSTRAINT {self._qi(fk_name)}"),
                )
                orphan_msg = self._find_fk_orphan_pg(conn, table, fk_name)
                conn.execute(text("RELEASE SAVEPOINT sp_validate"))
                if orphan_msg is not None:
                    results.append(
                        ConstraintResult(
                            table_name=table,
                            constraint_name=fk_name,
                            dialect=self._dialect,
                            status="failed",
                            error_msg=orphan_msg,
                        ),
                    )
                    continue
                results.append(
                    ConstraintResult(
                        table_name=table,
                        constraint_name=fk_name,
                        dialect=self._dialect,
                        status="enabled",
                    ),
                )
            except SQLAlchemyError as exc:
                conn.execute(text("ROLLBACK TO SAVEPOINT sp_validate"))
                results.append(
                    ConstraintResult(
                        table_name=table,
                        constraint_name=fk_name,
                        dialect=self._dialect,
                        status="failed",
                        error_msg=str(exc),
                    ),
                )

    # Definición de una FK desde el catálogo: tabla referenciada (``regclass``, ya citada y con esquema si hace falta)
    # y columnas de la hija y de la referenciada citadas con ``quote_ident``, en el orden de la constraint.
    _PG_FK_DEF_SQL = """
        SELECT c.confrelid::regclass::text,
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum)
        FROM pg_constraint c
        WHERE c.conrelid = CAST(:tbl AS regclass) AND c.conname = :name AND c.contype = 'f'
    """

    def _find_fk_orphan_pg(self, conn: Any, table: str, fk_name: str) -> str | None:
        """Busca una fila de ``table`` que incumpla la FK ``fk_name``; devuelve el mensaje de error o ``None``.

        PD-04 (performance-audit de dump 2026-09-25): ``DISABLE TRIGGER ALL`` no marca la FK como ``NOT VALID``, así que
        ``VALIDATE CONSTRAINT`` no comprueba nada y una fila huérfana cargada con los triggers desactivados pasaba como
        ``enabled``. Semántica ``MATCH SIMPLE`` (la de por defecto): una fila con alguna columna de la FK a NULL cumple.
        """
        definition = conn.execute(text(self._PG_FK_DEF_SQL), {"tbl": self._qt(table), "name": fk_name}).first()
        if definition is None or not definition[1] or not definition[2]:
            return None
        parent, child_cols, parent_cols = definition
        not_null = " AND ".join(f"c.{col} IS NOT NULL" for col in child_cols)
        match = " AND ".join(f"p.{pcol} = c.{ccol}" for ccol, pcol in zip(child_cols, parent_cols, strict=True))
        orphan = conn.execute(
            text(
                f"SELECT 1 FROM {self._qt(table)} c WHERE {not_null} "
                f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {match}) LIMIT 1"
            )
        ).first()
        if orphan is None:
            return None
        return (
            f"Hay filas en '{table}' que no cumplen la FK '{fk_name}' (sin fila referenciada en {parent}); se "
            "cargaron con los triggers desactivados. La FK sigue marcada como válida en el catálogo."
        )

    # ------------------------------------------------------------------
    # Oracle  (DISABLE/ENABLE VALIDATE por constraint — catalog-level)
    # ------------------------------------------------------------------

    def _disable_oracle(self, tables: list[str]) -> None:
        self._disabled = []
        insp: Inspector = inspect(self._engine)

        def _fetch_names(getter_fn: Callable[..., Any], table: str) -> list[str]:
            try:
                items = getter_fn(table, schema=self._schema)
                return [c.get("name", "") for c in items if c.get("name")]
            except SQLAlchemyError:
                return []

        with self._engine.connect() as conn:
            for table in tables:
                names: list[str] = []
                names.extend(_fetch_names(insp.get_foreign_keys, table))
                names.extend(
                    n
                    for n in _fetch_names(insp.get_check_constraints, table)
                    if not n.upper().startswith("SYS_C")  # filtrar constraints de sistema Oracle
                )
                names.extend(_fetch_names(insp.get_unique_constraints, table))
                for name in names:
                    try:
                        conn.execute(text(f"ALTER TABLE {self._qt(table)} DISABLE CONSTRAINT {self._qi(name)}"))
                        self._disabled.append((table, name))
                    except SQLAlchemyError as exc:
                        _log.warning("No se pudo deshabilitar '%s.%s': %s", table, name, exc)
            conn.commit()

    def _enable_oracle(self) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        with self._engine.connect() as conn:
            for table, constraint_name in self._disabled:
                try:
                    conn.execute(
                        text(f"ALTER TABLE {self._qt(table)} ENABLE VALIDATE CONSTRAINT {self._qi(constraint_name)}"),
                    )
                    conn.commit()
                    results.append(
                        ConstraintResult(
                            table_name=table,
                            constraint_name=constraint_name,
                            dialect=self._dialect,
                            status="enabled",
                        ),
                    )
                except SQLAlchemyError as exc:
                    conn.rollback()
                    results.append(
                        ConstraintResult(
                            table_name=table,
                            constraint_name=constraint_name,
                            dialect=self._dialect,
                            status="failed",
                            error_msg=str(exc),
                        ),
                    )
        return results

    # ------------------------------------------------------------------
    # Helpers de quoting
    # ------------------------------------------------------------------

    def _qi(self, name: str) -> str:
        """Quoted identifier según el dialect del engine destino."""
        return quote_identifier(name, self._engine)

    def _qt(self, table: str) -> str:
        """Tabla quoted con prefijo de schema opcional."""
        return quote_table(table, self._schema, self._engine)
