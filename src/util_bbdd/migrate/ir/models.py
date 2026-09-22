"""Modelos IR (Intermediate Representation) para migración DDL entre motores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..emitters.base import DDLEmitter

WarningSeverity = Literal["INFO", "WARNING", "ERROR"]


@dataclass(frozen=True, slots=True)
class MigrationWarning:
    """Aviso generado durante la transformación de tipos o identificadores."""

    table: str
    column: str | None
    oracle_type: str
    target_type: str
    message: str
    severity: WarningSeverity = "WARNING"
    proposals: tuple[str, ...] = ()


@dataclass(slots=True)
class CanonicalColumn:
    """Representación canónica de una columna durante la migración."""

    name: str
    original_name: str
    oracle_type: str
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

        Incluye tablas (con índices y FKs), vistas y rutinas.
        """
        return self.emitter.emit(self.tables, self.views, self.routines)

    def emit_statements(self) -> list[str]:
        """Genera la lista de sentencias DDL individuales (sin ';').

        Incluye tablas (con índices y FKs), vistas y rutinas.
        """
        return self.emitter.emit_statements(self.tables, self.views, self.routines)

    def execute(self, target_connection: Any) -> None:
        """Ejecuta el DDL generado contra el motor destino.

        Args:
            target_connection: SyncDatabaseManager del motor destino.

        Raises:
            ValueError: Si el plan tiene uno o más warnings de severidad ``ERROR``
                (``self.error_count > 0``). No hay flag de override: resuelve los
                errores del plan (revisa ``self.warnings``) antes de ejecutar, o usa
                ``emit_ddl()``/``emit_statements()`` para inspeccionar el DDL sin ejecutarlo.
        """
        if self.error_count > 0:
            error_messages = "; ".join(w.message for w in self.warnings if w.severity == "ERROR")
            raise ValueError(
                f"No se puede ejecutar el plan de migración: {self.error_count} warning(s) de "
                f"severidad ERROR sin resolver ({error_messages}). Revisa `plan.warnings` antes de "
                "ejecutar, o usa `emit_ddl()`/`emit_statements()` para inspeccionar el DDL generado "
                "sin ejecutarlo."
            )
        for stmt in self.emit_statements():
            stmt_clean = stmt.strip()
            if stmt_clean:
                target_connection.execute_custom_one(stmt_clean, {})

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


__all__: list[str] = [
    "WarningSeverity",
    "MigrationWarning",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    "CanonicalTable",
    "CanonicalView",
    "MigrationPlan",
]
