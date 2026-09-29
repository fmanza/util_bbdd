"""Validación de las vistas de un ``MigrationPlan`` contra el motor destino (V3, sesión 2026-09-29c-migrate-views).

- **PostgreSQL y SQL Server** (DDL transaccional): crea las tablas del plan (opcional) y cada vista en su propio
  *savepoint* dentro de una transacción que se deshace al terminar. No deja nada en el destino.
- **MySQL, MariaDB y Oracle** (el DDL hace commit implícito): solo comprueba la sintaxis con sqlglot en el dialecto
  destino; sin sqlglot no valida (``method="none"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ._dialects import SQLGLOT_DIALECT, sqlglot_available

if TYPE_CHECKING:
    from ..ir.models import MigrationPlan

ValidationMethod = Literal["transaction", "syntax", "none"]
TRANSACTIONAL_DDL_ENGINES: frozenset[str] = frozenset({"postgresql", "sqlserver"})


@dataclass(frozen=True, slots=True)
class ViewValidationResult:
    """Resultado de validar una vista en el destino.

    Attributes:
        view: Nombre de la vista en el destino.
        valid: True/False según la validación; None si no se pudo validar (``method="none"``).
        method: ``"transaction"`` (creada y deshecha en el destino), ``"syntax"`` (solo sintaxis) o ``"none"``.
        error: Mensaje del motor o de sqlglot si no es válida; motivo si no se validó.
    """

    view: str
    valid: bool | None
    method: ValidationMethod
    error: str | None = None


def _sqlalchemy_engine(target: Any) -> Any:
    """Engine de SQLAlchemy desde un ``SyncDatabaseManager`` (``get_sqlalchemy_engine``) o un Engine/Connection."""
    if hasattr(target, "get_sqlalchemy_engine"):
        return target.get_sqlalchemy_engine()
    return target


def _execute_raw(connection: Any, statement: str) -> None:
    """Ejecuta ``statement`` con el cursor del driver y sin parámetros (sin reinterpretar ``%``)."""
    cursor = connection.connection.dbapi_connection.cursor()
    try:
        cursor.execute(statement)
    finally:
        cursor.close()


def _first_line(error: Exception) -> str:
    return str(error).strip().splitlines()[0][:300] if str(error).strip() else type(error).__name__


def _validate_in_transaction(plan: MigrationPlan, target: Any, include_tables: bool) -> list[ViewValidationResult]:
    engine = _sqlalchemy_engine(target)
    connectable = engine.connect() if hasattr(engine, "connect") else engine
    results: list[ViewValidationResult] = []
    try:
        transaction = connectable.begin()
        try:
            if include_tables:
                for statement in plan.emitter.emit_statements(plan.tables, [], []):
                    savepoint = connectable.begin_nested()
                    try:
                        _execute_raw(connectable, statement)
                        savepoint.commit()
                    except Exception:  # noqa: BLE001 - la vista que dependa de esta tabla informará su error
                        savepoint.rollback()
            for view in plan.views:
                if not view.query:
                    continue
                savepoint = connectable.begin_nested()
                try:
                    for statement in plan.emitter.emit_statements([], [view], []):
                        _execute_raw(connectable, statement)
                    savepoint.commit()
                    results.append(ViewValidationResult(view=view.name, valid=True, method="transaction"))
                except Exception as err:  # noqa: BLE001 - error del motor al crear la vista
                    savepoint.rollback()
                    results.append(
                        ViewValidationResult(view=view.name, valid=False, method="transaction", error=_first_line(err))
                    )
        finally:
            transaction.rollback()
    finally:
        if connectable is not engine:
            connectable.close()
    return results


def _validate_syntax(plan: MigrationPlan) -> list[ViewValidationResult]:
    if not sqlglot_available():
        return [
            ViewValidationResult(
                view=view.name,
                valid=None,
                method="none",
                error=f"{plan.target_engine}: el DDL no es transaccional y sqlglot no está instalado",
            )
            for view in plan.views
            if view.query
        ]
    import sqlglot

    dialect = SQLGLOT_DIALECT[plan.target_engine]
    results: list[ViewValidationResult] = []
    for view in plan.views:
        if not view.query:
            continue
        try:
            sqlglot.parse_one(view.query, read=dialect)
            results.append(ViewValidationResult(view=view.name, valid=True, method="syntax"))
        except Exception as err:  # noqa: BLE001 - error de análisis de sqlglot
            results.append(ViewValidationResult(view=view.name, valid=False, method="syntax", error=_first_line(err)))
    return results


def validate_plan_views(
    plan: MigrationPlan, target: Any = None, *, include_tables: bool = True
) -> list[ViewValidationResult]:
    """Valida las vistas de ``plan`` (ver docstring del módulo).

    Args:
        plan: Plan de migración.
        target: ``SyncDatabaseManager`` (o Engine/Connection de SQLAlchemy) del destino. Obligatorio si el destino es
            PostgreSQL o SQL Server; se ignora en el resto.
        include_tables: Crea también las tablas del plan dentro de la transacción (validar antes de ejecutar el plan).
            Con False, las tablas deben existir ya en el destino.

    Raises:
        ValueError: Si el destino es transaccional y no se indica ``target``.
    """
    if plan.target_engine in TRANSACTIONAL_DDL_ENGINES:
        if target is None:
            raise ValueError(f"validate_views con destino {plan.target_engine} necesita la conexión del destino")
        return _validate_in_transaction(plan, target, include_tables)
    return _validate_syntax(plan)


__all__: list[str] = ["TRANSACTIONAL_DDL_ENGINES", "ValidationMethod", "ViewValidationResult", "validate_plan_views"]
