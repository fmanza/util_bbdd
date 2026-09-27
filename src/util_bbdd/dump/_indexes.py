"""Gestión dialect-specific de índices secundarios para volcado de datos.

Deshabilita los índices secundarios **no únicos** del destino antes de la carga
masiva y los reconstruye al finalizar, para acelerar los INSERT en tablas con
muchos índices.

Estrategia por motor (no destructiva salvo PostgreSQL):
  - SQL Server (mssql): ``ALTER INDEX ... DISABLE`` → ``... REBUILD``. Solo índices
    NONCLUSTERED (deshabilitar el clustered dejaría la tabla inaccesible).
  - Oracle: ``ALTER INDEX ... UNUSABLE`` → ``... REBUILD``.
  - PostgreSQL: captura el DDL con ``pg_get_indexdef`` (se loguea antes de borrar),
    ``DROP INDEX`` y recrea ejecutando el DDL guardado.
  - MariaDB / MySQL (InnoDB): no soportado (``DISABLE KEYS`` se ignora en InnoDB;
    DROP/CREATE es demasiado arriesgado). No-op con ``action="unsupported"``.

Solo se gestionan índices **no únicos**: los que respaldan PK / UNIQUE constraints
o son unique indexes quedan intactos, preservando la integridad durante la carga.
"""

from __future__ import annotations

import logging

from typing import Any, ClassVar, Literal

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..bulk._support.dialect import MYSQL_FAMILY
from ..metadata.oracle.indexes import (
    fetch_secondary_nonunique_indexes_sql as fetch_oracle_secondary_indexes_sql,
)
from ..metadata.postgresql.tables import (
    fetch_secondary_nonunique_indexes_sql as fetch_pg_secondary_indexes_sql,
)
from ..metadata.sqlserver.indexes import (
    fetch_secondary_nonunique_indexes_sql as fetch_mssql_secondary_indexes_sql,
)
from ._models import IndexActionResult
from ._sql_utils import quote_identifier, quote_table

_SUPPORTED_DIALECTS = frozenset({"mssql", "oracle", "postgresql"})
_UNSUPPORTED_DIALECTS = MYSQL_FAMILY


class IndexManager:
    """Gestiona la desactivación/reconstrucción de índices secundarios en el destino.

    Usar como context manager garantiza que ``rebuild_all()`` se llama incluso si la
    carga lanza una excepción. Los resultados quedan en ``index_results`` tras salir
    del bloque ``with``.

    Ejemplo::

        mgr = IndexManager(target_engine, schema="dbo")
        with mgr:
            mgr.disable_all(tables=load_order)
            # ... cargar datos ...
        print(mgr.index_results)

    Permisos requeridos: ``ALTER`` sobre las tablas (mssql/oracle) o propiedad de los
    índices (postgresql ``DROP``/``CREATE INDEX``).
    """

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, engine: Engine, schema: str | None = None) -> None:
        self._engine = engine
        self._schema = schema
        self._dialect = engine.dialect.name
        # mssql / oracle: (tabla, índice) deshabilitados o marcados UNUSABLE
        self._disabled: list[tuple[str, str]] = []
        # postgresql: (tabla, índice, ddl) eliminados — el ddl permite recrearlos
        self._dropped_pg: list[tuple[str, str, str]] = []
        # Resultados accesibles tras __exit__
        self.index_results: list[IndexActionResult] = []

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> IndexManager:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            self.index_results = self.rebuild_all()
        except Exception:  # noqa: BLE001
            self.logger.exception("Error al reconstruir índices — la excepción original no se enmascara")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def disable_all(self, tables: list[str]) -> None:
        """Deshabilita los índices secundarios no únicos de las tablas indicadas."""
        dialect = self._dialect
        if dialect in _UNSUPPORTED_DIALECTS:
            self.logger.warning(
                "Dialect '%s' no soporta la gestión de índices (InnoDB ignora DISABLE KEYS). "
                "Se continúa sin tocar índices.",
                dialect,
            )
            return
        if dialect not in _SUPPORTED_DIALECTS:
            self.logger.warning(
                "Dialect '%s' no soportado para gestión de índices. Se continúa sin tocar índices.", dialect
            )
            return

        if dialect == "mssql":
            self._disable_mssql(tables)
        elif dialect == "oracle":
            self._disable_oracle(tables)
        elif dialect == "postgresql":
            self._disable_postgresql(tables)

    def rebuild_all(self) -> list[IndexActionResult]:
        """Reconstruye todos los índices deshabilitados. Retorna resultado por índice."""
        dialect = self._dialect
        if dialect in _UNSUPPORTED_DIALECTS:
            return [
                IndexActionResult(
                    table_name="*",
                    index_name="*",
                    dialect=dialect,
                    action="unsupported",
                    error_msg="Gestión de índices no soportada en MariaDB/MySQL (InnoDB).",
                ),
            ]
        if dialect == "mssql":
            return self._rebuild_mssql()
        if dialect == "oracle":
            return self._rebuild_oracle()
        if dialect == "postgresql":
            return self._recreate_postgresql()
        return []

    # ------------------------------------------------------------------
    # SQL Server  (DISABLE / REBUILD — solo NONCLUSTERED no únicos)
    # ------------------------------------------------------------------

    def _disable_mssql(self, tables: list[str]) -> None:
        self._disabled = []
        with self._engine.connect() as conn:
            for table in tables:
                for index_name in self._discover_mssql(conn, table):
                    try:
                        conn.execute(text(f"ALTER INDEX {self._qi(index_name)} ON {self._qt(table)} DISABLE"))
                        conn.commit()
                        self._disabled.append((table, index_name))
                    except SQLAlchemyError as exc:
                        conn.rollback()
                        self.logger.warning("No se pudo deshabilitar el índice '%s.%s': %s", table, index_name, exc)

    def _discover_mssql(self, conn: Any, table: str) -> list[str]:
        rows = conn.execute(
            text(fetch_mssql_secondary_indexes_sql()),
            {"tbl": table, "schema": self._schema},
        ).fetchall()
        return [r[0] for r in rows]

    def _rebuild_mssql(self) -> list[IndexActionResult]:
        results: list[IndexActionResult] = []
        with self._engine.connect() as conn:
            for table, index_name in self._disabled:
                results.append(
                    self._run_rebuild(
                        conn,
                        f"ALTER INDEX {self._qi(index_name)} ON {self._qt(table)} REBUILD",
                        table,
                        index_name,
                        "rebuilt",
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Oracle  (UNUSABLE / REBUILD — índices NORMAL no asociados a constraint)
    # ------------------------------------------------------------------

    def _disable_oracle(self, tables: list[str]) -> None:
        self._disabled = []
        with self._engine.connect() as conn:
            for table in tables:
                for index_name in self._discover_oracle(conn, table):
                    try:
                        conn.execute(text(f"ALTER INDEX {self._qseq_ref(index_name)} UNUSABLE"))
                        conn.commit()
                        self._disabled.append((table, index_name))
                    except SQLAlchemyError as exc:
                        conn.rollback()
                        self.logger.warning("No se pudo marcar UNUSABLE el índice '%s.%s': %s", table, index_name, exc)

    def _discover_oracle(self, conn: Any, table: str) -> list[str]:
        if self._schema:
            rows = conn.execute(
                text(fetch_oracle_secondary_indexes_sql(with_owner=True)),
                {"tbl": table, "owner": self._schema},
            ).fetchall()
        else:
            rows = conn.execute(
                text(fetch_oracle_secondary_indexes_sql(with_owner=False)),
                {"tbl": table},
            ).fetchall()
        return [r[0] for r in rows]

    def _rebuild_oracle(self) -> list[IndexActionResult]:
        results: list[IndexActionResult] = []
        with self._engine.connect() as conn:
            for table, index_name in self._disabled:
                results.append(
                    self._run_rebuild(
                        conn, f"ALTER INDEX {self._qseq_ref(index_name)} REBUILD", table, index_name, "rebuilt"
                    )
                )
        return results

    # ------------------------------------------------------------------
    # PostgreSQL  (DROP + recreate desde pg_get_indexdef)
    # ------------------------------------------------------------------

    def _disable_postgresql(self, tables: list[str]) -> None:
        self._dropped_pg = []
        with self._engine.connect() as conn:
            for table in tables:
                for index_name, ddl in self._discover_postgresql(conn, table):
                    # Loguear el DDL ANTES del DROP: si el proceso cae entre DROP y CREATE,
                    # el índice es recuperable manualmente desde el log.
                    self.logger.warning("PostgreSQL: DROP índice '%s.%s'. DDL para recrear: %s", table, index_name, ddl)
                    try:
                        conn.execute(text(f"DROP INDEX {self._qt(index_name)}"))
                        conn.commit()
                        self._dropped_pg.append((table, index_name, ddl))
                    except SQLAlchemyError as exc:
                        conn.rollback()
                        self.logger.warning("No se pudo eliminar el índice '%s.%s': %s", table, index_name, exc)

    def _discover_postgresql(self, conn: Any, table: str) -> list[tuple[str, str]]:
        rows = conn.execute(
            text(fetch_pg_secondary_indexes_sql()),
            {"tbl": table, "schema": self._schema},
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _recreate_postgresql(self) -> list[IndexActionResult]:
        results: list[IndexActionResult] = []
        with self._engine.connect() as conn:
            for table, index_name, ddl in self._dropped_pg:
                results.append(self._run_rebuild(conn, ddl, table, index_name, "recreated"))
        return results

    # ------------------------------------------------------------------
    # Helper de reconstrucción común
    # ------------------------------------------------------------------

    def _run_rebuild(
        self,
        conn: Any,
        sql: str,
        table: str,
        index_name: str,
        ok_action: Literal["rebuilt", "recreated"],
    ) -> IndexActionResult:
        try:
            conn.execute(text(sql))
            conn.commit()
            return IndexActionResult(
                table_name=table,
                index_name=index_name,
                dialect=self._dialect,
                action=ok_action,
            )
        except SQLAlchemyError as exc:
            conn.rollback()
            self.logger.warning("Error reconstruyendo el índice '%s.%s': %s", table, index_name, exc)
            return IndexActionResult(
                table_name=table,
                index_name=index_name,
                dialect=self._dialect,
                action="failed",
                error_msg=str(exc),
            )

    # ------------------------------------------------------------------
    # Helpers de quoting
    # ------------------------------------------------------------------

    def _qi(self, name: str) -> str:
        """Quoted identifier según el dialect del engine destino."""
        return quote_identifier(name, self._engine)

    def _qt(self, table: str) -> str:
        """Tabla/índice quoted con prefijo de schema opcional."""
        return quote_table(table, self._schema, self._engine)

    def _qseq_ref(self, index_name: str) -> str:
        """Referencia al índice Oracle (schema-qualified) para ALTER INDEX."""
        if self._schema:
            return f"{self._qi(self._schema)}.{self._qi(index_name)}"
        return self._qi(index_name)


__all__: list[str] = ["IndexManager"]
