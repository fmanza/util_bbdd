"""Modelos IR (Intermediate Representation) para migración DDL entre motores."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..emitters.base import DDLEmitter

WarningSeverity = Literal["INFO", "WARNING", "ERROR"]
WarningCategory = Literal[
    "TYPE",
    "DEFAULT",
    "IDENTIFIER",
    "IDENTIFIER_CASE_COLLISION",
    "AUTO_INCREMENT",
    "FOREIGN_KEY",
    "INDEX",
    "VIEW",
    "ROUTINE",
    "COMMENT",
    "TABLE",
]
"""Qué clase de aviso es (0.21.0; antes iba mezclado con el tipo en ``oracle_type``).

- ``TYPE``: conversión del tipo de una columna (``source_type`` = tipo en el origen).
- ``DEFAULT``: valor por defecto sin traducción fiable (``source_type`` = tipo de la columna).
- ``IDENTIFIER``: nombre truncado al límite del destino.
- ``IDENTIFIER_CASE_COLLISION``: nombres que solo difieren en mayúsculas.
- ``AUTO_INCREMENT``: autoincrementales, secuencias e identidades (``source_type`` = tipo de la PK si aplica).
- ``FOREIGN_KEY``: claves foráneas (acciones no soportadas, FK aplazadas).
- ``INDEX``: índices (p. ej. renombrados por colisión de nombre en el schema).
- ``VIEW``: vistas (reescritura, construcciones sin traducción, definición no disponible).
- ``ROUTINE``: procedimientos, funciones y packages.
- ``COMMENT``: comentario de tabla o columna recortado al límite del destino, o de vista que el destino no admite.
- ``TABLE``: problemas de la tabla en conjunto (p. ej. sin columnas activas).
"""

WarningCode = Literal[
    "COLUMN_OMITTED",
    "AUTO_INCREMENT_NO_SEQUENCE",
    "FK_DEFERRED",
    "FK_ON_UPDATE_IGNORED",
    "VIEW_PASSTHROUGH",
    "VIEW_NOT_REWRITTEN",
    "VIEW_REWRITTEN",
    "VIEW_ORACLE_SEMANTICS",
    "VIEW_HIERARCHY",
    "VIEW_EXTERNAL_REFERENCE",
    "VIEW_HEADER_COLUMNS",
    "VIEW_DEFINITION_UNAVAILABLE",
    "VIEW_MANUAL_REVIEW",
    "VIEW_LEXICAL_REWRITE",
    "VIEW_USER_PSEUDOCOLUMN",
    "ROUTINE_NO_BODY",
    "ROUTINE_PACKAGE_MEMBER",
    "COMMENT_TRUNCATED",
    "VIEW_COMMENT_UNSUPPORTED",
    "TABLE_NO_COLUMNS",
]
"""Subtipo estable de un aviso dentro de su categoría (0.22.0, E1).

Para filtrar avisos en código: ``target_type`` guarda un tipo, un nombre **o** una etiqueta legible según el caso
(``"VIEW (reescrita)"``, ``"(no body)"``…), y esas etiquetas pueden cambiar de texto. Los avisos de conversión de tipos
e identificadores no llevan código: su ``target_type`` es el tipo o el nombre en el destino.

- ``COLUMN_OMITTED`` (``TYPE``): columna sin equivalente en el destino (``ROWID``), omitida.
- ``AUTO_INCREMENT_NO_SEQUENCE`` (``AUTO_INCREMENT``): Oracle destino sin ``SEQUENCE``/``TRIGGER`` para el autoincremental.
- ``FK_DEFERRED`` (``FOREIGN_KEY``): FK de un ciclo, añadida con ``ALTER TABLE`` al final.
- ``FK_ON_UPDATE_IGNORED`` (``FOREIGN_KEY``): ``ON UPDATE`` sin equivalente en Oracle.
- ``VIEW_PASSTHROUGH``: vista copiada sin reescribir por la estrategia ``"passthrough"`` (o sin sqlglot).
- ``VIEW_NOT_REWRITTEN``: vista sin traducción fiable, copiada sin reescribir (el motivo va en ``message``).
- ``VIEW_REWRITTEN``: vista reescrita con sqlglot (``INFO``, revisar la semántica).
- ``VIEW_ORACLE_SEMANTICS``: cadena vacía y ``NULL`` en Oracle.
- ``VIEW_HIERARCHY``: ``CONNECT BY`` convertido en CTE recursiva.
- ``VIEW_EXTERNAL_REFERENCE``: la vista usa objetos fuera del schema migrado.
- ``VIEW_HEADER_COLUMNS``: vista de SQL Server con columnas en la cabecera.
- ``VIEW_DEFINITION_UNAVAILABLE``: definición no disponible (``WITH ENCRYPTION`` o sin permiso).
- ``VIEW_MANUAL_REVIEW``: construcción de Oracle que la reescritura léxica no traduce.
- ``VIEW_LEXICAL_REWRITE``: sustitución léxica de una función de Oracle (``target_type`` = sustituta).
- ``VIEW_USER_PSEUDOCOLUMN``: pseudocolumna ``USER`` sustituida (``target_type`` = función destino).
- ``ROUTINE_NO_BODY``: rutina sin cuerpo disponible.
- ``ROUTINE_PACKAGE_MEMBER``: miembro de un PACKAGE de Oracle.
- ``COMMENT_TRUNCATED`` (``COMMENT``): comentario recortado al límite del destino.
- ``VIEW_COMMENT_UNSUPPORTED`` (``COMMENT``): comentario de vista que MySQL/MariaDB no guardan.
- ``TABLE_NO_COLUMNS`` (``TABLE``, ``ERROR``): tabla sin columnas activas.
"""


@dataclass(frozen=True, slots=True)
class MigrationWarning:
    """Aviso generado durante la planificación o la emisión del DDL.

    Attributes:
        table: Tabla, vista o rutina afectada.
        column: Columna afectada, si la hay.
        category: Clase de aviso (:data:`WarningCategory`).
        target_type: Tipo, nombre o etiqueta en el destino (depende de la categoría): el tipo destino en ``TYPE``, el
            nombre nuevo en ``IDENTIFIER``, una etiqueta legible en el resto. Para filtrar, usar ``category`` y ``code``.
        message: Explicación legible.
        severity: ``INFO``, ``WARNING`` o ``ERROR`` (un ``ERROR`` impide ``MigrationPlan.execute``).
        source_type: Tipo de datos en el origen, cuando el aviso trata de uno (``TYPE``, ``DEFAULT``, ``AUTO_INCREMENT``).
        proposals: Alternativas propuestas.
        code: Subtipo estable del aviso (:data:`WarningCode`, 0.22.0); ``None`` en los de tipos e identificadores.
    """

    table: str
    column: str | None
    category: WarningCategory
    target_type: str
    message: str
    severity: WarningSeverity = "WARNING"
    source_type: str | None = None
    proposals: tuple[str, ...] = ()
    code: WarningCode | None = None


@dataclass(slots=True)
class CanonicalColumn:
    """Representación canónica de una columna durante la migración.

    ``source_type`` es el tipo de la columna en el motor origen (hasta 0.20.0 se llamaba ``oracle_type``).
    """

    name: str
    original_name: str
    source_type: str
    target_type: str
    nullable: bool
    default: str | None
    comment: str
    ordinal: int
    auto_increment: bool = False
    is_primary_key: bool = False
    char_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    warnings: list[MigrationWarning] = field(default_factory=list)
    ddl_comment: str | None = None
    omit: bool = False


@dataclass(slots=True)
class CanonicalIndex:
    """Representación canónica de un índice."""

    name: str
    original_name: str
    columns: list[str]
    unique: bool


@dataclass(slots=True)
class CanonicalFK:
    """Representación canónica de una foreign key."""

    name: str
    original_name: str
    columns: list[str]
    ref_table: str
    ref_columns: list[str]
    on_delete: str
    on_update: str
    is_external: bool = False


@dataclass(slots=True)
class CanonicalTable:
    """Representación canónica de una tabla durante la migración."""

    name: str
    original_name: str
    schema: str
    columns: list[CanonicalColumn]
    primary_key: list[str]
    indexes: list[CanonicalIndex]
    foreign_keys: list[CanonicalFK]
    comment: str
    warnings: list[MigrationWarning]


@dataclass(slots=True)
class CanonicalView:
    """Representación canónica de una vista durante la migración.

    El campo ``query`` contiene el SELECT reescrito con sustituciones
    best-effort (SYSDATE, NVL, hints Oracle, FROM DUAL, prefijos de schema).
    Constructs que requieren revisión manual generan MigrationWarning con
    severity="WARNING" y se dejan sin modificar en el SQL.
    """

    name: str
    original_name: str
    schema: str
    query: str
    columns: list[str]
    comment: str
    warnings: list[MigrationWarning]


@dataclass(slots=True)
class CanonicalRoutine:
    """Representación canónica de una rutina (PROCEDURE/FUNCTION) durante la migración.

    El campo ``body`` contiene el cuerpo DDL verbatim del motor origen.
    Constructs que requieren revisión manual generan MigrationWarning con
    severity="WARNING". Si body no está disponible se emite un stub.
    Los miembros de PACKAGE Oracle se marcan con ``is_package_member=True``;
    sólo se emite un comentario DDL para ellos.
    """

    name: str
    original_name: str
    schema: str
    routine_type: str
    body: str
    return_type: str
    comment: str
    warnings: list[MigrationWarning]
    is_package_member: bool = False
    package_name: str | None = None


@dataclass
class MigrationPlan:
    """Plan de migración ejecutable: contiene tablas transformadas, warnings y configuración."""

    tables: list[CanonicalTable]
    warnings: list[MigrationWarning]
    source_schema: str
    source_engine: str
    target_engine: str
    emitter: DDLEmitter = field(repr=False)
    views: list[CanonicalView] = field(default_factory=list)
    routines: list[CanonicalRoutine] = field(default_factory=list)

    def emit_ddl(self) -> str:
        """Genera el script DDL completo para el motor destino.

        Incluye tablas (con índices y FKs), vistas y rutinas. Algunos emisores
        descubren warnings solo durante la emisión (p.ej. un DEFAULT con forma de
        función no reconocida, MIG-03); ``self.warnings`` se actualiza con ellos
        tras generar el DDL.
        """
        ddl = self.emitter.emit(self.tables, self.views, self.routines)
        self._sync_warnings_from_tables()
        return ddl

    def emit_statements(self) -> list[str]:
        """Genera la lista de sentencias DDL individuales (sin ';').

        Incluye tablas (con índices y FKs), vistas y rutinas. Algunos emisores
        descubren warnings solo durante la emisión (p.ej. un DEFAULT con forma de
        función no reconocida, MIG-03); ``self.warnings`` se actualiza con ellos
        tras generar las sentencias.
        """
        statements = self.emitter.emit_statements(self.tables, self.views, self.routines)
        self._sync_warnings_from_tables()
        return statements

    def _sync_warnings_from_tables(self) -> None:
        """Incorpora a ``self.warnings`` los warnings nuevos que la emisión haya
        añadido a ``col.warnings``/``table.warnings`` (generados en fase de
        emisión, no de transformación, por lo que no estaban en el plan original).
        También los de ``view.warnings`` (comentarios de vistas, E2 0.22.0).
        Idempotente: no duplica warnings ya presentes.
        """
        for view in self.views:
            for warning in view.warnings:
                if warning not in self.warnings:
                    self.warnings.append(warning)
        for table in self.tables:
            for warning in table.warnings:
                if warning not in self.warnings:
                    self.warnings.append(warning)
            for col in table.columns:
                for warning in col.warnings:
                    if warning not in self.warnings:
                        self.warnings.append(warning)

    def execute(self, target_connection: Any) -> None:
        """Ejecuta el DDL generado contra el motor destino.

        Las sentencias se aplican una a una, con ``commit`` tras cada una, por **una sola** conexión (el
        ``SET search_path`` de ``pg_schema`` afecta a las siguientes). Las sentencias que solo contienen comentarios
        (rutinas sin cuerpo, miembros de PACKAGE) no se envían.

        Args:
            target_connection: ``SyncDatabaseManager`` del motor destino (o un ``Engine`` de SQLAlchemy). Un objeto
                que solo ofrezca ``execute_custom_one(sql, params)`` se usa sentencia a sentencia con ese método.

        Raises:
            ValueError: Si el plan tiene uno o más warnings de severidad ``ERROR``
                (``self.error_count > 0``). No hay flag de override: resuelve los
                errores del plan (revisa ``self.warnings``) antes de ejecutar, o usa
                ``emit_ddl()``/``emit_statements()`` para inspeccionar el DDL sin ejecutarlo.
            DatabaseOperationError: Si una sentencia falla; indica su posición y su primera línea. Las anteriores
                quedan aplicadas.
        """
        if self.error_count > 0:
            error_messages = "; ".join(w.message for w in self.warnings if w.severity == "ERROR")
            raise ValueError(
                f"No se puede ejecutar el plan de migración: {self.error_count} warning(s) de "
                f"severidad ERROR sin resolver ({error_messages}). Revisa `plan.warnings` antes de "
                "ejecutar, o usa `emit_ddl()`/`emit_statements()` para inspeccionar el DDL generado "
                "sin ejecutarlo."
            )
        statements = [stmt.strip() for stmt in self.emit_statements() if _has_sql(stmt)]
        if hasattr(target_connection, "get_sqlalchemy_engine") or hasattr(target_connection, "raw_connection"):
            _execute_statements(target_connection, statements, self.target_engine)
            return
        for stmt in statements:
            target_connection.execute_custom_one(stmt, {})

    def validate_views(self, target_connection: Any = None, *, include_tables: bool = True) -> list[Any]:
        """Valida las vistas del plan en el destino sin dejar cambios.

        En PostgreSQL y SQL Server (DDL transaccional) crea las tablas del plan (si ``include_tables``) y cada vista en
        una transacción que se deshace. En MySQL, MariaDB y Oracle (el DDL hace commit implícito) solo comprueba la
        sintaxis con sqlglot; sin sqlglot no valida.

        Args:
            target_connection: ``SyncDatabaseManager`` (o Engine de SQLAlchemy) del destino; obligatorio con destino
                PostgreSQL o SQL Server.
            include_tables: Crear también las tablas del plan en la transacción (validar antes de ``execute``).

        Returns:
            list[ViewValidationResult]: Una entrada por vista con SQL (``view``, ``valid``, ``method``, ``error``).
        """
        from ..views.validation import validate_plan_views

        return list(validate_plan_views(self, target_connection, include_tables=include_tables))

    def suggested_filename(self, suffix: str = "", ext: str = "sql") -> str:
        """Nombre de fichero canónico que incorpora schema, motor origen y motor destino.

        Args:
            suffix: Sufijo adicional antes de la extensión (p.ej. ``"report"``).
            ext: Extensión del fichero sin punto (p.ej. ``"sql"``, ``"md"``).

        Returns:
            Nombre de fichero normalizado, p.ej. ``ventas_oracle_to_mariadb.sql``
            o ``ventas_oracle_to_mariadb_report.md``.
        """
        base = f"{self.source_schema.lower()}_{self.source_engine}_to_{self.target_engine}"
        if suffix:
            base = f"{base}_{suffix}"
        return f"{base}.{ext}"

    @property
    def error_count(self) -> int:
        """Número de warnings con severidad ERROR."""
        return sum(1 for w in self.warnings if w.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        """Número de warnings con severidad WARNING."""
        return sum(1 for w in self.warnings if w.severity == "WARNING")

    @property
    def info_count(self) -> int:
        """Número de warnings con severidad INFO."""
        return sum(1 for w in self.warnings if w.severity == "INFO")


def _has_sql(statement: str) -> bool:
    """False si la sentencia solo tiene comentarios ``--`` o espacios (Oracle la rechaza con ORA-00900)."""
    return any(line.strip() and not line.strip().startswith("--") for line in statement.splitlines())


def _execute_statements(target: Any, statements: list[str], target_engine: str) -> None:
    """Aplica ``statements`` por una conexión DB-API: cursor del driver sin parámetros y ``commit`` tras cada una.

    Sin parámetros, los drivers *pyformat* no reinterpretan los ``%`` literales del DDL (``LIKE 'a%'``). El Engine de
    ``get_sqlalchemy_engine()`` se crea para esta ejecución y se libera al terminar; uno recibido se deja abierto.
    """
    from ..._core.exceptions import DatabaseOperationError

    owned = hasattr(target, "get_sqlalchemy_engine")
    engine = target.get_sqlalchemy_engine() if owned else target
    try:
        connection = engine.raw_connection()
        try:
            cursor = connection.cursor()
            try:
                for position, statement in enumerate(statements, start=1):
                    try:
                        cursor.execute(statement)
                        connection.commit()
                    except Exception as err:
                        with suppress(Exception):  # un fallo del rollback no debe tapar el error de la sentencia
                            connection.rollback()
                        first_line = next(
                            ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")
                        )
                        raise DatabaseOperationError(
                            f"Sentencia {position}/{len(statements)} del plan falló ({first_line[:120]}): {err}",
                            "MIGRATE_EXECUTE",
                            db_type=target_engine,
                        ) from err
            finally:
                cursor.close()
        finally:
            connection.close()
    finally:
        if owned:
            engine.dispose()


__all__: list[str] = [
    "WarningSeverity",
    "WarningCategory",
    "WarningCode",
    "MigrationWarning",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    "CanonicalTable",
    "CanonicalView",
    "MigrationPlan",
]
