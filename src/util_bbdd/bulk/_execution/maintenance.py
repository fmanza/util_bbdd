"""Desactivación y restauración de constraints e índices de una tabla durante una carga masiva.

Cuerpo de :meth:`BulkCrud.maintenance_scope`, extraído de ``bulk/crud.py`` en v1.1.0 (A5, SRP de ``BulkCrud`` por dentro).
Desde 3.2.0 los índices siguen la estrategia común con ``dump`` (``bulk/_support/secondary_indexes.py``). La firma
pública, el resultado (:class:`MaintenanceScopeResult`) y la documentación siguen en ``BulkCrud``.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, Table, literal, select, text
from sqlalchemy.exc import SQLAlchemyError

from ...metadata import facts
from ...metadata.model import Kind
from .._models import MaintenanceScopeConstraintResult, MaintenanceScopeResult
from .._support.dialect import (
    MYSQL_FAMILY,
    can_disable_pg_triggers,
    disable_table_integrity_sql,
    enable_table_integrity_sql,
)
from .._support.fk_orphans import orphan_check_sql
from .._support.secondary_indexes import (
    SUPPORTED_DIALECTS,
    IndexDdlRunner,
    IndexMode,
    IndexStep,
    SecondaryIndexPlanner,
    rebuild_error,
)
from .session import CommitCadence, SessionScope


class TableMaintenance:
    """Prepara una tabla para una carga de alto volumen dentro de la sesión de ``BulkCrud`` y la restaura al salir.

    ``BulkCrud`` crea una instancia por llamada a ``maintenance_scope`` con su engine, su sesión, la cadencia de commit
    de su ejecutor, su lector de metadatos y su logger.

    Args:
        engine: Engine de la carga (dialecto, preparador de identificadores y conexión nueva para Oracle).
        session: Sesión de ``bulk_session()``: conexión activa y acciones posteriores a su fin.
        cadence: Cadencia de commit del ejecutor (``commit_every_n_chunks``).
        table_snapshot: Metadatos de una tabla por tipo (``BulkCrud._table_snapshot``).
        logger: Logger de ``BulkCrud``.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        session: SessionScope,
        cadence: CommitCadence,
        table_snapshot: Callable[[Table, set[Kind]], Any],
        logger: logging.Logger,
    ) -> None:
        self.engine: Engine = engine
        self._session: SessionScope = session
        self._cadence: CommitCadence = cadence
        self._table_snapshot: Callable[[Table, set[Kind]], Any] = table_snapshot
        self.logger: logging.Logger = logger
        #: MariaDB/MySQL: comprobar huérfanos al reactivar ``FOREIGN_KEY_CHECKS`` (v3.3.0, ``validate_fks_after``).
        self.validate_fks_after: bool = False

    @contextmanager
    def scope(
        self,
        tabla: Table,
        tabla_destino: str,
        *,
        disable_constraints: bool,
        index_mode: IndexMode | None,
        require_optimization: bool,
        validate_fks_after: bool = True,
    ) -> Generator[MaintenanceScopeResult, None, None]:
        """Ver :meth:`BulkCrud.maintenance_scope` (``tabla`` ya reflejada)."""
        dialect: str = self.engine.dialect.name
        quoted_name = self.engine.dialect.identifier_preparer.format_table(tabla)
        self.validate_fks_after = validate_fks_after

        conn = self._session.connection
        if conn is None:
            raise RuntimeError(
                "maintenance_scope requiere una sesión activa. "
                "Úsalo siempre dentro de bulk_session(): "
                "'with bulk.bulk_session():\\n    with bulk.maintenance_scope(...):\\n        ...'"
            )

        pg_disabled = False
        mssql_constraints_disabled = False
        indexes_disabled: list[IndexStep] = []
        oracle_disabled: list[str] = []
        result = MaintenanceScopeResult()
        rebuild_failure: list[Exception] = []

        def restore(on: Any = conn) -> list[MaintenanceScopeConstraintResult]:
            if index_mode is not None and indexes_disabled:
                runner = self._index_runner(dialect)
                result.index_results = runner.restore(on, indexes_disabled)
                error = rebuild_error(runner, result.index_results, f"maintenance_scope('{tabla_destino}')")
                if error is not None:
                    rebuild_failure.append(error)
            if disable_constraints:
                return self._enable_constraints(
                    on, dialect, quoted_name, tabla, pg_disabled, mssql_constraints_disabled, oracle_disabled
                )
            return []

        # La restauración del camino normal va en el ``finally`` (no tras el ``try``) para que ninguna salida del
        # generador la salte; ``failed`` la reserva a ese camino, porque tras un error la hace ``_restore_after_error``.
        failed = False
        try:
            if disable_constraints:
                pg_disabled, mssql_constraints_disabled, oracle_disabled = self._disable_constraints(
                    conn, dialect, quoted_name, tabla, tabla_destino, require_optimization
                )
                result.optimization_applied = (
                    pg_disabled or mssql_constraints_disabled or bool(oracle_disabled) or dialect in MYSQL_FAMILY
                )
            if index_mode is not None:
                indexes_disabled = self._disable_indexes(conn, dialect, quoted_name, tabla, tabla_destino, index_mode)
                self._warn_all_mode(conn, tabla, tabla_destino, indexes_disabled)
            self.logger.info(f"🛠️ Modo mantenimiento activado: {tabla_destino} ({dialect})")
            yield result
        except BaseException:
            failed = True
            self._restore_after_error(conn, restore, tabla_destino)
            raise
        finally:
            if not failed:
                result.constraint_results = restore()
                self.logger.debug(f"🛠️ Modo mantenimiento finalizado: {tabla_destino}")
                if rebuild_failure:
                    # Tras restaurar todo (índices, FK entrantes y constraints): en PostgreSQL y SQL Server la sesión
                    # deshace la carga entera; en Oracle y MariaDB/MySQL el DDL ya confirmó.
                    raise rebuild_failure[0]

    def _warn_all_mode(self, conn: Any, tabla: Table, tabla_destino: str, disabled: list[IndexStep]) -> None:
        """Aviso de ``disable_indexes="all"`` y, si la tabla ya tiene filas, de que sus duplicados no se detectarán.

        Solo si de verdad se desactivó un único (en la sesión atómica de InnoDB, por ejemplo, no se toca nada).
        """
        if not any(step.unique and step.skip_reason is None for step in disabled):
            return
        self.logger.warning(
            f"⚠️ disable_indexes='all' en {tabla_destino}: PK/UNIQUE desactivadas durante la carga, sin control de "
            "duplicados. Solo para datos ya validados; si la reconstrucción falla se lanza IndexRebuildError."
        )
        try:
            has_rows = conn.execute(select(literal(1)).select_from(tabla).limit(1)).first() is not None
        except SQLAlchemyError:
            return
        if has_rows:
            self.logger.warning(
                f"⚠️ {tabla_destino} ya tiene filas: con disable_indexes='all' los duplicados contra ellas solo "
                "aparecerán al reconstruir los índices únicos."
            )

    def _restore_after_error(
        self, conn: Any, restore: Callable[..., list[MaintenanceScopeConstraintResult]], tabla_destino: str
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
        cadence = self._cadence
        if cadence.every is None and self.engine.dialect.name == "oracle":
            # Oracle: el DDL no es transaccional y ENABLE CONSTRAINT confirmaría lo pendiente de la sesión (H-31). Se
            # reactivan cuando la sesión haya hecho rollback, en otra conexión (las filas pendientes bloquean la tabla).
            def restore_after_rollback() -> None:
                with self.engine.connect() as fresh:
                    restore(fresh)
                    fresh.commit()

            self._session.after_end.append(restore_after_rollback)
            return
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

    def _disable_constraints(
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
            all_names = self._oracle_fetch_constraint_names(tabla)
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

    def _disable_indexes(
        self,
        conn: Any,
        dialect: str,
        quoted_name: str,
        tabla: Table,
        tabla_destino: str,
        mode: IndexMode = "secondary",
    ) -> list[IndexStep]:
        """Deshabilita los índices de ``mode`` (estrategia común con ``dump``); devuelve los que hay que restaurar.

        En la conexión de la sesión. SQL Server y PostgreSQL: DDL transaccional, cada sentencia en un savepoint (un fallo
        no aborta la sesión y su rollback deshace la desactivación). Oracle: el DDL confirma la transacción (como sus
        constraints). MariaDB/MySQL InnoDB: ``DROP INDEX`` confirma la transacción, así que solo se aplica con
        ``commit_every_n_chunks`` (sesión no atómica); en la sesión atómica se omite (auditoría de bulk 2026-09-24,
        hallazgo 8). MyISAM/Aria: ``DISABLE KEYS``.
        """
        if dialect in MYSQL_FAMILY and self._cadence.every is None:
            storage_engine = facts.storage_engine(conn, tabla.schema, tabla.name)
            if str(storage_engine or "").upper() not in ("MYISAM", "ARIA"):
                self.logger.info(
                    f"ℹ️ Se omite la desactivación de índices en {tabla_destino}: motor {storage_engine}. En InnoDB el "
                    "DROP INDEX provocaría un commit implícito y la sesión dejaría de ser atómica; se aplica con "
                    "commit_every_n_chunks, en dump (manage_indexes) y en la carga paralela."
                )
                return []
        if dialect not in SUPPORTED_DIALECTS:
            return []
        planner = SecondaryIndexPlanner(dialect, self.engine.dialect.identifier_preparer)
        steps = planner.plan(conn, table=tabla.name, schema=tabla.schema, quoted_table=quoted_name, mode=mode)
        innodb = not any(step.index_name == "*" for step in steps)  # MyISAM/Aria: un paso DISABLE KEYS ("*")
        if dialect in MYSQL_FAMILY and innodb and any(step.grouped for step in steps):
            self.logger.warning(
                f"⚠️ {tabla_destino}: DROP INDEX en InnoDB confirma lo pendiente de la sesión (commit implícito)."
            )
        return self._index_runner(dialect).disable(conn, steps)

    def _index_runner(self, dialect: str) -> IndexDdlRunner:
        return IndexDdlRunner(dialect, self.logger, commit=False, savepoint=dialect in ("mssql", "postgresql"))

    def _enable_constraints(
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
            if self.validate_fks_after:
                return self._check_fk_orphans(conn, tabla, quoted_name)
            return [
                MaintenanceScopeConstraintResult(
                    constraint_name="FOREIGN_KEY_CHECKS",
                    status="unverified",
                    error_msg="FK_CHECKS restaurado; no hay validación retroactiva de integridad.",
                )
            ]
        if dialect == "postgresql" and pg_disabled:
            conn.execute(text(enable_table_integrity_sql(dialect, quoted_name)))
            return self._check_fk_orphans(conn, tabla, quoted_name)
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

    def _check_fk_orphans(self, conn: Any, tabla: Table, quoted_name: str) -> list[MaintenanceScopeConstraintResult]:
        """Filas huérfanas de cada FK de la tabla (``bulk/_support/fk_orphans.py``).

        PostgreSQL siempre (audit H-01, 2026-09-27: ``DISABLE TRIGGER`` no marca la FK como ``NOT VALID``); MariaDB/MySQL
        con ``validate_fks_after`` (v3.3.0: ``FOREIGN_KEY_CHECKS=1`` no valida lo ya cargado).
        """
        try:
            fks = [
                {
                    "name": fk.name,
                    "constrained_columns": list(fk.columns),
                    "referred_schema": fk.ref_schema,
                    "referred_table": fk.ref_table,
                    "referred_columns": list(fk.ref_columns),
                }
                for fk in self._table_snapshot(tabla, {Kind.FOREIGN_KEYS}).foreign_keys(tabla.name)
            ]
        except Exception:  # engine simulado en tests, motor sin catálogo o sin permisos
            self.logger.debug(f"⚠️ orphan-check omitido en '{tabla.name}': catálogo no disponible para este engine.")
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
            sql = orphan_check_sql(self.engine.dialect.name, prep, quoted_name, fk)
            if sql is None:
                continue  # metadata FK malformada
            fk_name = fk.get("name") or "?"
            try:
                orphan = conn.execute(text(sql)).first()
            except SQLAlchemyError:
                continue
            if orphan is not None:
                msg = (
                    f"FK '{fk_name}' en '{tabla.name}': hay filas sin fila referenciada "
                    f"en '{fk.get('referred_table')}'. La FK está marcada como válida pero contiene violaciones. "
                    "Verificar integridad manualmente o hacer rollback."
                )
                self.logger.warning(f"⚠️ {msg}")
                results.append(
                    MaintenanceScopeConstraintResult(constraint_name=fk_name, status="failed", error_msg=msg)
                )
            else:
                results.append(MaintenanceScopeConstraintResult(constraint_name=fk_name, status="enabled"))
        return results

    def _oracle_fetch_constraint_names(self, tabla: Table) -> list[str]:
        """Retorna nombres de FK, CHECK (no SYS_C) y UNIQUE constraints de la tabla para Oracle."""
        try:
            snapshot = self._table_snapshot(tabla, {Kind.FOREIGN_KEYS, Kind.CHECKS, Kind.UNIQUES})
        except Exception:  # engine simulado en tests, conexión sin permisos
            return []
        # Nombres como los guarda Oracle (los cita quote_identifier): FK, CHECK con nombre propio y UNIQUE
        name = tabla.name
        return (
            [fk.name for fk in snapshot.foreign_keys(name) if fk.name]
            + [c.name for c in snapshot.checks(name) if c.name and not c.name.upper().startswith("SYS_C")]
            + [u.name for u in snapshot.uniques(name) if u.name]
        )
