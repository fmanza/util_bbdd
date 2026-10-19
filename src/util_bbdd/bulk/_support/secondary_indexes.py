"""Desactivación y restauración de índices secundarios no únicos durante una carga: estrategia común de bulk y dump.

Qué índices (``metadata.facts.secondary_nonunique_indexes``) y qué DDL por motor:

- SQL Server: NONCLUSTERED no únicos, ``ALTER INDEX … DISABLE`` → ``REBUILD`` (nunca el clustered ni PK/UNIQUE).
- Oracle: ``NORMAL`` no únicos, ``ALTER INDEX … UNUSABLE`` → ``REBUILD`` (el DDL confirma la transacción).
- PostgreSQL: no únicos, ``DROP INDEX`` → su ``pg_get_indexdef`` con ``IF NOT EXISTS`` (el DDL se loguea antes de borrar).
- MariaDB/MySQL: MyISAM/Aria, ``DISABLE KEYS`` → ``ENABLE KEYS``; InnoDB, ``DROP INDEX`` → un solo
  ``ALTER TABLE … ADD INDEX …`` por tabla (una pasada); nunca los que necesita una FK ni la PK (es el clustered).

Lo planifica :class:`SecondaryIndexPlanner` y lo ejecuta :class:`IndexDdlRunner`, sobre la conexión que se le pase:
``dump.IndexManager`` y ``ParallelBulkLoader`` con una propia y un commit por sentencia; ``BulkCrud.maintenance_scope``
con la de su sesión y un savepoint por sentencia (SQL Server y PostgreSQL). Un índice que falla no detiene a los demás.
Medición: ``.ai/sessions/2026-10-18b-index-modes-bulk-dump/03_G0_MEDICION.md``.
"""

from __future__ import annotations

import logging

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...metadata import facts
from .._models import IndexActionResult
from .dialect import MYSQL_FAMILY

#: Modos de gestión de índices. ``"secondary"``: los secundarios no únicos (``True`` equivale a él).
IndexMode = Literal["secondary"]
INDEX_MODES: frozenset[str] = frozenset({"secondary"})
#: Motores con estrategia de índices.
SUPPORTED_DIALECTS: frozenset[str] = frozenset({"mssql", "oracle", "postgresql"}) | MYSQL_FAMILY
_MYISAM_LIKE: frozenset[str] = frozenset({"MYISAM", "ARIA"})


def resolve_index_mode(value: bool | str | None, field: str) -> IndexMode | None:
    """``False``/``None`` → ``None`` (no se tocan); ``True`` → ``"secondary"``; un modo válido, tal cual.

    Raises:
        ValueError: Si ``value`` no es ``bool`` ni un modo de :data:`INDEX_MODES`.
    """
    if value is None or value is False:
        return None
    if value is True or value == "secondary":
        return "secondary"
    raise ValueError(f"{field} debe ser bool o 'secondary', recibido: {value!r}")


@dataclass(frozen=True)
class IndexStep:
    """Un índice que se desactiva y su restauración.

    Attributes:
        table: Tabla (como la recibió el planificador).
        quoted_table: Tabla citada (agrupa la restauración de InnoDB).
        index_name: Nombre del índice (``"*"`` para ``DISABLE KEYS`` de toda la tabla).
        disable_sql: Sentencia de desactivación.
        restore_sql: Sentencia de restauración; en InnoDB, la cláusula ``ADD INDEX …`` (ver ``grouped``).
        action: Resultado si la restauración va bien.
        recovery_ddl: DDL para recrear el índice a mano, que se loguea antes de borrarlo (PostgreSQL e InnoDB).
        grouped: ``True`` si ``restore_sql`` es una cláusula de un ``ALTER TABLE`` común a la tabla (InnoDB).
    """

    table: str
    quoted_table: str
    index_name: str
    disable_sql: str
    restore_sql: str
    action: Literal["rebuilt", "recreated"]
    recovery_ddl: str | None = None
    grouped: bool = False


class SecondaryIndexPlanner:
    """Decide qué índices de una tabla se desactivan y con qué DDL (ver el docstring del módulo).

    Args:
        dialect: Nombre del dialecto de SQLAlchemy.
        preparer: ``identifier_preparer`` del dialecto (cita índices y esquemas).
    """

    def __init__(self, dialect: str, preparer: Any) -> None:
        self.dialect = dialect
        self._prep = preparer

    def plan(self, conn: Any, *, table: str, schema: str | None, quoted_table: str) -> list[IndexStep]:
        """Pasos para la tabla; ``[]`` si no hay índices que tocar o el motor no tiene estrategia."""
        dialect = self.dialect
        if dialect in MYSQL_FAMILY:
            return self._plan_mysql(conn, table, schema, quoted_table)
        if dialect not in SUPPORTED_DIALECTS:
            return []
        steps: list[IndexStep] = []
        for name, ddl in facts.secondary_nonunique_indexes(conn, schema, table, dialect):
            ref = self._qualified(name, schema)
            if dialect == "mssql":
                q = self._prep.quote(name)
                disable, restore = (
                    f"ALTER INDEX {q} ON {quoted_table} DISABLE",
                    f"ALTER INDEX {q} ON {quoted_table} REBUILD",
                )
                steps.append(IndexStep(table, quoted_table, name, disable, restore, "rebuilt"))
            elif dialect == "oracle":
                steps.append(
                    IndexStep(
                        table,
                        quoted_table,
                        name,
                        f"ALTER INDEX {ref} UNUSABLE",
                        f"ALTER INDEX {ref} REBUILD",
                        "rebuilt",
                    )
                )
            elif ddl:  # postgresql: sin su DDL no se podría recrear; no se borra
                steps.append(
                    IndexStep(table, quoted_table, name, f"DROP INDEX {ref}", _if_not_exists(ddl), "recreated", ddl)
                )
        return steps

    def _plan_mysql(self, conn: Any, table: str, schema: str | None, quoted_table: str) -> list[IndexStep]:
        if str(facts.storage_engine(conn, schema, table) or "").upper() in _MYISAM_LIKE:
            return [
                IndexStep(
                    table,
                    quoted_table,
                    "*",
                    f"ALTER TABLE {quoted_table} DISABLE KEYS",
                    f"ALTER TABLE {quoted_table} ENABLE KEYS",
                    "rebuilt",
                )
            ]
        steps: list[IndexStep] = []
        for name, clause in facts.secondary_nonunique_indexes(conn, schema, table, self.dialect):
            if not clause:
                continue
            steps.append(
                IndexStep(
                    table,
                    quoted_table,
                    name,
                    f"ALTER TABLE {quoted_table} DROP INDEX {self._prep.quote(name)}",
                    f"ADD {clause}",
                    "recreated",
                    recovery_ddl=f"ALTER TABLE {quoted_table} ADD {clause}",
                    grouped=True,
                )
            )
        return steps

    def _qualified(self, name: str, schema: str | None) -> str:
        quoted = self._prep.quote(name)
        return f"{self._prep.quote(schema)}.{quoted}" if schema else quoted


def _if_not_exists(ddl: str) -> str:
    """``CREATE INDEX x …`` → ``CREATE INDEX IF NOT EXISTS x …``: tras un rollback que deshizo el DROP, no falla."""
    for prefix in ("CREATE INDEX ", "CREATE UNIQUE INDEX "):
        if ddl.startswith(prefix) and not ddl.startswith(f"{prefix}IF NOT EXISTS "):
            return f"{prefix}IF NOT EXISTS {ddl[len(prefix) :]}"
    return ddl


def restore_batches(steps: Sequence[IndexStep]) -> list[tuple[str, list[IndexStep]]]:
    """Sentencias de restauración en orden; los pasos ``grouped`` de una tabla, en un solo ``ALTER TABLE``."""
    batches: list[tuple[str, list[IndexStep]]] = []
    grouped: dict[str, list[IndexStep]] = {}
    for step in steps:
        if step.grouped:
            if step.quoted_table not in grouped:
                grouped[step.quoted_table] = []
                batches.append(("", grouped[step.quoted_table]))  # se rellena abajo, manteniendo el orden
            grouped[step.quoted_table].append(step)
        else:
            batches.append((step.restore_sql, [step]))
    return [
        (sql or f"ALTER TABLE {members[0].quoted_table} " + ", ".join(s.restore_sql for s in members), members)
        for sql, members in batches
    ]


class IndexDdlRunner:
    """Ejecuta los pasos de :class:`SecondaryIndexPlanner` sobre una conexión, tolerando el fallo de cada sentencia.

    Args:
        dialect: Nombre del dialecto (va en los resultados).
        logger: Logger del llamador.
        commit: ``True`` (modo autónomo: ``dump`` y carga paralela): commit tras cada sentencia y rollback si falla.
        savepoint: ``True`` (dentro de la transacción de una sesión): cada sentencia en un ``SAVEPOINT``, para que un
            fallo no aborte la sesión (PostgreSQL) ni la deje a medias.
    """

    def __init__(self, dialect: str, logger: logging.Logger, *, commit: bool, savepoint: bool) -> None:
        self.dialect = dialect
        self.logger = logger
        self._commit = commit
        self._savepoint = savepoint

    def disable(self, conn: Any, steps: Sequence[IndexStep]) -> list[IndexStep]:
        """Desactiva los índices; devuelve los que se desactivaron (los que hay que restaurar)."""
        done: list[IndexStep] = []
        for step in steps:
            if step.recovery_ddl:
                # Antes de borrar: si el proceso cae entre DROP y CREATE, el índice se recupera desde el log.
                self.logger.warning(
                    f"Se borra el índice '{step.table}.{step.index_name}' durante la carga. DDL para recrearlo: "
                    f"{step.recovery_ddl}"
                )
            try:
                self._execute(conn, step.disable_sql)
                done.append(step)
            except SQLAlchemyError as exc:
                self.logger.warning(f"No se pudo desactivar el índice '{step.table}.{step.index_name}': {exc}")
        return done

    def restore(self, conn: Any, steps: Sequence[IndexStep]) -> list[IndexActionResult]:
        """Restaura los índices desactivados; un resultado por índice."""
        results: list[IndexActionResult] = []
        for sql, members in restore_batches(steps):
            try:
                self._execute(conn, sql)
                results.extend(IndexActionResult(s.table, s.index_name, self.dialect, s.action) for s in members)
            except SQLAlchemyError as exc:
                names = ", ".join(f"{s.table}.{s.index_name}" for s in members)
                self.logger.warning(f"Error al restaurar el índice {names}: {exc}")
                results.extend(
                    IndexActionResult(s.table, s.index_name, self.dialect, "failed", error_msg=str(exc))
                    for s in members
                )
        return results

    def _execute(self, conn: Any, sql: str) -> None:
        try:
            if self._savepoint:
                with conn.begin_nested():
                    conn.execute(text(sql))
            else:
                conn.execute(text(sql))
            if self._commit:
                conn.commit()
        except SQLAlchemyError:
            if self._commit:
                conn.rollback()
            raise


__all__: list[str] = [
    "INDEX_MODES",
    "SUPPORTED_DIALECTS",
    "IndexDdlRunner",
    "IndexMode",
    "IndexStep",
    "SecondaryIndexPlanner",
    "resolve_index_mode",
    "restore_batches",
]
