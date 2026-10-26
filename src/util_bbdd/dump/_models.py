"""Tipos de datos públicos del módulo dump.

Separados en un módulo propio para romper la dependencia circular entre
``orchestrator`` y ``reporters``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import Engine

from util_bbdd._core.validation import OptionalPathField, PathField, validate_batch_config
from util_bbdd.audit.contracts import AuditSink
from util_bbdd.bulk._models import IndexActionResult, PKSyncResult
from util_bbdd.bulk._support.rejects import validate_isolation
from util_bbdd.bulk._support.secondary_indexes import IndexMode, resolve_index_mode

# IndexActionResult vive en bulk desde 3.2.0 (lo devuelven también maintenance_scope y ParallelBulkLoader); se reexporta.
__all__: list[str] = ["IndexActionResult", "PKSyncResult"]


@dataclass
class ConstraintResult:
    """Resultado de rehabilitar una constraint individual en el destino."""

    table_name: str
    constraint_name: str
    dialect: str
    status: Literal["enabled", "failed", "unverified"]
    error_msg: str = ""


@dataclass
class DumpConfig:
    """Configuración de un volcado de datos de esquema/BD origen a destino.

    Args:
        source_engine: Engine SQLAlchemy del esquema origen (lectura).
        target_engine: Engine SQLAlchemy del esquema destino (escritura).
            **Recomendación para MariaDB/MySQL:** crear con ``pool_pre_ping=True`` y
            ``pool_recycle=3600`` para evitar ``InterfaceError: Server has gone away``
            cuando el pool reutiliza conexiones ociosas entre tablas::

                target_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)

        source_schema: Nombre del schema origen; ``None`` usa el default del engine.
        target_schema: Nombre del schema destino; ``None`` usa el default del engine.
        tables: Tablas a volcar. ``None`` = todas las tablas del origen.
        chunk_size: Filas por chunk de lectura del origen. También es el lote de escritura
            salvo que ``write_batch_size`` indique otro (ver abajo).
            **Tablas con columnas TEXT/BLOB/JSON extensas:** el tamaño del paquete INSERT
            puede superar ``max_allowed_packet`` del servidor MariaDB/MySQL (16 MB por
            defecto), produciendo ``Lost connection to server during query``. Reduce el
            valor (p.ej. ``chunk_size=500`` o ``chunk_size=100``) o aumenta
            ``max_allowed_packet`` en el servidor (``SET GLOBAL max_allowed_packet=67108864``).
        output_dir: Directorio donde guardar el informe Excel (``str`` o ``Path``; se guarda como ``Path``).
        truncate_target: ``True`` (default) = limpiar tablas destino antes de cargar.
            Recomendado para volcados completos. ``False`` = modo append.
        bulk_audit_path: Ruta (``str`` o ``Path``) del CSV de auditoría para los inserts en destino.
            ``None`` (default) = los inserts no se registran en auditoría.
        collect_row_counts: Si ``True`` (default), se ejecutan ``COUNT(*)`` sobre origen
            y destino por tabla para obtener la volumetría real. ``False`` los omite y
            usa ``-1`` como sentinel; útil en volcados de alto volumen donde el conteo
            es costoso (Snowflake, Oracle sin estadísticas actualizadas, tablas muy grandes).
        sync_pk_sequences: Si ``True`` (default), ejecuta la Fase 6a tras la carga:
            resincroniza los contadores PK (sequence / IDENTITY / AUTO_INCREMENT) en el
            destino para que coincidan con el ``MAX`` real de cada columna. Desactivar
            con ``False`` si se gestiona la resincronización manualmente o si el motor
            destino no soporta la operación con los permisos disponibles.
        commit_every_n_chunks: Si se indica (entero ≥ 1), la carga de cada tabla commitea
            cada N lotes de ``chunk_size`` filas en lugar de en una única transacción por
            tabla, acotando el tamaño de la transacción (undo/redo log) en tablas muy
            grandes. ``None`` (default) = una transacción por tabla (atómico por tabla).
            **Advertencia:** con la cadencia activa la carga de una tabla deja de ser
            atómica; un fallo a mitad deja committeados los lotes anteriores de esa tabla
            (coherente con la semántica best-effort del volcado).
        manage_indexes: ``True`` o ``"secondary"`` (3.2.0, equivalentes): deshabilita los índices secundarios
            **no únicos** del destino antes de la carga y los reconstruye al final, acelerando los INSERT en
            tablas con muchos índices. ``False`` (default) = no se tocan los índices. Misma estrategia que
            ``BulkCrud.maintenance_scope(disable_indexes=...)`` (``bulk/_support/secondary_indexes.py``):
            mssql ``ALTER INDEX DISABLE``→``REBUILD`` (solo NONCLUSTERED), oracle ``UNUSABLE``→``REBUILD``,
            postgresql ``DROP``+recreate desde ``pg_get_indexdef``, mariadb/mysql (desde 3.2.0) InnoDB ``DROP
            INDEX`` + un ``ALTER TABLE … ADD INDEX`` por tabla y MyISAM/Aria ``DISABLE KEYS`` (el DDL de lo que se
            borra se loguea antes). Nunca toca índices que respaldan PK/UNIQUE ni, en InnoDB, los que necesita una
            FK. Efecto medido a 3,5M filas con 2 índices secundarios (tras solapar lectura y escritura): Oracle
            −14 % (reconstrucción 2,7 s), SQL Server −8 %, PostgreSQL sin ganancia; en una carga directa con
            ``bulk`` la ganancia es mayor (sesión 2026-10-18b, G0). Compensa más cuantos más índices secundarios
            tenga el destino; no se activa automáticamente.
            ``"all"`` (3.3.0): además, índices únicos y PK/UNIQUE (nunca el índice clustered ni la PK de InnoDB o de
            una IOT), con las FK que los referencian (SQL Server y Oracle las reactivan; PostgreSQL las borra y
            recrea ``NOT VALID`` + ``VALIDATE``). La unicidad **no se comprueba** durante la carga: solo para datos
            ya validados (p. ej. la carga final de un proceso con iteraciones de calidad). Exige
            ``truncate_target=True`` y no admite ``on_error="isolate"`` (los duplicados no darían error que apartar).
            Si un único no se puede reconstruir (duplicados), el resultado del índice es ``"failed"`` con las claves
            repetidas en ``error_msg``.
        validate_fks_after: MariaDB/MySQL (3.3.0; por defecto desde 3.4.0): tras reactivar ``FOREIGN_KEY_CHECKS``,
            comprueba con un ``NOT EXISTS`` por FK que no se cargaron filas huérfanas (``constraint_results`` pasa de
            ``"unverified"`` a ``"enabled"``/``"failed"``). En el resto de motores la validación ya se hace al
            reactivar. ``True`` (default desde 3.4.0); ``False`` deja la fila única ``"unverified"`` de hasta 3.3.0.
        max_parallel_tables: Número máximo de tablas a cargar concurrentemente dentro de
            un mismo nivel topológico FK (tablas mutuamente independientes). ``1`` (default)
            = carga secuencial. Valores > 1 usan un ``ThreadPoolExecutor`` con una instancia
            ``BulkCrud`` por hilo. Las tablas en ciclos FK se cargan siempre secuencialmente.
            Se degrada automáticamente (con warning) a la capacidad real del pool de
            conexiones (``pool_size + max_overflow``) de origen/destino. La auditoría sigue
            activa bajo paralelismo: las escrituras de los hilos al mismo CSV se serializan
            con un lock por ruta.
        parallel_pk_ranges: Número de rangos contiguos de PK en que particionar la carga de
            **cada** tabla con PK de una sola columna entera (``WHERE pk >= lo AND pk < hi``),
            cargados en paralelo con su propia ``BulkCrud``. ``1`` (default) = sin
            particionado. Solo aplica a tablas cuya PK es una única columna entera presente
            en las columnas comunes; el resto se cargan completas. La concurrencia total
            (``max_parallel_tables * parallel_pk_ranges``) se degrada con warning a la
            capacidad real del pool. **Requiere** que el destino no tenga triggers per-fila
            dependientes del orden de inserción. Efecto medido con 4 rangos a 3,5M filas (frente a la
            carga secuencial, que ya solapa lectura y escritura): SQL Server −37 % (recomendado);
            PostgreSQL −9 % y Oracle −2 % (poca ganancia); MySQL y MariaDB casi el doble de tiempo
            (no recomendado; se avisa en el log); SQLite se fuerza a 1 (un solo escritor).
            ``"auto"`` (v3.0.0): el número de rangos de cada tabla lo decide ``ParallelPlanner`` con el motor de
            destino y las filas del origen (el ``COUNT(*)`` de ``collect_row_counts``; sin él, la cota
            ``MAX(pk) − MIN(pk) + 1``, que sobrestima si la PK tiene huecos), con las mediciones de arriba: hoy solo
            particiona con destino SQL Server y tablas de 3,5M filas o más (4 rangos, o menos si el pool no da para
            ``max_parallel_tables`` × 4); el resto se carga entera. El motivo de cada tabla queda en el log (INFO).
        write_batch_size: Filas por lote de escritura en el destino (una sentencia ``COPY`` o
            ``executemany`` por lote). ``None`` (default): 20 000 con destino PostgreSQL (``COPY``,
            −31 % a 3,5M filas frente a 5 000) y ``chunk_size`` en el resto de motores (en SQL Server
            un lote de 20 000 fue un 81 % más lento). Con ``commit_every_n_chunks`` el default es
            siempre ``chunk_size``, para no cambiar cada cuántas filas se confirma. Un entero fija el
            lote en todos los motores. La lectura sigue siendo por ``chunk_size``; los chunks leídos
            se agrupan hasta completar el lote (+1 lote en memoria).
        on_error: Como ``RejectOptions(on_error=...)`` de ``BulkCrud``: con ``"isolate"`` las filas que el destino no admite (PK duplicada,
            NOT NULL, valor demasiado largo o fuera de precisión) se apartan a ``rejects_csv_path`` y el resto de la
            tabla se copia; la tabla queda ``success`` con ``TableDumpResult.rows_rejected``. Durante la carga las
            constraints del destino están desactivadas: las FK y los CHECK no fallan aquí (una fila huérfana se copia y
            falla al rehabilitar la constraint, como sin aislamiento). La posición (``fila``) es la de la lectura del
            origen (``SELECT`` sin ``ORDER BY``: no se repite entre volcados); con ``parallel_pk_ranges`` es la del
            rango, que va en la columna ``particion``. Fase 4, sesión 2026-10-01u.
        rejects_csv_path: CSV de rechazos común a todas las tablas (ver ``BulkCrud``). Obligatorio con
            ``on_error="isolate"``.
        max_rejects: Filas que cada tabla (o cada rango, con ``parallel_pk_ranges``) puede rechazar; la siguiente deja
            esa tabla en error y el volcado sigue. ``None`` (default): sin límite.
        bulk_audit_strict: Se pasa como ``audit_strict`` a cada ``BulkCrud`` y ``ParallelBulkLoader`` del volcado.
            ``False`` (default): un fallo al escribir el CSV de auditoría no interrumpe la carga; se registra como
            ERROR y se cuenta en ``DumpResult.audit_summary.audit_failures``. ``True``: el fallo deshace la carga de
            esa tabla (o partición) y queda como error de la tabla.
        audit_sink: Destino opcional de eventos de auditoría (:mod:`util_bbdd.audit`, p. ej. ``JsonLinesAuditSink``).
            Recibe los eventos ``operation`` de las ``BulkCrud`` del volcado y los ``partition``/``run`` de las cargas
            por rangos (con ``bulk_audit_strict`` como política de fallo de los ``operation``), el evento ``table`` de
            cada tabla al terminar su carga (4.4.0; antes, al final) y, al terminar, uno por tabla sin destino,
            constraint, índice y contador PK, y un ``run`` de cierre. Todos llevan el mismo ``run_id``
            (``DumpResult.audit_run_id``). Se puede usar sin ``bulk_audit_path``. Un fallo al escribir estos eventos se
            registra como ERROR y no cambia el resultado (el evento de una tabla que falla se reintenta al final).
            ``None`` (default): sin eventos.

    Raises:
        ValueError: Si ``chunk_size`` no es un entero ≥ 1, o si ``commit_every_n_chunks`` o ``write_batch_size`` no son
            ``None`` ni un entero ≥ 1, o si ``on_error``, ``rejects_csv_path`` y ``max_rejects`` no son una
            combinación válida (las reglas de ``BulkCrud``), o si ``output_dir``, ``bulk_audit_path`` o
            ``rejects_csv_path`` no son ``str`` ni ``Path``, o ``parallel_pk_ranges`` no es un entero ni ``"auto"``. Se
            valida al construir, antes de tocar el destino.
    """

    source_engine: Engine
    target_engine: Engine
    source_schema: str | None = None
    target_schema: str | None = None
    tables: list[str] | None = None
    chunk_size: int = 5000
    # Rutas: aceptan str o Path (v1.1.0) y se leen siempre como Path (T-09: descriptores, antes anotadas StrPath).
    output_dir: PathField = PathField(Path())
    truncate_target: bool = True
    bulk_audit_path: OptionalPathField = OptionalPathField()
    collect_row_counts: bool = True
    sync_pk_sequences: bool = True
    commit_every_n_chunks: int | None = None
    manage_indexes: bool | IndexMode = False
    max_parallel_tables: int = 1
    parallel_pk_ranges: int | Literal["auto"] = 1
    bulk_audit_strict: bool = False
    write_batch_size: int | None = None
    on_error: Literal["raise", "isolate"] = "raise"
    rejects_csv_path: OptionalPathField = OptionalPathField()
    max_rejects: int | None = None
    audit_sink: AuditSink | None = None
    validate_fks_after: bool = True

    def __post_init__(self) -> None:
        # Validar aquí y no en la primera BulkCrud: run() la crea después de vaciar el destino (truncate_target), así que
        # un chunk_size o commit_every_n_chunks inválido vaciaba las tablas y luego fallaba; con chunk_size=0 y
        # write_batch_size no se leía nada y la tabla quedaba vacía con estado "success".
        # Refactor v0.30.1: usa validador centralizado validate_batch_config().
        validate_batch_config(self.chunk_size, self.commit_every_n_chunks, self.write_batch_size)
        # v1.1.0: con output_dir como str, run() cargaba los datos y fallaba al escribir el informe sin devolver el
        # DumpResult; bulk_audit_path como str fallaba antes de cargar. Las rutas ya llegan aquí como Path: las
        # normalizan y validan sus descriptores (PathField/OptionalPathField) al asignarse en __init__.
        validate_isolation(self.on_error, self.rejects_csv_path, self.max_rejects)
        if resolve_index_mode(self.manage_indexes, "manage_indexes") == "all":
            # AUDIT_PLAN F2/F3 (sesión 2026-10-18b): sin unicidad durante la carga, los duplicados contra filas ya
            # existentes o los que "isolate" debería apartar solo aparecerían al reconstruir.
            if not self.truncate_target:
                raise ValueError("manage_indexes='all' exige truncate_target=True (el destino debe empezar vacío).")
            if self.on_error == "isolate":
                raise ValueError("manage_indexes='all' no admite on_error='isolate': los duplicados no darían error.")
        ranges = self.parallel_pk_ranges
        if ranges != "auto" and (isinstance(ranges, bool) or not isinstance(ranges, int)):
            raise ValueError(f"parallel_pk_ranges debe ser un entero o 'auto', recibido: {ranges!r}")


@dataclass
class TableDumpResult:
    """Resultado del volcado de una tabla individual.

    ``rows_rejected``: filas apartadas al CSV de rechazos con ``DumpConfig(on_error="isolate")``; la tabla puede ser
    ``success`` con filas rechazadas. Con estado ``error`` (p. ej. ``max_rejects`` superado) la carga de la tabla se
    deshizo y no se copió nada, pero los rechazos escritos siguen en el CSV y aquí (B-1, audit-code 2026-10-01).
    """

    table_name: str
    source_rows: int
    target_rows_before: int
    target_rows_after: int
    status: Literal["success", "missing_target", "skipped", "error"]
    skipped_columns: list[str]
    load_order_position: int
    in_cycle: bool = False
    error_msg: str = ""
    rows_rejected: int = 0


@dataclass
class DumpAuditSummary:
    """Métricas de auditoría de inserts extraídas del CSV de ``bulk.audit`` al finalizar el volcado.

    Solo se popula cuando ``DumpConfig.bulk_audit_path`` está configurado y el CSV
    contiene entradas del rango temporal del volcado, o cuando hubo fallos al escribirlo
    (``audit_failures > 0``; entonces las métricas del CSV pueden ser 0).

    Attributes:
        total_operaciones: Número de lotes INSERT registrados en auditoría.
        total_filas: Suma de filas insertadas según el CSV de auditoría.
        tiempo_total_seg: Tiempo total de inserción (segundos) según auditoría.
        tiempo_promedio_seg: Tiempo medio por lote INSERT.
        tablas_auditadas: Número de tablas distintas con al menos un INSERT registrado.
        tabla_mas_activa: Tabla con mayor número de lotes INSERT (``None`` si no hay datos).
        audit_path: Ruta del CSV de auditoría consultado.
        audit_failures: Registros de auditoría que no se pudieron escribir en el CSV durante el volcado (con
            ``DumpConfig.bulk_audit_strict=False``). Si es mayor que 0, las métricas anteriores están incompletas.
        audited_rows: Filas que **este volcado** escribió en el CSV, contadas por las ``BulkCrud`` y no leídas del
            fichero. Puede diferir de ``total_filas``, que sale del CSV filtrado por hora e incluye lo que otros procesos
            escriban en el mismo fichero durante el volcado (en ese caso se registra un WARNING).
        unaudited_committed_rows: Filas confirmadas en destino por commits periódicos (``commit_every_n_chunks``) que
            no constan en el CSV porque la carga de su tabla falló a mitad de una operación.
        audit_uncommitted_records: Registros escritos en el CSV antes de un commit que falló (con
            ``bulk_audit_strict=True``): el CSV los tiene y el destino no. ``total_filas`` los incluye.

    Si alguno de ``audit_failures``, ``unaudited_committed_rows`` o ``audit_uncommitted_records`` es mayor que 0, el
    resumen se devuelve aunque el CSV no tenga entradas del volcado.
    """

    total_operaciones: int
    total_filas: int
    tiempo_total_seg: float
    tiempo_promedio_seg: float
    tablas_auditadas: int
    tabla_mas_activa: str | None
    audit_path: Path
    audit_failures: int = 0
    audited_rows: int = 0
    unaudited_committed_rows: int = 0
    audit_uncommitted_records: int = 0


DumpWarningCode = Literal[
    "MISSING_TARGET",
    "NO_COMMON_COLUMNS",
    "SKIPPED_COLUMNS",
    "REQUIRED_TARGET_COLUMNS",
    "OUTSIDE_REFERENCES",
    "FK_CYCLE",
    "CONSTRAINTS_NOT_MANAGED",
    "SQLITE_SOURCE",
]
"""Códigos estables de :class:`DumpPlanWarning` (4.4.0):

- ``MISSING_TARGET``: la tabla no existe en el destino; no se carga (``status="missing_target"`` en ``run()``).
- ``NO_COMMON_COLUMNS``: ninguna columna del origen existe en el destino; no se carga (``status="skipped"``).
- ``SKIPPED_COLUMNS``: columnas del origen que el destino no tiene; no se copian.
- ``REQUIRED_TARGET_COLUMNS``: columnas del destino sin nulos ni valor por defecto que el origen no tiene; la carga de
  la tabla fallará.
- ``OUTSIDE_REFERENCES``: la tabla tiene FK hacia tablas que no se vuelcan; sus filas deben existir ya en el destino.
- ``FK_CYCLE``: tablas con FK circular; se cargan al final, en el orden del origen.
- ``CONSTRAINTS_NOT_MANAGED``: el destino no admite desactivar constraints; se carga con ellas activas.
- ``SQLITE_SOURCE``: origen SQLite (sin tipos de columna); ver ``DumpOrchestrator``.
"""


@dataclass(frozen=True)
class DumpPlanWarning:
    """Aviso de :meth:`DumpOrchestrator.plan` (4.4.0).

    Attributes:
        code: Código estable (:data:`DumpWarningCode`), para que quien lo muestre no dependa del texto.
        message: Explicación en español.
        table: Tabla de origen a la que se refiere, o ``None`` si es general.
    """

    code: DumpWarningCode
    message: str
    table: str | None = None


@dataclass(frozen=True)
class DumpPlanTable:
    """Una tabla de :class:`DumpPlan`, en el orden de carga (4.4.0).

    Attributes:
        table_name: Nombre en el origen (``TableDumpResult.table_name``).
        target_table: Nombre en el destino (puede diferir en mayúsculas), o ``None`` si no existe allí.
        load_order_position: Posición de carga, como ``TableDumpResult.load_order_position`` (``-1`` sin destino).
        in_cycle: ``True`` si está en un ciclo de FK.
        skipped_columns: Columnas del origen que el destino no tiene (no se copian).
        required_target_columns: Columnas del destino sin nulos ni valor por defecto que el origen no tiene.
        outside_references: Tablas que no se vuelcan y a las que apunta por FK.
    """

    table_name: str
    target_table: str | None
    load_order_position: int
    in_cycle: bool = False
    skipped_columns: tuple[str, ...] = ()
    required_target_columns: tuple[str, ...] = ()
    outside_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class DumpPlan:
    """Vista previa de un volcado: lo que haría ``run()`` sin escribir nada (``DumpOrchestrator.plan()``, 4.4.0).

    Attributes:
        load_order: Orden de carga, el mismo que daría ``DumpResult.load_order`` con el mismo catálogo.
        cycles: Grupos de tablas con FK circular (``DumpResult.cycles_detected``).
        missing_target: Tablas del origen que no existen en el destino.
        tables: Una entrada por tabla, en el orden de ``load_order``.
        warnings: Avisos por tabla y generales.
        constraints_managed: ``True`` si ``run()`` desactiva las constraints del destino durante la carga.
    """

    load_order: list[str]
    cycles: list[list[str]]
    missing_target: list[str]
    tables: tuple[DumpPlanTable, ...]
    warnings: tuple[DumpPlanWarning, ...]
    constraints_managed: bool


@dataclass
class DumpResult:
    """Resultado completo de un volcado.

    Attributes:
        table_results: Resultado por tabla volcada (o intentada).
        constraint_results: Resultado por constraint al rehabilitar (per-tabla/constraint).
        load_order: Orden topológico de carga aplicado.
        cycles_detected: Grupos de tablas con FK circular (cargadas al final).
        report: Ruta del informe Excel generado (3 hojas fijas y hasta 3 opcionales; ver ``DumpReporter``).
        audit_summary: Métricas de auditoría extraídas de ``bulk.audit`` al finalizar.
            ``None`` cuando ``DumpConfig.bulk_audit_path`` no está configurado o el CSV
            no contiene entradas del volcado actual.
        pk_sync_results: Resultado por columna PK sincronizada en la Fase 6a.
            ``None`` cuando ``DumpConfig.sync_pk_sequences=False`` o el motor destino
            no tiene tablas con contadores PK.
        index_results: Resultado por índice gestionado (deshabilitado y reconstruido).
            ``None`` cuando ``DumpConfig.manage_indexes=False``.
        audit_run_id: ``run_id`` de todos los eventos del volcado en ``DumpConfig.audit_sink``; ``None`` sin destino.
        constraint_reactivation_error: Mensaje de error si la reactivación general de constraints falló
            (fallo no recuperable en ``ConstraintManager.enable_all()``). Distinto de ``constraint_results``,
            que reporta fallos por-constraint/tabla. ``None`` si la reactivación fue exitosa.
            Si presente, aparece en la hoja "Errores de Reactivación" del informe Excel (con fondo rojo).
        constraints_journal: Ruta del diario de constraints si sigue en ``output_dir`` al terminar (4.4.0): alguna
            constraint no se pudo reactivar (SQL Server, PostgreSQL u Oracle). Reintentar con
            ``restore_constraints(target_engine, ruta)`` tras corregir la causa. ``None`` si todo se reactivó o el
            destino no lleva diario.
    """

    table_results: list[TableDumpResult]
    constraint_results: list[ConstraintResult]
    load_order: list[str]
    cycles_detected: list[list[str]]
    report: Path
    audit_summary: DumpAuditSummary | None = None
    pk_sync_results: list[PKSyncResult] | None = None
    index_results: list[IndexActionResult] | None = None
    audit_run_id: str | None = None
    constraint_reactivation_error: str | None = None
    constraints_journal: Path | None = None

    @property
    def rows_rejected(self) -> int:
        """Filas apartadas al CSV de rechazos en todo el volcado (``DumpConfig(on_error="isolate")``)."""
        return sum(result.rows_rejected for result in self.table_results)
