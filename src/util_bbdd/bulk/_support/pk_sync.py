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
from typing import Any, ClassVar, Literal

from sqlalchemy import Column, Engine, Table, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from ...metadata.oracle.tables import fetch_identity_generation_sql
from .._models import PKSyncResult
from .sql_quoting import quote_identifier as _qi, quote_table as _qt
from .validation import is_identity_pk

_SUPPORTED_DIALECTS = frozenset({"postgresql", "mssql", "mariadb", "mysql", "oracle"})


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

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

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
                    self.logger.info(
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
                    self.logger.warning("PK sync error en %s.%s: %s", table.name, col.name, exc)

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
        # pg_get_serial_sequence analiza el primer argumento como identificador SQL (sin comillas lo pasa a minúsculas):
        # se cita como el dialecto (auditoría de bulk 2026-09-24, hallazgo 5), si no "Orders" se buscaba como orders.
        table_ref = _qt(table.name, schema, self._engine)

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
        # DBCC CHECKIDENT requiere el nombre de tabla como literal de texto: se cita cada
        # parte (bracket quoting, igual que _sync_mariadb con backticks) y se escapan las
        # comillas simples embebidas para no romper el literal ni permitir inyección.
        table_ref = _qt(table.name, schema, self._engine).replace("'", "''")

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

        status: Literal["synced", "no_rows"]
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
        """Oracle >= 12c: ``ALTER TABLE … MODIFY (col GENERATED … AS IDENTITY (START WITH n))``."""
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
        # Nombres como en el catálogo (auditoría de bulk 2026-09-24, hallazgo 5): denormalize_name pasa a mayúsculas los
        # no sensibles a mayúsculas y deja tal cual los creados entre comillas (p.ej. "orders"), que UPPER() no encontraba.
        denormalize = self._engine.dialect.denormalize_name

        # Tipo de identity en el catálogo: hay que repetirlo al modificarla (ALWAYS / BY DEFAULT [ON NULL]).
        if schema:
            identity_row = conn.execute(
                text(fetch_identity_generation_sql(with_owner=True)),
                {"owner": denormalize(schema), "tbl": denormalize(table.name), "col": denormalize(col.name)},
            ).fetchone()
        else:
            identity_row = conn.execute(
                text(fetch_identity_generation_sql(with_owner=False)),
                {"tbl": denormalize(table.name), "col": denormalize(col.name)},
            ).fetchone()

        if identity_row is None:
            return PKSyncResult(
                table_name=table.name,
                column_name=col.name,
                engine_dialect="oracle",
                max_value=None,
                status="unsupported",
                error_msg="Identity column not found in ALL_TAB_IDENTITY_COLS / USER_TAB_IDENTITY_COLS.",
            )

        generation_type, default_on_null = identity_row
        max_val_raw = conn.execute(select(func.max(col))).scalar()

        status: Literal["synced", "no_rows"]
        if max_val_raw is None:
            next_val = 1
            max_val2: int | None = None
            status = "no_rows"
        else:
            max_val2 = int(max_val_raw)
            next_val = max_val2 + 1
            status = "synced"

        # La secuencia de una identity (ISEQ$$_n) no admite ALTER SEQUENCE: ORA-32793 "Cannot alter a system-generated
        # sequence" (auditoría de bulk 2026-09-24, hallazgo 9: la sincronización en Oracle siempre acababa en error). Se
        # modifica la identity de la columna conservando su tipo de generación.
        if generation_type == "ALWAYS":
            generated = "ALWAYS"
        elif default_on_null == "YES":
            generated = "BY DEFAULT ON NULL"
        else:
            generated = "BY DEFAULT"
        quoted_table = _qt(table.name, schema, self._engine)
        quoted_col = _qi(col.name, self._engine)
        conn.execute(
            text(
                f"ALTER TABLE {quoted_table} MODIFY ({quoted_col} GENERATED {generated} AS IDENTITY "
                f"(START WITH {next_val}))"
            )
        )
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

    Mismo criterio que ``get_insert_columns`` (``is_identity_pk``), para detectar igual en insert y sync.
    """
    return [col for col in table.primary_key.columns if is_identity_pk(col)]


__all__: list[str] = ["PKSequenceSyncer"]
