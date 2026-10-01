"""Tipos de datos públicos del módulo dump.

Separados en un módulo propio para romper la dependencia circular entre
``orchestrator`` y ``reporters``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import Engine

from util_bbdd.bulk._execution.executors import validate_chunk_size
from util_bbdd.bulk._models import PKSyncResult
from util_bbdd.bulk._support.rejects import validate_isolation

__all__: list[str] = ["PKSyncResult"]


@dataclass
class ConstraintResult:
    """Resultado de rehabilitar una constraint individual en el destino."""

    table_name: str
    constraint_name: str
    dialect: str
    status: Literal["enabled", "failed", "unverified"]
    error_msg: str = ""


@dataclass
class IndexActionResult:
    """Resultado de gestionar (deshabilitar/reconstruir) un índice individual en el destino.

    Attributes:
        table_name: Tabla a la que pertenece el índice (``"*"`` para resultados globales).
        index_name: Nombre del índice (``"*"`` para resultados globales).
        dialect: Dialecto del motor destino.
        action: Resultado de la operación:

            - ``"rebuilt"`` — índice deshabilitado/unusable y reconstruido (mssql/oracle).
            - ``"recreated"`` — índice eliminado y recreado desde su DDL (postgresql).
            - ``"failed"`` — fallo al reconstruir/recrear; ver ``error_msg``.
            - ``"unsupported"`` — motor no soportado (mariadb/mysql InnoDB).
        error_msg: Detalle del error cuando ``action="failed"`` o ``"unsupported"``.
    """

    table_name: str
    index_name: str
    dialect: str
    action: Literal["rebuilt", "recreated", "failed", "unsupported"]
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
        output_dir: Directorio donde guardar el informe Excel.
        truncate_target: ``True`` (default) = limpiar tablas destino antes de cargar.
            Recomendado para volcados completos. ``False`` = modo append.
        bulk_audit_path: Ruta del CSV de auditoría para los inserts en destino.
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
        manage_indexes: Si ``True``, deshabilita los índices secundarios **no únicos** del
            destino antes de la carga y los reconstruye al final, acelerando los INSERT en
            tablas con muchos índices. ``False`` (default) = no se tocan los índices.
            Comportamiento por motor: mssql ``ALTER INDEX DISABLE``→``REBUILD`` (solo
            NONCLUSTERED), oracle ``UNUSABLE``→``REBUILD``, postgresql ``DROP``+recreate
            desde ``pg_get_indexdef`` (DDL logueado antes del DROP), mariadb/mysql no
            soportado (no-op). Nunca toca índices que respaldan PK/UNIQUE. Efecto medido a 3,5M
            filas con 2 índices secundarios (tras solapar lectura y escritura): Oracle −14 %
            (reconstrucción 2,7 s), SQL Server −8 %, PostgreSQL sin ganancia. Compensa más cuantos más
            índices secundarios tenga el destino; no se activa automáticamente.
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
        write_batch_size: Filas por lote de escritura en el destino (una sentencia ``COPY`` o
            ``executemany`` por lote). ``None`` (default): 20 000 con destino PostgreSQL (``COPY``,
            −31 % a 3,5M filas frente a 5 000) y ``chunk_size`` en el resto de motores (en SQL Server
            un lote de 20 000 fue un 81 % más lento). Con ``commit_every_n_chunks`` el default es
            siempre ``chunk_size``, para no cambiar cada cuántas filas se confirma. Un entero fija el
            lote en todos los motores. La lectura sigue siendo por ``chunk_size``; los chunks leídos
            se agrupan hasta completar el lote (+1 lote en memoria).
        on_error: Como ``BulkCrud(on_error=...)``: con ``"isolate"`` las filas que el destino no admite (PK duplicada,
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

    Raises:
        ValueError: Si ``chunk_size`` no es un entero ≥ 1, o si ``commit_every_n_chunks`` o ``write_batch_size`` no son
            ``None`` ni un entero ≥ 1, o si ``on_error``, ``rejects_csv_path`` y ``max_rejects`` no son una
            combinación válida (las reglas de ``BulkCrud``). Se valida al construir, antes de tocar el destino.
    """

    source_engine: Engine
    target_engine: Engine
    source_schema: str | None = None
    target_schema: str | None = None
    tables: list[str] | None = None
    chunk_size: int = 5000
    output_dir: Path = field(default_factory=Path)
    truncate_target: bool = True
    bulk_audit_path: Path | None = None
    collect_row_counts: bool = True
    sync_pk_sequences: bool = True
    commit_every_n_chunks: int | None = None
    manage_indexes: bool = False
    max_parallel_tables: int = 1
    parallel_pk_ranges: int = 1
    bulk_audit_strict: bool = False
    write_batch_size: int | None = None
    on_error: Literal["raise", "isolate"] = "raise"
    rejects_csv_path: Path | None = None
    max_rejects: int | None = None

    def __post_init__(self) -> None:
        # Validar aquí y no en la primera BulkCrud: run() la crea después de vaciar el destino (truncate_target), así que
        # un chunk_size o commit_every_n_chunks inválido vaciaba las tablas y luego fallaba; con chunk_size=0 y
        # write_batch_size no se leía nada y la tabla quedaba vacía con estado "success".
        validate_chunk_size(self.chunk_size)
        if self.commit_every_n_chunks is not None and self.commit_every_n_chunks < 1:
            raise ValueError(
                f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {self.commit_every_n_chunks}"
            )
        if self.write_batch_size is not None and self.write_batch_size < 1:
            raise ValueError(f"write_batch_size debe ser None o un entero ≥ 1, recibido: {self.write_batch_size}")
        validate_isolation(self.on_error, self.rejects_csv_path, self.max_rejects)


@dataclass
class TableDumpResult:
    """Resultado del volcado de una tabla individual.

    ``rows_rejected``: filas apartadas al CSV de rechazos con ``DumpConfig(on_error="isolate")``; la tabla puede ser
    ``success`` con filas rechazadas.
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


@dataclass
class DumpResult:
    """Resultado completo de un volcado.

    Attributes:
        table_results: Resultado por tabla volcada (o intentada).
        constraint_results: Resultado por constraint al rehabilitar.
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
    """

    table_results: list[TableDumpResult]
    constraint_results: list[ConstraintResult]
    load_order: list[str]
    cycles_detected: list[list[str]]
    report: Path
    audit_summary: DumpAuditSummary | None = None
    pk_sync_results: list[PKSyncResult] | None = None
    index_results: list[IndexActionResult] | None = None

    @property
    def rows_rejected(self) -> int:
        """Filas apartadas al CSV de rechazos en todo el volcado (``DumpConfig(on_error="isolate")``)."""
        return sum(result.rows_rejected for result in self.table_results)
