"""Orquestador principal del módulo migrate.

MigrationPlanner coordina extractor → transformer → emitter para producir
un MigrationPlan ejecutable o exportable como script SQL.
"""

from __future__ import annotations

from typing import Any, Literal

from .charset import DEFAULT_CHARSET, DEFAULT_COLLATION, validate_charset, validate_collation
from .emitters.mariadb import MariaDBDDLEmitter
from .extractors.oracle import OracleSchemaExtractor
from .ir.models import MigrationPlan, MigrationWarning
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer

NumberFallback = Literal["DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)"]

_SUPPORTED_SOURCE: frozenset[str] = frozenset({"oracle"})
_SUPPORTED_TARGET: frozenset[str] = frozenset({"mariadb"})


class MigrationPlanner:
    """Orquestador de migración DDL entre motores.

    Args:
        source_engine: Motor origen (actualmente solo "oracle").
        target_engine: Motor destino (actualmente solo "mariadb").
        charset: CHARACTER SET MariaDB (obligatorio; default: utf8mb4).
        collation: COLLATE MariaDB (obligatorio; default: utf8mb4_unicode_ci).
        number_fallback: Tipo destino para NUMBER Oracle sin precisión.
        engine: Motor de almacenamiento MariaDB (default: InnoDB).

    Raises:
        ValueError: Si source_engine o target_engine no están soportados,
                    o si charset/collation no son válidos.
    """

    def __init__(
        self,
        source_engine: str = "oracle",
        target_engine: str = "mariadb",
        charset: str = DEFAULT_CHARSET,
        collation: str = DEFAULT_COLLATION,
        number_fallback: NumberFallback = "DOUBLE",
        engine: str = "InnoDB",
    ) -> None:
        src = source_engine.strip().lower()
        tgt = target_engine.strip().lower()

        if src not in _SUPPORTED_SOURCE:
            raise ValueError(f"Motor origen '{source_engine}' no soportado. Soportados: {sorted(_SUPPORTED_SOURCE)}")
        if tgt not in _SUPPORTED_TARGET:
            raise ValueError(f"Motor destino '{target_engine}' no soportado. Soportados: {sorted(_SUPPORTED_TARGET)}")

        self._source_engine = src
        self._target_engine = tgt
        self._charset = validate_charset(charset)
        self._collation = validate_collation(collation)
        self._number_fallback = number_fallback
        self._engine = engine

    def plan(self, connection: Any, schema: str) -> MigrationPlan:
        """Extrae y transforma el esquema Oracle, produciendo un MigrationPlan.

        Args:
            connection: SyncDatabaseManager de Oracle (duck-typed).
            schema: Nombre del schema/owner a migrar.

        Returns:
            MigrationPlan listo para emit_ddl() o execute().
        """
        extractor = OracleSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)

        transformer = OracleToMariaDBTransformer(
            number_fallback=self._number_fallback,
            charset=self._charset,
        )
        transformed = transformer.transform(raw_tables)

        # Consolidar todos los warnings de tablas y columnas
        all_warnings: list[MigrationWarning] = []
        for table in transformed:
            all_warnings.extend(table.warnings)
            for col in table.columns:
                all_warnings.extend(col.warnings)

        emitter = MariaDBDDLEmitter(
            charset=self._charset,
            collation=self._collation,
            engine=self._engine,
        )

        return MigrationPlan(
            tables=transformed,
            warnings=all_warnings,
            source_schema=schema,
            source_engine=self._source_engine,
            target_engine=self._target_engine,
            emitter=emitter,
        )


__all__: list[str] = [
    "MigrationPlanner",
    "NumberFallback",
]
