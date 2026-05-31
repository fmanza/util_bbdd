"""Resincronización de contadores PK (sequences, identity, auto_increment) tras carga masiva.

Motores soportados:
  - PostgreSQL: setval() sobre la sequence vinculada (SERIAL / GENERATED AS IDENTITY).
  - SQL Server: DBCC CHECKIDENT con RESEED al MAX actual.
  - MariaDB / MySQL: ALTER TABLE AUTO_INCREMENT = MAX + 1.
  - Oracle >= 12c: ALTER SEQUENCE RESTART START WITH MAX + 1
      (sequence localizada via ALL_TAB_IDENTITY_COLS / USER_TAB_IDENTITY_COLS).
  - Oracle < 12c (trigger + sequence manual): status="unsupported".
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

from sqlalchemy import Column, Engine, Table, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from .._models import PKSyncResult

_log = logging.getLogger(__name__)

_SUPPORTED_DIALECTS = frozenset({"postgresql", "mssql", "mariadb", "mysql", "oracle"})


# ---------------------------------------------------------------------------
# Helpers de quoting — equivalentes a dump._sql_utils, sin dependencia cruzada
# ---------------------------------------------------------------------------


def _qi(name: str, engine: Engine) -> str:
    """Quoted identifier según el dialect del engine."""
    return engine.dialect.identifier_preparer.quote(name)


def _qt(table_name: str, schema: str | None, engine: Engine) -> str:
    """Tabla quoted con prefijo de schema opcional."""
    if schema:
        return f"{_qi(schema, engine)}.{_qi(table_name, engine)}"
    return _qi(table_name, engine)


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------


class PKSequenceSyncer:
    """Sincroniza los contadores PK tras una carga masiva con PKs explícitas.

    Instancia un handler por dialecto y recorre las columnas PK con semántica
    de autoincrement/identity de cada ``Table`` reflejado.

    Ejemplo::

        syncer = PKSequenceSyncer(engine, schema="dbo")
        results = syncer.sync_all(tables)
        for r in results:
            print(r.table_name, r.column_name, r.status, r.max_value)

    Permisos requeridos por motor:

    - **PostgreSQL**: propietario de la tabla o ``SUPERUSER``.
    - **SQL Server**: ``ALTER TABLE`` permission o membresía en ``db_owner``.
    - **MariaDB/MySQL**: ``ALTER`` privilege sobre la tabla.
    - **Oracle >= 12c**: ``SELECT`` en ``ALL_TAB_IDENTITY_COLS`` (disponible por
      defecto) + ``ALTER ANY SEQUENCE`` o ser propietario de la sequence.
    """

    def __init__(self, engine: Engine, schema: str | None = None) -> None:
        self._engine = engine
        self._schema = schema
        self._dialect = engine.dialect.name

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def sync_table(self, table: Table) -> list[PKSyncResult]:
        """Sincroniza los contadores de todas las columnas PK con identity/autoincrement."""
        identity_cols = _get_identity_pk_cols(table)
        if not identity_cols:
            return []

        if self._dialect not in _SUPPORTED_DIALECTS:
            return [
                PKSyncResult(
                    table_name=table.name,
                    column_name=col.name,
                    engine_dialect=self._dialect,
                    max_value=None,
                    status="unsupported",
                    error_msg=f"Dialect '{self._dialect}' not supported for PK sequence sync.",
                )
                for col in identity_cols
            ]

        handler: Callable[[Any, Table, Column], PKSyncResult] = self._get_handler()
        results: list[PKSyncResult] = []

        with self._engine.connect() as conn:
            for col in identity_cols:
                try:
                    result = handler(conn, table, col)
                    results.append(result)
                    _log.info(
                        "PK sync [%s] %s.%s → %s (max=%s)",
                        self._dialect,
                        table.name,
                        col.name,
                        result.status,
                        result.max_value,
                    )
                except SQLAlchemyError as exc:
                    try:
                        conn.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    results.append(
                        PKSyncResult(
                            table_name=table.name,
                            column_name=col.name,
                            engine_dialect=self._dialect,
                            max_value=None,
                            status="error",
                            error_msg=str(exc),
                        )
                    )
                    _log.warning("PK sync error en %s.%s: %s", table.name, col.name, exc)

        return results

    def sync_all(self, tables: list[Table]) -> list[PKSyncResult]:
        """Sincroniza los contadores de todas las tablas de la lista."""
        results: list[PKSyncResult] = []
        for table in tables:
            results.extend(self.sync_table(table))
        return results

    # ------------------------------------------------------------------
    # Dispatch por dialecto
    # ------------------------------------------------------------------

    def _get_handler(self) -> Callable[[Any, Table, Column], PKSyncResult]:
        return {
            "postgresql": self._sync_postgresql,
            "mssql": self._sync_mssql,
            "mariadb": self._sync_mariadb,
            "mysql": self._sync_mariadb,
            "oracle": self._sync_oracle,
        }.get(self._dialect, self._sync_unsupported)

    # ------------------------------------------------------------------
    # Handlers por motor
    # ------------------------------------------------------------------

    def _sync_postgresql(self, conn: Any, table: Table, col: Column) -> PKSyncResult:
        """PostgreSQL: setval() sobre la sequence vinculada (SERIAL / IDENTITY)."""
        schema = table.schema or self._schema
        table_ref = f"{schema}.{table.name}" if schema else table.name

        seq_name: str | None = conn.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": table_ref, "col": col.name},
        ).scalar()

        if seq_name is None:
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="postgresql",
                max_value=None,
                status="skipped",
                error_msg="No sequence found via pg_get_serial_sequence (UUID or natural PK).",
            )

        max_val_raw = conn.execute(select(func.max(col))).scalar()

        if max_val_raw is None:
            # Tabla vacía: is_called=false → nextval() devolverá 1 sin incrementar primero
            conn.execute(text("SELECT setval(:seq, 1, false)"), {"seq": seq_name})
            conn.commit()
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="postgresql",
                max_value=None,
                status="no_rows",
            )

        max_val = int(max_val_raw)
        # is_called=true → nextval() devuelve max_val + 1
        conn.execute(text("SELECT setval(:seq, :val, true)"), {"seq": seq_name, "val": max_val})
        conn.commit()

        return PKSyncResult(
            table_name=table.name,
            column_name=col.name,
            engine_dialect="postgresql",
            max_value=max_val,
            status="synced",
        )

    def _sync_mssql(self, conn: Any, table: Table, col: Column) -> PKSyncResult:
        """SQL Server: DBCC CHECKIDENT con RESEED al MAX actual."""
        if getattr(col, "identity", None) is None:
            # autoincrement=True pero sin propiedad IDENTITY declarativa
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="mssql",
                max_value=None,
                status="skipped",
                error_msg="Column has autoincrement=True but no IDENTITY property in metadata.",
            )

        schema = table.schema or self._schema
        # DBCC CHECKIDENT requiere el nombre de tabla como literal de texto
        table_ref = f"{schema}.{table.name}" if schema else table.name

        max_val_raw = conn.execute(select(func.max(col))).scalar()

        if max_val_raw is None:
            # Tabla vacía: RESEED a 0; el próximo INSERT obtendrá el seed (habitualmente 1)
            conn.execute(text(f"DBCC CHECKIDENT ('{table_ref}', RESEED, 0)"))
            conn.commit()
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="mssql",
                max_value=None,
                status="no_rows",
            )

        max_val = int(max_val_raw)
        conn.execute(text(f"DBCC CHECKIDENT ('{table_ref}', RESEED, {max_val})"))
        conn.commit()

        return PKSyncResult(
            table_name=table.name,
            column_name=col.name,
            engine_dialect="mssql",
            max_value=max_val,
            status="synced",
        )

    def _sync_mariadb(self, conn: Any, table: Table, col: Column) -> PKSyncResult:
        """MariaDB/MySQL: ALTER TABLE AUTO_INCREMENT = MAX + 1."""
        schema = table.schema or self._schema
        quoted_table = _qt(table.name, schema, self._engine)

        max_val_raw = conn.execute(select(func.max(col))).scalar()

        if max_val_raw is None:
            next_val = 1
            max_val: int | None = None
            status = "no_rows"
        else:
            max_val = int(max_val_raw)
            next_val = max_val + 1
            status = "synced"

        # DDL en InnoDB → commit implícito; el conn.commit() posterior es no-op
        conn.execute(text(f"ALTER TABLE {quoted_table} AUTO_INCREMENT = {next_val}"))
        conn.commit()

        return PKSyncResult(
            table_name=table.name,
            column_name=col.name,
            engine_dialect=self._dialect,
            max_value=max_val,
            status=status,
        )

    def _sync_oracle(self, conn: Any, table: Table, col: Column) -> PKSyncResult:
        """Oracle >= 12c: RESTART SEQUENCE localizada via ALL_TAB_IDENTITY_COLS."""
        if getattr(col, "identity", None) is None:
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="oracle",
                max_value=None,
                status="unsupported",
                error_msg=(
                    "Oracle pre-12c: trigger+sequence pattern has no declarative metadata. "
                    "Resync manually with ALTER SEQUENCE."
                ),
            )

        schema = table.schema or self._schema

        # Localizar sequence en el catálogo de Oracle
        if schema:
            seq_row = conn.execute(
                text(
                    "SELECT sequence_name FROM all_tab_identity_cols "
                    "WHERE owner = UPPER(:owner) "
                    "  AND table_name = UPPER(:tbl) "
                    "  AND column_name = UPPER(:col)"
                ),
                {"owner": schema, "tbl": table.name, "col": col.name},
            ).fetchone()
        else:
            seq_row = conn.execute(
                text(
                    "SELECT sequence_name FROM user_tab_identity_cols "
                    "WHERE table_name = UPPER(:tbl) "
                    "  AND column_name = UPPER(:col)"
                ),
                {"tbl": table.name, "col": col.name},
            ).fetchone()

        if seq_row is None:
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="oracle",
                max_value=None,
                status="unsupported",
                error_msg="Sequence name not found in ALL_TAB_IDENTITY_COLS / USER_TAB_IDENTITY_COLS.",
            )

        seq_name: str = seq_row[0]
        max_val_raw = conn.execute(select(func.max(col))).scalar()

        if max_val_raw is None:
            next_val = 1
            max_val2: int | None = None
            status = "no_rows"
        else:
            max_val2 = int(max_val_raw)
            next_val = max_val2 + 1
            status = "synced"

        # Quoted sequence ref — nombres Oracle del catálogo ya están en uppercase
        quoted_seq = _qi(seq_name, self._engine)
        seq_ref = f"{_qi(schema, self._engine)}.{quoted_seq}" if schema else quoted_seq

        # ALTER SEQUENCE RESTART START WITH n (sintaxis Oracle 12c+)
        conn.execute(text(f"ALTER SEQUENCE {seq_ref} RESTART START WITH {next_val}"))
        conn.commit()

        return PKSyncResult(
            table_name=table.name,
            column_name=col.name,
            engine_dialect="oracle",
            max_value=max_val2,
            status=status,
        )

    def _sync_unsupported(self, conn: Any, table: Table, col: Column) -> PKSyncResult:
        return PKSyncResult(
            table_name=table.name,
            column_name=col.name,
            engine_dialect=self._dialect,
            max_value=None,
            status="unsupported",
            error_msg=f"Dialect '{self._dialect}' not supported for PK sequence sync.",
        )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _get_identity_pk_cols(table: Table) -> list[Column]:
    """Devuelve las columnas PK con semántica de autoincrement/identity.

    Reutiliza el mismo criterio que ``get_insert_columns`` en validation.py
    para garantizar detección consistente entre insert y sync.
    """
    return [
        col
        for col in table.primary_key.columns
        if col.autoincrement is True or getattr(col, "identity", None) is not None
    ]


__all__: list[str] = ["PKSequenceSyncer"]
