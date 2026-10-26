"""Orquestador principal del módulo migrate.

MigrationPlanner coordina extractor → transformer → emitter para producir
un MigrationPlan ejecutable o exportable como script SQL.
"""

from __future__ import annotations

from typing import Any, Literal

from ._compat.default_normalizer import normalize_default
from ._compat.identifier_rules import check_identifier, find_case_insensitive_collisions
from .charset import (
    DEFAULT_CHARSET,
    DEFAULT_COLLATION,
    DEFAULT_COLLATION_MYSQL,
    validate_charset,
    validate_charset_collation_pair,
    validate_collation,
    validate_mysql_collation,
    validate_storage_engine,
)
from .emitters.mariadb import MariaDBDDLEmitter
from .emitters.mysql import MySQLDDLEmitter
from .emitters.oracle import _VALID_ORACLE_IDENTITY_MODES, OracleDDLEmitter, OracleIdentityMode
from .emitters.postgresql import PostgreSQLDDLEmitter
from .emitters.sqlserver import SQLServerDDLEmitter
from .extractors.mariadb import MariaDBSchemaExtractor
from .extractors.mysql import MariaDBFullTypeSchemaExtractor, MySQLSchemaExtractor
from .extractors.oracle import OracleSchemaExtractor
from .extractors.postgresql import PostgreSQLSchemaExtractor
from .extractors.sqlserver import SQLServerSchemaExtractor
from .ir.models import CanonicalTable, CanonicalView, MigrationPlan, MigrationWarning
from .transformers.mariadb_to_mysql import MariaDBToMySQLTransformer
from .transformers.mariadb_to_oracle import MariaDBToOracleTransformer
from .transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from .transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from .transformers.mysql_to_mariadb import MySQLToMariaDBTransformer
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer
from .transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from .transformers.oracle_to_sqlserver import OracleToSQLServerTransformer
from .transformers.postgresql_to_mariadb import PostgreSQLToMariaDBTransformer
from .transformers.postgresql_to_oracle import PostgreSQLToOracleTransformer
from .transformers.postgresql_to_sqlserver import PostgreSQLToSQLServerTransformer
from .transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from .transformers.sqlserver_to_oracle import SQLServerToOracleTransformer
from .transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer
from .views import ViewStrategy, resolve_view_strategy

NumberFallback = Literal["DOUBLE", "DECIMAL(38,10)", "DECIMAL(18,4)"]

_SUPPORTED_SOURCE: frozenset[str] = frozenset({"oracle", "mariadb", "mysql", "sqlserver", "postgresql"})
_SUPPORTED_TARGET: frozenset[str] = frozenset({"mariadb", "mysql", "sqlserver", "postgresql", "oracle"})
# Destinos de la familia MySQL/MariaDB: comparten los transformers X → MariaDB; cada uno con su emitter.
_MYSQL_FAMILY_TARGETS: frozenset[str] = frozenset({"mariadb", "mysql"})

# Remapeo de NumberFallback inválido para SQL Server
_SS_FALLBACK_REMAP: dict[str, str] = {"DOUBLE": "FLOAT"}

# Remapeo de NumberFallback para PostgreSQL (DOUBLE → DOUBLE PRECISION)
_PG_FALLBACK_REMAP: dict[str, str] = {"DOUBLE": "DOUBLE PRECISION"}


class MigrationPlanner:
    """Orquestador de migración DDL entre motores.

    Args:
        source_engine: Motor origen ("oracle", "mariadb", "mysql", "sqlserver" o "postgresql").
        target_engine: Motor destino ("mariadb", "mysql", "sqlserver", "postgresql" o "oracle").
        charset: CHARACTER SET (solo aplica cuando target_engine es "mariadb" o "mysql").
        collation: COLLATE (solo aplica cuando target_engine es "mariadb" o "mysql"). Con destino "mysql", el
            valor por defecto (``utf8mb4_uca1400_ai_ci``, exclusivo de MariaDB) se sustituye por
            ``utf8mb4_0900_ai_ci``; una collation que MySQL no tenga lanza ``ValueError``.
        number_fallback: Tipo destino para NUMBER Oracle sin precisión
            (solo cuando source_engine="oracle").
        engine: Motor de almacenamiento (solo aplica cuando target_engine es "mariadb" o "mysql").
        int_display_width: Display width para INT en MariaDB (default: 11).
            Usar 0 para emitir solo ``INT`` sin paréntesis.
            Solo aplica cuando source_engine="oracle" y target_engine="mariadb" (con destino "mysql" el
            emitter quita el ancho de los enteros, obsoleto en MySQL 8, salvo ``TINYINT(1)``).
        sql_server_collation: COLLATE a nivel columna para SQL Server (opcional).
            Si None, no se emite cláusula COLLATE (usa collation de la BD destino).
        pg_schema: Schema PostgreSQL (opcional). Si se indica, emite
            ``SET search_path = schema;`` al inicio del script DDL.
        view_strategy: Cómo se migra el SQL de las vistas. ``"auto"`` (por defecto) lo reescribe al dialecto destino
            con sqlglot si está instalado (extra ``util_bbdd[migrate]``) y, si no, lo copia sin reescribir;
            ``"transpile"`` exige sqlglot; ``"passthrough"`` lo copia sin reescribir (comportamiento hasta 0.19.0).
            Una vista que no se puede reescribir de forma fiable se copia sin reescribir, con aviso.

    Raises:
        ValueError: Si source_engine o target_engine no están soportados,
                    si source_engine == target_engine, si charset/collation
                    no son válidos para MariaDB, si engine no es un nombre de motor de
                    almacenamiento válido (destino MariaDB/MySQL) o si view_strategy no es válida.
        ImportError: Si view_strategy="transpile" y sqlglot no está instalado.
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
        oracle_identity_mode: OracleIdentityMode = "sequence_trigger",
        view_strategy: ViewStrategy = "auto",
    ) -> None:
        src = source_engine.strip().lower()
        tgt = target_engine.strip().lower()

        if src not in _SUPPORTED_SOURCE:
            raise ValueError(f"Motor origen '{source_engine}' no soportado. Soportados: {sorted(_SUPPORTED_SOURCE)}")
        if tgt not in _SUPPORTED_TARGET:
            raise ValueError(f"Motor destino '{target_engine}' no soportado. Soportados: {sorted(_SUPPORTED_TARGET)}")
        if src == tgt:
            raise ValueError(f"Motor origen y destino son el mismo ('{src}'). La migración requiere motores distintos.")
        if oracle_identity_mode not in _VALID_ORACLE_IDENTITY_MODES:
            raise ValueError(
                f"oracle_identity_mode '{oracle_identity_mode}' no es válido. "
                f"Valores aceptados: {sorted(_VALID_ORACLE_IDENTITY_MODES)}"
            )

        self._source_engine = src
        self._target_engine = tgt
        self._number_fallback = number_fallback
        self._engine = validate_storage_engine(engine) if tgt in _MYSQL_FAMILY_TARGETS else engine
        self._int_display_width = int_display_width
        self._sql_server_collation = sql_server_collation
        self._pg_schema = pg_schema
        self._oracle_identity_mode: OracleIdentityMode = oracle_identity_mode
        self._view_strategy = resolve_view_strategy(view_strategy)

        if tgt == "mariadb":
            self._charset = validate_charset(charset)
            self._collation = validate_collation(collation)
            validate_charset_collation_pair(self._charset, self._collation)
        elif tgt == "mysql":
            self._charset = validate_charset(charset)
            self._collation = validate_mysql_collation(
                DEFAULT_COLLATION_MYSQL if collation == DEFAULT_COLLATION else collation
            )
            validate_charset_collation_pair(self._charset, self._collation)
        else:
            self._charset = charset
            self._collation = collation

    @staticmethod
    def supported_sources() -> tuple[str, ...]:
        """Motores que ``source_engine`` admite, en orden alfabético.

        Cualquier par de un origen y un destino distintos está soportado (el mismo motor en los dos lados lanza
        ``ValueError``).

        Returns:
            Nombres en minúsculas, como los acepta ``source_engine``.

        Example:
            >>> MigrationPlanner.supported_sources()
            ('mariadb', 'mysql', 'oracle', 'postgresql', 'sqlserver')
        """
        return tuple(sorted(_SUPPORTED_SOURCE))

    @staticmethod
    def supported_targets() -> tuple[str, ...]:
        """Motores que ``target_engine`` admite, en orden alfabético (ver :meth:`supported_sources`).

        Returns:
            Nombres en minúsculas, como los acepta ``target_engine``.

        Example:
            >>> MigrationPlanner.supported_targets()
            ('mariadb', 'mysql', 'oracle', 'postgresql', 'sqlserver')
        """
        return tuple(sorted(_SUPPORTED_TARGET))

    def plan(self, connection: Any, schema: str) -> MigrationPlan:
        """Extrae y transforma el esquema origen, produciendo un MigrationPlan.

        El catálogo se lee con la ``MetadataSource`` del origen (una consulta por tipo de objeto, ADR-003), descartando
        lo que tuviera en caché para ``schema``: el plan refleja siempre el catálogo actual.

        Args:
            connection: ``SyncDatabaseManager`` del motor origen (se usa su ``metadata_source``) o una
                ``MetadataSource`` (p. ej. ``CatalogSource.from_engine(engine)``).
            schema: Nombre del schema/owner/database a migrar.
                Para SQL Server corresponde a TABLE_SCHEMA (ej. ``'dbo'``).

        Returns:
            MigrationPlan listo para emit_ddl() o execute().
        """
        if self._source_engine == "oracle":
            return self._plan_from_oracle(connection, schema)
        elif self._source_engine == "mariadb":
            return self._plan_from_mariadb(connection, schema)
        elif self._source_engine == "mysql":
            return self._plan_from_mysql(connection, schema)
        elif self._source_engine == "sqlserver":
            return self._plan_from_sqlserver(connection, schema)
        else:  # postgresql
            return self._plan_from_postgresql(connection, schema)

    # ─── Pipelines por motor origen ───────────────────────────────────────────

    def _mysql_family_emitter(self) -> MariaDBDDLEmitter:
        """Emitter del destino de la familia MySQL/MariaDB (``MySQLDDLEmitter`` hereda de ``MariaDBDDLEmitter``)."""
        emitter_cls = MySQLDDLEmitter if self._target_engine == "mysql" else MariaDBDDLEmitter
        return emitter_cls(charset=self._charset, collation=self._collation, engine=self._engine)

    def _plan_from_oracle(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline Oracle → (MariaDB | MySQL | SQL Server | PostgreSQL)."""
        extractor = OracleSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)
        raw_routines = extractor.extract_routines(schema)

        if self._target_engine in _MYSQL_FAMILY_TARGETS:
            transformer: Any = OracleToMariaDBTransformer(
                number_fallback=self._number_fallback,
                charset=self._charset,
                int_display_width=self._int_display_width,
            )
            emitter: Any = self._mysql_family_emitter()
        elif self._target_engine == "sqlserver":
            ss_fallback = _SS_FALLBACK_REMAP.get(self._number_fallback, self._number_fallback)
            transformer = OracleToSQLServerTransformer(number_fallback=ss_fallback)
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)
        else:  # postgresql
            pg_fallback = _PG_FALLBACK_REMAP.get(self._number_fallback, self._number_fallback)
            transformer = OracleToPostgreSQLTransformer(number_fallback=pg_fallback)
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, raw_routines, schema)

    def _plan_from_mariadb(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline MariaDB → (Oracle | MySQL | SQL Server | PostgreSQL)."""
        extractor = (
            MariaDBFullTypeSchemaExtractor(connection)
            if self._target_engine == "mysql"
            else MariaDBSchemaExtractor(connection)
        )
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)
        raw_routines = extractor.extract_routines(schema)

        if self._target_engine == "oracle":
            transformer: Any = MariaDBToOracleTransformer()
            emitter: Any = OracleDDLEmitter(oracle_identity_mode=self._oracle_identity_mode)
        elif self._target_engine == "mysql":
            transformer = MariaDBToMySQLTransformer()
            emitter = self._mysql_family_emitter()
        elif self._target_engine == "sqlserver":
            transformer = MariaDBToSQLServerTransformer()
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)
        else:  # postgresql
            transformer = MariaDBToPostgreSQLTransformer()
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, raw_routines, schema)

    def _plan_from_mysql(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline MySQL → (Oracle | MariaDB | SQL Server | PostgreSQL).

        MySQL comparte con MariaDB los ``DATA_TYPE`` que usan los mapas ``mariadb_to_*``: hacia Oracle, SQL Server y
        PostgreSQL se reutilizan los transformers de MariaDB. Hacia MariaDB se conserva el tipo completo
        (``COLUMN_TYPE``).
        """
        extractor = MySQLSchemaExtractor(connection, full_column_types=self._target_engine == "mariadb")
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)
        raw_routines = extractor.extract_routines(schema)

        if self._target_engine == "oracle":
            transformer: Any = MariaDBToOracleTransformer()
            emitter: Any = OracleDDLEmitter(oracle_identity_mode=self._oracle_identity_mode)
        elif self._target_engine == "mariadb":
            transformer = MySQLToMariaDBTransformer()
            emitter = self._mysql_family_emitter()
        elif self._target_engine == "sqlserver":
            transformer = MariaDBToSQLServerTransformer()
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)
        else:  # postgresql
            transformer = MariaDBToPostgreSQLTransformer()
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, raw_routines, schema)

    def _plan_from_sqlserver(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline SQL Server → (Oracle | MariaDB | MySQL | PostgreSQL)."""
        extractor = SQLServerSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)
        raw_routines = extractor.extract_routines(schema)

        if self._target_engine == "oracle":
            transformer: Any = SQLServerToOracleTransformer()
            emitter: Any = OracleDDLEmitter(oracle_identity_mode=self._oracle_identity_mode)
        elif self._target_engine in _MYSQL_FAMILY_TARGETS:
            transformer = SQLServerToMariaDBTransformer()
            emitter = self._mysql_family_emitter()
        else:  # postgresql
            transformer = SQLServerToPostgreSQLTransformer()
            emitter = PostgreSQLDDLEmitter(pg_schema=self._pg_schema)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, raw_routines, schema)

    def _plan_from_postgresql(self, connection: Any, schema: str) -> MigrationPlan:
        """Pipeline PostgreSQL → (Oracle | MariaDB | MySQL | SQL Server)."""
        extractor = PostgreSQLSchemaExtractor(connection)
        raw_tables = extractor.extract(schema)
        raw_views = extractor.extract_views(schema)
        raw_routines = extractor.extract_routines(schema)

        if self._target_engine == "oracle":
            transformer: Any = PostgreSQLToOracleTransformer()
            emitter: Any = OracleDDLEmitter(oracle_identity_mode=self._oracle_identity_mode)
        elif self._target_engine in _MYSQL_FAMILY_TARGETS:
            transformer = PostgreSQLToMariaDBTransformer()
            emitter = self._mysql_family_emitter()
        else:  # sqlserver
            transformer = PostgreSQLToSQLServerTransformer()
            emitter = SQLServerDDLEmitter(collation=self._sql_server_collation)

        return self._build_plan(transformer, emitter, raw_tables, raw_views, raw_routines, schema)

    # ─── Vistas ─────────────────────────────────────────────────────────────────

    def _transform_views(
        self,
        transformer: Any,
        raw_views: list[CanonicalView],
        raw_tables: list[CanonicalTable],
        transformed: list[CanonicalTable],
        schema: str,
    ) -> list[CanonicalView]:
        """Vistas del destino: reescritas con sqlglot (``view_strategy``) o sin reescribir (transformer)."""
        if self._view_strategy == "passthrough" or not raw_views:
            return list(transformer.transform_views(raw_views))

        from .views.transpiler import ViewTranspileContext, transpile_views

        max_length: int = getattr(transformer, "MAX_IDENTIFIER_LENGTH", 128)  # sin int(): conserva ByteLimit (A6)
        views: list[CanonicalView] = []
        object_names: dict[str, str] = {}
        for raw_table, new_table in zip(raw_tables, transformed, strict=True):
            object_names[raw_table.name.lower()] = new_table.name
        for view in raw_views:
            adapted, warning = check_identifier(view.name, max_length)
            renamed = CanonicalView(
                name=adapted,
                original_name=view.original_name,
                schema=view.schema,
                query=view.query,
                columns=list(view.columns),
                comment=view.comment,
                warnings=list(view.warnings),
            )
            if warning:
                renamed.warnings.append(
                    MigrationWarning(
                        table=view.name,
                        column=None,
                        category="IDENTIFIER",
                        target_type=adapted,
                        message=warning,
                        severity="WARNING",
                    )
                )
            object_names[view.name.lower()] = adapted
            views.append(renamed)

        # Columnas: nombre origen → destino solo si es el mismo en todas las tablas (si no, se deja sin tocar).
        column_names: dict[str, str] = {}
        ambiguous: set[str] = set()
        column_types: dict[str, dict[str, str]] = {}
        integer_columns: dict[str, frozenset[str]] = {}
        for raw_table, new_table in zip(raw_tables, transformed, strict=True):
            column_types[raw_table.name] = {col.name: col.source_type for col in raw_table.columns if col.source_type}
            integer_columns[raw_table.name] = frozenset(col.name for col in raw_table.columns if col.scale == 0)
            for raw_col, new_col in zip(raw_table.columns, new_table.columns, strict=True):
                key = raw_col.name.lower()
                if column_names.get(key, new_col.name) != new_col.name:
                    ambiguous.add(key)
                column_names[key] = new_col.name
        for key in ambiguous:
            column_names.pop(key, None)

        context = ViewTranspileContext(
            source_engine=self._source_engine,
            target_engine=self._target_engine,
            source_schema=schema,
            object_names=object_names,
            column_names=column_names,
            column_types=column_types,
            integer_columns=integer_columns,
        )
        return transpile_views(views, context)

    # ─── Construcción del plan ─────────────────────────────────────────────────

    def _build_plan(
        self,
        transformer: Any,
        emitter: Any,
        raw_tables: list[Any],
        raw_views: list[Any],
        raw_routines: list[Any],
        schema: str,
    ) -> MigrationPlan:
        # H4: DEFAULT del origen en forma canónica (casts PG, paréntesis SQL Server, SYSDATE...) antes de transformar.
        for table in raw_tables:
            for column in table.columns:
                column.default = normalize_default(self._source_engine, column.default)

        transformed = transformer.transform(raw_tables)
        transformed_views = self._transform_views(transformer, raw_views, raw_tables, transformed, schema)
        transformed_routines = transformer.transform_routines(raw_routines)

        all_warnings: list[MigrationWarning] = []
        for table in transformed:
            all_warnings.extend(table.warnings)
            for col in table.columns:
                all_warnings.extend(col.warnings)
        for view in transformed_views:
            all_warnings.extend(view.warnings)
        for routine in transformed_routines:
            all_warnings.extend(routine.warnings)

        # H2 (auditoría 0.21.0): una tabla sin columnas activas daría un CREATE TABLE inválido a mitad de execute().
        for table in transformed:
            if not any(not column.omit for column in table.columns):
                all_warnings.append(
                    MigrationWarning(
                        table=table.name,
                        column=None,
                        category="TABLE",
                        target_type="(sin columnas)",
                        code="TABLE_NO_COLUMNS",
                        message=(
                            f"Tabla '{table.name}' sin columnas activas: no se extrajo ninguna o todas se omitieron por "
                            "tipos sin equivalente; su CREATE TABLE no es válido. Revisar el origen o excluir la tabla."
                        ),
                        severity="ERROR",
                    )
                )

        # CMP-02 (AUDIT_CODE 2026-09-22) + A8 (2026-09-29): nombres que solo difieren en mayúsculas.
        all_warnings.extend(_case_collision_warnings(self._target_engine, transformed, transformed_views))

        return MigrationPlan(
            tables=transformed,
            warnings=all_warnings,
            source_schema=schema,
            source_engine=self._source_engine,
            target_engine=self._target_engine,
            emitter=emitter,
            views=transformed_views,
            routines=transformed_routines,
        )


#: Destinos en los que dos columnas de una tabla que solo difieren en mayúsculas chocan SIEMPRE (Oracle las emite en
#: mayúsculas; MySQL/MariaDB no distinguen mayúsculas en nombres de columna) → ERROR. SQL Server depende de la
#: collation (por defecto no distingue) → WARNING. PostgreSQL entrecomilla con el case exacto → sin aviso.
_COLUMN_CASE_COLLISION_SEVERITY: dict[str, str] = {
    "oracle": "ERROR",
    "mariadb": "ERROR",
    "mysql": "ERROR",
    "sqlserver": "WARNING",
}
#: Tablas y vistas: Oracle las emite en mayúsculas → ERROR; SQL Server (collation) y MySQL/MariaDB
#: (``lower_case_table_names``) dependen de la configuración → WARNING; PostgreSQL → WARNING solo por referencias
#: sin comillas (comportamiento de CMP-02).
_OBJECT_CASE_COLLISION_SEVERITY: dict[str, str] = {"oracle": "ERROR"}


def _case_collision_warnings(
    target_engine: str, tables: list[CanonicalTable], views: list[CanonicalView]
) -> list[MigrationWarning]:
    """Avisos de nombres que solo difieren en mayúsculas, con la severidad del destino (A8).

    Antes solo se avisaba de tablas/vistas, siempre como WARNING y afirmando que el DDL no colisionaba; hacia Oracle
    (ORA-00955, ORA-00957), MySQL/MariaDB (1060) y SQL Server (2705, 2714) el ``CREATE TABLE`` fallaba. Con ERROR,
    ``MigrationPlan.execute`` se niega a empezar.
    """
    warnings: list[MigrationWarning] = []
    object_severity = _OBJECT_CASE_COLLISION_SEVERITY.get(target_engine, "WARNING")
    names = [table.name for table in tables] + [view.name for view in views]
    for name_a, name_b in find_case_insensitive_collisions(names):
        if object_severity == "ERROR":
            detail = f"en {target_engine} ambos se crean con el mismo nombre y el segundo CREATE falla"
        elif target_engine == "postgresql":
            detail = "el DDL migrado los entrecomilla y no colisiona, pero una referencia sin comillas los confundiría"
        else:
            detail = f"en {target_engine} colisionan si el destino no distingue mayúsculas (collation o configuración)"
        warnings.append(
            MigrationWarning(
                table=name_a,
                column=None,
                category="IDENTIFIER_CASE_COLLISION",
                target_type=name_b,
                message=f"Identificadores '{name_a}' y '{name_b}' solo difieren en mayúsculas/minúsculas: {detail}.",
                severity=object_severity,  # type: ignore[arg-type]
            )
        )
    column_severity = _COLUMN_CASE_COLLISION_SEVERITY.get(target_engine)
    if column_severity is None:
        return warnings
    for table in tables:
        for name_a, name_b in find_case_insensitive_collisions(c.name for c in table.columns if not c.omit):
            warnings.append(
                MigrationWarning(
                    table=table.name,
                    column=name_b,
                    category="IDENTIFIER_CASE_COLLISION",
                    target_type=name_a,
                    message=(
                        f"Tabla '{table.name}': las columnas '{name_a}' y '{name_b}' solo difieren en "
                        f"mayúsculas/minúsculas; en {target_engine} "
                        + (
                            "son la misma columna y el CREATE TABLE falla. Renombrar una en el origen o en el DDL."
                            if column_severity == "ERROR"
                            else "chocan si la collation no distingue mayúsculas (la de por defecto no lo hace)."
                        )
                    ),
                    severity=column_severity,  # type: ignore[arg-type]
                )
            )
    return warnings


__all__: list[str] = [
    "MigrationPlanner",
    "NumberFallback",
]
