"""Desactivación y restauración de índices durante una carga: estrategia común de bulk y dump.

Modos (``IndexMode``):

- ``"secondary"`` (3.2.0): índices secundarios **no únicos** (``metadata.facts.secondary_nonunique_indexes``).
- ``"all"`` (3.3.0): además, índices únicos y PK/UNIQUE (``facts.unique_indexes``), con las FK que los referencian
  (``facts.inbound_foreign_keys``). La unicidad no se comprueba durante la carga: solo para datos ya validados.

DDL por motor:

- SQL Server: ``ALTER INDEX … DISABLE`` → ``REBUILD`` (NONCLUSTERED; nunca el clustered). En ``"all"``, el motor
  deshabilita las FK que referencian un índice deshabilitado; se reactivan con ``WITH CHECK CHECK CONSTRAINT``.
- Oracle: ``ALTER INDEX … UNUSABLE`` → ``REBUILD`` (el DDL confirma la transacción). En ``"all"``, PK/UNIQUE con
  ``DISABLE CONSTRAINT … CASCADE`` → ``ENABLE VALIDATE`` y después las FK entrantes; nunca la PK de una IOT. Los índices
  únicos sin constraint no se tocan.
- PostgreSQL: ``DROP INDEX`` → su ``pg_get_indexdef`` con ``IF NOT EXISTS`` (el DDL se loguea antes de borrar). En
  ``"all"``, primero se borran las FK entrantes, después PK/UNIQUE (``pg_get_constraintdef``) e índices únicos; se
  recrean al revés y las FK con ``NOT VALID`` + ``VALIDATE CONSTRAINT``.
- MariaDB/MySQL: MyISAM/Aria, ``DISABLE KEYS`` → ``ENABLE KEYS``; InnoDB, ``DROP INDEX`` → un solo
  ``ALTER TABLE … ADD INDEX …`` por tabla (una pasada); nunca los que usa o referencia una FK ni la PK (el clustered).

Lo planifica :class:`SecondaryIndexPlanner` y lo ejecuta :class:`IndexDdlRunner`, sobre la conexión que se le pase:
``dump.IndexManager`` y ``ParallelBulkLoader`` con una propia y un commit por sentencia; ``BulkCrud.maintenance_scope``
con la de su sesión y un savepoint por sentencia (SQL Server y PostgreSQL). Un paso que falla no detiene a los demás y
se restaura todo lo que se desactivó. Solo se tocan las PK/UNIQUE **activas** al planificar: una que ya desactivó la
ruta de constraints (UNIQUE de Oracle con ``disable_constraints``) queda a cargo de esa ruta.
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

#: Modos de gestión de índices. ``"secondary"``: los secundarios no únicos (``True`` equivale a él); ``"all"``: además
#: los únicos y PK/UNIQUE posibles (v3.3.0).
IndexMode = Literal["secondary", "all"]
INDEX_MODES: frozenset[str] = frozenset({"secondary", "all"})
#: Motores con estrategia de índices.
SUPPORTED_DIALECTS: frozenset[str] = frozenset({"mssql", "oracle", "postgresql"}) | MYSQL_FAMILY
_MYISAM_LIKE: frozenset[str] = frozenset({"MYISAM", "ARIA"})
#: Prioridad de restauración (menor primero): índices únicos, secundarios, PK/UNIQUE, FK entrantes, validación de FK.
_UNIQUE_INDEX, _SECONDARY, _CONSTRAINT, _FOREIGN_KEY, _VALIDATE = 0, 1, 2, 3, 4
#: Claves duplicadas que se muestran por índice único que no se pudo reconstruir.
MAX_DUPLICATES = 5


def resolve_index_mode(value: bool | str | None, field: str) -> IndexMode | None:
    """``False``/``None`` → ``None`` (no se tocan); ``True`` → ``"secondary"``; un modo válido, tal cual.

    Raises:
        ValueError: Si ``value`` no es ``bool`` ni un modo de :data:`INDEX_MODES`.
    """
    if value is None or value is False:
        return None
    if value is True or value == "secondary":
        return "secondary"
    if value == "all":
        return "all"
    raise ValueError(f"{field} debe ser bool, 'secondary' o 'all', recibido: {value!r}")


@dataclass(frozen=True)
class IndexStep:
    """Un índice (o una FK) que se desactiva y su restauración.

    Attributes:
        table: Tabla (como la recibió el planificador; en las FK entrantes, la tabla hija).
        quoted_table: Tabla citada (agrupa la restauración de InnoDB).
        index_name: Nombre del índice, constraint o FK (``"*"`` para ``DISABLE KEYS`` de toda la tabla).
        disable_sql: Sentencia de desactivación; ``""`` si la desactiva el propio motor (FK de SQL Server y Oracle).
        restore_sql: Sentencia de restauración; en InnoDB, la cláusula ``ADD …`` (ver ``grouped``).
        action: Resultado si la restauración va bien.
        recovery_ddl: DDL para recrearlo a mano, que se loguea antes de borrarlo (PostgreSQL e InnoDB).
        grouped: ``True`` si ``restore_sql`` es una cláusula de un ``ALTER TABLE`` común a la tabla (InnoDB).
        priority: Orden de restauración (menor primero).
        step_id: Identificador del paso (por defecto ``table.index_name``).
        depends_on: ``step_id`` que tiene que haberse desactivado para que este paso cuente.
        unique_columns: Columnas citadas de la clave de un índice único (diagnóstico de duplicados si no se reconstruye).
    """

    table: str
    quoted_table: str
    index_name: str
    disable_sql: str
    restore_sql: str
    action: Literal["rebuilt", "recreated"]
    recovery_ddl: str | None = None
    grouped: bool = False
    priority: int = _SECONDARY
    step_id: str = ""
    depends_on: str | None = None
    unique_columns: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return self.step_id or f"{self.table}.{self.index_name}"


class SecondaryIndexPlanner:
    """Decide qué índices de una tabla se desactivan y con qué DDL (ver el docstring del módulo).

    Args:
        dialect: Nombre del dialecto de SQLAlchemy.
        preparer: ``identifier_preparer`` del dialecto (cita índices y esquemas).
    """

    def __init__(self, dialect: str, preparer: Any) -> None:
        self.dialect = dialect
        self._prep = preparer

    def plan(
        self, conn: Any, *, table: str, schema: str | None, quoted_table: str, mode: IndexMode = "secondary"
    ) -> list[IndexStep]:
        """Pasos para la tabla, en orden de desactivación; ``[]`` si no hay nada que tocar o el motor no está soportado."""
        dialect = self.dialect
        if dialect in MYSQL_FAMILY:
            return self._plan_mysql(conn, table, schema, quoted_table, mode)
        if dialect not in SUPPORTED_DIALECTS:
            return []
        steps = self._plan_unique(conn, table, schema, quoted_table) if mode == "all" else []
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

    # ------------------------------------------------------------------
    # "all": únicos, PK/UNIQUE y FK entrantes
    # ------------------------------------------------------------------

    def _plan_unique(self, conn: Any, table: str, schema: str | None, quoted_table: str) -> list[IndexStep]:
        uniques = facts.unique_indexes(conn, schema, table, self.dialect)
        if not uniques:
            return []
        inbound = facts.inbound_foreign_keys(conn, schema, table, self.dialect)
        if self.dialect == "mssql":
            return self._plan_unique_mssql(table, quoted_table, uniques, inbound)
        if self.dialect == "oracle":
            return self._plan_unique_oracle(table, quoted_table, uniques, inbound)
        return self._plan_unique_postgresql(table, schema, quoted_table, uniques, inbound)

    def _key_columns(self, fact: facts.UniqueIndexFact) -> tuple[str, ...]:
        return tuple(self._prep.quote(c) for c in fact.columns)

    def _child(self, fk: facts.InboundForeignKeyFact) -> str:
        return (
            f"{self._prep.quote(fk.schema)}.{self._prep.quote(fk.table)}" if fk.schema else self._prep.quote(fk.table)
        )

    def _plan_unique_mssql(
        self,
        table: str,
        quoted_table: str,
        uniques: Sequence[facts.UniqueIndexFact],
        inbound: Sequence[facts.InboundForeignKeyFact],
    ) -> list[IndexStep]:
        steps: list[IndexStep] = []
        for fact in uniques:
            q = self._prep.quote(fact.name)
            steps.append(
                IndexStep(
                    table,
                    quoted_table,
                    fact.name,
                    f"ALTER INDEX {q} ON {quoted_table} DISABLE",
                    f"ALTER INDEX {q} ON {quoted_table} REBUILD",
                    "rebuilt",
                    priority=_UNIQUE_INDEX,
                    unique_columns=self._key_columns(fact),
                )
            )
        disabled = {fact.name for fact in uniques}
        for fk in inbound:
            if fk.referenced not in disabled or not fk.enabled:
                continue  # las deshabilitadas antes se quedan como estaban
            check = "WITH CHECK CHECK" if fk.validated else "CHECK"
            child = self._child(fk)
            steps.append(
                IndexStep(
                    fk.table,
                    child,
                    fk.name,
                    "",  # SQL Server la deshabilita al deshabilitar el índice que referencia
                    f"ALTER TABLE {child} {check} CONSTRAINT {self._prep.quote(fk.name)}",
                    "rebuilt",
                    priority=_FOREIGN_KEY,
                    step_id=f"fk:{child}.{fk.name}",
                    depends_on=f"{table}.{fk.referenced}",
                )
            )
        return steps

    def _plan_unique_oracle(
        self,
        table: str,
        quoted_table: str,
        uniques: Sequence[facts.UniqueIndexFact],
        inbound: Sequence[facts.InboundForeignKeyFact],
    ) -> list[IndexStep]:
        steps: list[IndexStep] = []
        for fact in uniques:
            q = self._prep.quote(fact.name)
            steps.append(
                IndexStep(
                    table,
                    quoted_table,
                    fact.name,
                    f"ALTER TABLE {quoted_table} DISABLE CONSTRAINT {q} CASCADE",
                    f"ALTER TABLE {quoted_table} ENABLE VALIDATE CONSTRAINT {q}",
                    "rebuilt",
                    priority=_CONSTRAINT,
                    unique_columns=self._key_columns(fact),
                )
            )
        for fk in inbound:
            child = self._child(fk)
            validate = "VALIDATE" if fk.validated else "NOVALIDATE"
            steps.append(
                IndexStep(
                    fk.table,
                    child,
                    fk.name,
                    "",  # DISABLE CONSTRAINT … CASCADE la desactiva con la PK/UNIQUE
                    f"ALTER TABLE {child} ENABLE {validate} CONSTRAINT {self._prep.quote(fk.name)}",
                    "rebuilt",
                    priority=_FOREIGN_KEY,
                    step_id=f"fk:{child}.{fk.name}",
                    depends_on=f"{table}.{fk.referenced}",
                )
            )
        return steps

    def _plan_unique_postgresql(
        self,
        table: str,
        schema: str | None,
        quoted_table: str,
        uniques: Sequence[facts.UniqueIndexFact],
        inbound: Sequence[facts.InboundForeignKeyFact],
    ) -> list[IndexStep]:
        steps: list[IndexStep] = []
        for fk in inbound:  # primero: PostgreSQL no deja borrar la PK/UNIQUE de la que dependen
            child, name = self._child(fk), self._prep.quote(fk.name)
            ddl = fk.ddl or ""
            not_valid = fk.validated and "NOT VALID" not in ddl.upper()
            fk_id = f"fk:{child}.{fk.name}"
            steps.append(
                IndexStep(
                    fk.table,
                    child,
                    fk.name,
                    f"ALTER TABLE {child} DROP CONSTRAINT {name}",
                    f"ALTER TABLE {child} ADD CONSTRAINT {name} {ddl}{' NOT VALID' if not_valid else ''}",
                    "recreated",
                    recovery_ddl=f"ALTER TABLE {child} ADD CONSTRAINT {name} {ddl}",
                    priority=_FOREIGN_KEY,
                    step_id=fk_id,
                )
            )
            if not_valid:
                steps.append(
                    IndexStep(
                        fk.table,
                        child,
                        fk.name,
                        "",
                        f"ALTER TABLE {child} VALIDATE CONSTRAINT {name}",
                        "recreated",
                        priority=_VALIDATE,
                        step_id=f"{fk_id}#validate",
                        depends_on=fk_id,
                    )
                )
        for fact in uniques:
            if fact.constraint is not None:
                q = self._prep.quote(fact.constraint)
                ddl = f"ALTER TABLE {quoted_table} ADD CONSTRAINT {q} {fact.ddl}"
                disable, restore, priority = f"ALTER TABLE {quoted_table} DROP CONSTRAINT {q}", ddl, _CONSTRAINT
            else:
                ddl = fact.ddl or ""
                disable, restore, priority = (
                    f"DROP INDEX {self._qualified(fact.name, schema)}",
                    _if_not_exists(ddl),
                    _UNIQUE_INDEX,
                )
            steps.append(
                IndexStep(
                    table,
                    quoted_table,
                    fact.name,
                    disable,
                    restore,
                    "recreated",
                    recovery_ddl=ddl,
                    priority=priority,
                    unique_columns=self._key_columns(fact),
                )
            )
        return steps

    # ------------------------------------------------------------------
    # MariaDB / MySQL
    # ------------------------------------------------------------------

    def _plan_mysql(
        self, conn: Any, table: str, schema: str | None, quoted_table: str, mode: IndexMode
    ) -> list[IndexStep]:
        myisam = str(facts.storage_engine(conn, schema, table) or "").upper() in _MYISAM_LIKE
        steps: list[IndexStep] = []
        if mode == "all":
            for fact in facts.unique_indexes(conn, schema, table, self.dialect):
                steps.append(self._mysql_drop_add(table, quoted_table, fact.name, fact.ddl or "", fact))
        if myisam:
            steps.append(
                IndexStep(
                    table,
                    quoted_table,
                    "*",
                    f"ALTER TABLE {quoted_table} DISABLE KEYS",
                    f"ALTER TABLE {quoted_table} ENABLE KEYS",
                    "rebuilt",
                )
            )
            return steps
        for name, clause in facts.secondary_nonunique_indexes(conn, schema, table, self.dialect):
            if clause:
                steps.append(self._mysql_drop_add(table, quoted_table, name, clause, None))
        return steps

    def _mysql_drop_add(
        self, table: str, quoted_table: str, name: str, clause: str, unique: facts.UniqueIndexFact | None
    ) -> IndexStep:
        return IndexStep(
            table,
            quoted_table,
            name,
            f"ALTER TABLE {quoted_table} DROP INDEX {self._prep.quote(name)}",
            f"ADD {clause}",
            "recreated",
            recovery_ddl=f"ALTER TABLE {quoted_table} ADD {clause}",
            grouped=True,
            priority=_SECONDARY if unique is None else _UNIQUE_INDEX,
            unique_columns=() if unique is None else self._key_columns(unique),
        )

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
    """Sentencias de restauración por prioridad; los pasos ``grouped`` de una tabla, en un solo ``ALTER TABLE``."""
    batches: list[tuple[str, list[IndexStep]]] = []
    grouped: dict[str, list[IndexStep]] = {}
    for step in sorted(steps, key=lambda s: s.priority):
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


def duplicates_sql(dialect: str, quoted_table: str, columns: Sequence[str], limit: int = MAX_DUPLICATES) -> str:
    """SQL con hasta ``limit`` claves repetidas de ``columns`` en la tabla y cuántas veces aparece cada una."""
    cols = ", ".join(columns)
    body = f"{cols}, COUNT(*) FROM {quoted_table} GROUP BY {cols} HAVING COUNT(*) > 1"
    if dialect == "mssql":
        return f"SELECT TOP {limit} {body}"
    if dialect == "oracle":
        return f"SELECT {body} FETCH FIRST {limit} ROWS ONLY"
    return f"SELECT {body} LIMIT {limit}"


class IndexDdlRunner:
    """Ejecuta los pasos de :class:`SecondaryIndexPlanner` sobre una conexión, tolerando el fallo de cada sentencia.

    Args:
        dialect: Nombre del dialecto (va en los resultados).
        logger: Logger del llamador.
        commit: ``True`` (modo autónomo: ``dump`` y carga paralela): commit tras cada sentencia y rollback si falla.
        savepoint: ``True`` (dentro de la transacción de una sesión): cada sentencia en un ``SAVEPOINT``, para que un
            fallo no aborte la sesión (PostgreSQL) ni la deje a medias.

    Attributes:
        duplicates: Tras :meth:`restore`, por índice único que no se reconstruyó (``tabla.índice``), sus claves repetidas.
    """

    def __init__(self, dialect: str, logger: logging.Logger, *, commit: bool, savepoint: bool) -> None:
        self.dialect = dialect
        self.logger = logger
        self._commit = commit
        self._savepoint = savepoint
        self.duplicates: dict[str, list[str]] = {}
        self.failed_unique: list[str] = []

    def disable(self, conn: Any, steps: Sequence[IndexStep]) -> list[IndexStep]:
        """Desactiva los índices; devuelve los que se desactivaron (los que hay que restaurar)."""
        done: list[IndexStep] = []
        done_keys: set[str] = set()
        for step in steps:
            if step.depends_on is not None and step.depends_on not in done_keys:
                continue  # lo que lo provocaba no se desactivó
            if step.disable_sql and step.recovery_ddl:
                # Antes de borrar: si el proceso cae entre DROP y CREATE, se recupera desde el log.
                self.logger.warning(
                    f"Se borra '{step.table}.{step.index_name}' durante la carga. DDL para recrearlo: {step.recovery_ddl}"
                )
            try:
                if step.disable_sql:
                    self._execute(conn, step.disable_sql)
                done.append(step)
                done_keys.add(step.key)
            except SQLAlchemyError as exc:
                self.logger.warning(f"No se pudo desactivar '{step.table}.{step.index_name}': {exc}")
        return done

    def restore(self, conn: Any, steps: Sequence[IndexStep]) -> list[IndexActionResult]:
        """Restaura lo desactivado por prioridad; un resultado por paso. Los únicos que fallan, en ``failed_unique``."""
        results: list[IndexActionResult] = []
        for sql, members in restore_batches(steps):
            try:
                self._execute(conn, sql)
                results.extend(IndexActionResult(s.table, s.index_name, self.dialect, s.action) for s in members)
            except SQLAlchemyError as exc:
                names = ", ".join(f"{s.table}.{s.index_name}" for s in members)
                self.logger.warning(f"Error al restaurar {names}: {exc}")
                for step in members:
                    message = str(exc)
                    if step.unique_columns:
                        dups = self._find_duplicates(conn, step)
                        self.failed_unique.append(f"{step.table}.{step.index_name}")
                        if dups:
                            self.duplicates[f"{step.table}.{step.index_name}"] = dups
                            message = f"{message} | claves duplicadas: {'; '.join(dups)}"
                    results.append(IndexActionResult(step.table, step.index_name, self.dialect, "failed", message))
        return results

    def _find_duplicates(self, conn: Any, step: IndexStep) -> list[str]:
        """Hasta :data:`MAX_DUPLICATES` claves repetidas (``"valores → repeticiones"``); ``[]`` si no se pueden leer."""
        try:
            rows = conn.execute(text(duplicates_sql(self.dialect, step.quoted_table, step.unique_columns))).fetchall()
        except SQLAlchemyError as exc:
            self.logger.debug(f"No se pudieron leer las claves duplicadas de {step.table}.{step.index_name}: {exc}")
            if self._commit:
                conn.rollback()
            return []
        return [f"{', '.join(map(str, row[:-1]))} → {row[-1]}" for row in rows]

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


def rebuild_error(runner: IndexDdlRunner, results: list[IndexActionResult], where: str) -> Exception | None:
    """``IndexRebuildError`` si algún índice único o PK no se reconstruyó (``"all"``); ``None`` si no."""
    if not runner.failed_unique:
        return None
    from ..._core.exceptions import IndexRebuildError

    detail = "; ".join(
        f"{name}: {', '.join(runner.duplicates[name])}" if name in runner.duplicates else name
        for name in runner.failed_unique
    )
    return IndexRebuildError(
        f"{where}: no se pudieron reconstruir índices únicos o PK tras la carga (¿claves duplicadas?): {detail}",
        results=results,
        duplicates=dict(runner.duplicates),
    )


__all__: list[str] = [
    "INDEX_MODES",
    "MAX_DUPLICATES",
    "SUPPORTED_DIALECTS",
    "IndexDdlRunner",
    "IndexMode",
    "IndexStep",
    "SecondaryIndexPlanner",
    "duplicates_sql",
    "rebuild_error",
    "resolve_index_mode",
    "restore_batches",
]
