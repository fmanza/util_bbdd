"""Orquestador principal del módulo migrate.

MigrationPlanner coordina extractor → transformer → emitter para producir
un MigrationPlan ejecutable o exportable como script SQL.
"""

from __future__ import annotations

from typing import Any, Literal

from .charset import DEFAULT_CHARSET, DEFAULT_COLLATION, validate_charset, validate_collation
from .emitters.mariadb import MariaDBDDLEmitter
from .emitters.oracle import OracleDDLEmitter
from .emitters.postgresql import PostgreSQLDDLEmitter
from .emitters.sqlserver import SQLServerDDLEmitter
from .extractors.mariadb import MariaDBSchemaExtractor
from .extractors.oracle import OracleSchemaExtractor
from .extractors.sqlserver import SQLServerSchemaExtractor
from .ir.models import MigrationPlan, MigrationWarning
from .transformers.mariadb_to_oracle import MariaDBToOracleTransformer
from .transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from .transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer
from .transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from .transformers.oracle_to_sqlserver import OracleToSQLServerTransformer
from .transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from .transformers.sqlserver_to_oracle import SQLServerToOracleTransformer
from .transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer

NumberFallback = Literal["DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)"]

_SUPPORTED_SOURCE: frozenset[str] = frozenset({"oracle", "mariadb", "sqlserver"})
_SUPPORTED_TARGET: frozenset[str] = frozenset({"mariadb", "sqlserver", "postgresql", "oracle"})

# Remapeo de NumberFallback inválido para SQL Server
_SS_FALLBACK_REMAP: dict[str, str] = {"DOUBLE": "FLOAT"}

# Remapeo de NumberFallback para PostgreSQL (DOUBLE → DOUBLE PRECISION)
_PG_FALLBACK_REMAP: dict[str, str] = {"DOUBLE": "DOUBLE PRECISION"}


class MigrationPlanner:
    """Orquestador de migración DDL entre motores.

    Args:
        source_engine: Motor origen ("oracle" o "mariadb").
        target_engine: Motor destino ("mariadb", "sqlserver", "postgresql" o "oracle").
        charset: CHARACTER SET MariaDB (solo aplica cuando target_engine="mariadb"
            o source_engine="mariadb" y target_engine="mariadb").
        collation: COLLATE MariaDB (solo aplica cuando target_engine="mariadb").
        number_fallback: Tipo destino para NUMBER Oracle sin precisión
            (solo cuando source_engine="oracle").
        engine: Motor de almacenamiento MariaDB (solo aplica cuando target_engine="mariadb").
        int_display_width: Display width para INT en MariaDB (default: 11).
            Usar 0 para emitir solo ``INT`` sin paréntesis.
            Solo aplica cuando source_engine="oracle" y target_engine="mariadb".
        sql_server_collation: COLLATE a nivel columna para SQL Server (opcional).
            Si None, no se emite cláusula COLLATE (usa collation de la BD destino).
        pg_schema: Schema PostgreSQL (opcional). Si se indica, emite
            ``SET search_path = schema;`` al inicio del script DDL.

    Raises:
        ValueError: Si source_engine o target_engine no están soportados,
                    si source_engine == target_engine, o si charset/collation
                    no son válidos para MariaDB.
    """

    def __init__(
        self,
        source_engine: str = "oracle",
        target_engine: str = "mariadb",
        charset: str = DEFAULT_CHARSET,
        collation: str = DEFAULT_COLLATION,
        number_fallback: NumberFallback = "DOUBLE",
        engine: str = "InnoDB",
        int_display_width: int = 11,
        sql_server_collation: str | None = None,
        pg_schema: str | None = None,
    ) -> None:
        src = source_engine.strip().lower()
        tgt = target_engine.strip().lower()

        if src not in _SUPPORTED_SOURCE:
            raise ValueError(
                f"Motor origen '{source_engine}' no soportado. Soportados: {sorted(_SUPPORTED_SOURCE)}"
            )
        if tgt not in _SUPPORTED_TARGET:
            raise ValueError(
                f"Motor destino '{target_engine}' no soportado. Soportados: {sorted(_SUPPORTED_TARGET)}"
            )
        if src == tgt:
            raise ValueError(
                f"Motor origen y destino son el mismo ('{src}'). "
                "La migración requiere motores distintos."
            )

        self._source_engine = src
        self._target_engine = tgt
        self._number_fallback = number_fallback
        self._engine = engine
        self._int_display_width = int_display_width
        self._sql_server_collation = sql_server_collation
        self._pg_schema = pg_schema

        if tgt == "mariadb":
            self._charset = validate_charset(charset)
            self._collation = validate_collation(collation)
        else:
            self._charset = charset
            self._collation = collation

    def plan(self, connection: Any, schema: str) -> MigrationPlan:
        """Extrae y transforma el esquema origen, produciendo un MigrationPlan.

        Args:
            connection: SyncDatabaseManager del motor origen (duck-typed).
            schema: Nombre del schema/owner/database a migrar.
                Para SQL Server corresponde a TABLE_SCHEMA (ej. ``'dbo'``).

        Returns:
            MigrationPlan listo para emit_ddl() o execute().
        """
        if self._source_engine == "oracle":
            return self._plan_from_oracle(connection, schema)
        elif self._source_engine == "mariadb":
            return self._plan_from_mariadb(connection, schema)
        else:  # sqlserver
            return self._plan_from_sqlserver(connection, schema)

    # ─── Pipelines por motor origen ───────────────────────────────────────────

    def _plan_from_oracle(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline Oracle → (MariaDB | SQL Server | PostgreSQL)."""
        extractor = OracleSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)

        if self._target_engine == "mariadb":
            transformer: Any = OracleToMariaDBTransformer(
                number_fallback=self._number_fallback,
                charset=self._charset,
                int_display_width=self._int_display_width,
            )
            emitter: Any = MariaDBDDLEmitter(
                charset=self._charset,
                collation=self._collation,
                engine=self._engine,
            )
        elif self._target_engine == "sqlserver":
            ss_fallback = _SS_FALLBACK_REMAP.get(self._number_fallback, self._number_fallback)
            transformer = OracleToSQLServerTransformer(number_fallback=ss_fallback)
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)
        else:  # postgresql
            pg_fallback = _PG_FALLBACK_REMAP.get(self._number_fallback, self._number_fallback)
            transformer = OracleToPostgreSQLTransformer(number_fallback=pg_fallback)
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, schema)

    def _plan_from_mariadb(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline MariaDB → (Oracle | SQL Server | PostgreSQL)."""
        extractor = MariaDBSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)

        if self._target_engine == "oracle":
            transformer: Any = MariaDBToOracleTransformer()
            emitter: Any = OracleDDLEmitter()
        elif self._target_engine == "sqlserver":
            transformer = MariaDBToSQLServerTransformer()
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)
        else:  # postgresql
            transformer = MariaDBToPostgreSQLTransformer()
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, schema)

    def _plan_from_sqlserver(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline SQL Server → (Oracle | MariaDB | PostgreSQL)."""
        extractor = SQLServerSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)

        if self._target_engine == "oracle":
            transformer: Any = SQLServerToOracleTransformer()
            emitter: Any = OracleDDLEmitter()
        elif self._target_engine == "mariadb":
            transformer = SQLServerToMariaDBTransformer()
            emitter = MariaDBDDLEmitter(
                charset=self._charset,
                collation=self._collation,
                engine=self._engine,
            )
        else:  # postgresql
            transformer = SQLServerToPostgreSQLTransformer()
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, schema)

    # ─── Construcción del plan ────────────────────────────────────────────────

    def _build_plan(
        self,
        transformer: Any,
        emitter: Any,
        raw_tables: list[Any],
        raw_views: list[Any],
        schema: str,
    ) -> MigrationPlan:
        transformed = transformer.transform(raw_tables)
        transformed_views = transformer.transform_views(raw_views)

        all_warnings: list[MigrationWarning] = []
        for table in transformed:
            all_warnings.extend(table.warnings)
            for col in table.columns:
                all_warnings.extend(col.warnings)
        for view in transformed_views:
            all_warnings.extend(view.warnings)

        return MigrationPlan(
            tables=transformed,
            warnings=all_warnings,
            source_schema=schema,
            source_engine=self._source_engine,
            target_engine=self._target_engine,
            emitter=emitter,
            views=transformed_views,
        )


__all__: list[str] = [
    "MigrationPlanner",
    "NumberFallback",
]
