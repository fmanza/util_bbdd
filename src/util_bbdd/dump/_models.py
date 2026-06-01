"""Tipos de datos públicos del módulo dump.

Separados en un módulo propio para romper la dependencia circular entre
``orchestrator`` y ``reporters``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import Engine

from util_bbdd.bulk._models import PKSyncResult

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
        chunk_size: Filas por chunk. Se aplica en dos niveles: (1) lectura origen
            vía ``pd.read_sql(chunksize=chunk_size)`` y (2) inserción destino en
            ``BulkCrud(chunk_size=chunk_size)``. Ambos reciben el mismo valor.
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
            soportado (no-op). Nunca toca índices que respaldan PK/UNIQUE.
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


@dataclass
class TableDumpResult:
    """Resultado del volcado de una tabla individual."""

    table_name: str
    source_rows: int
    target_rows_before: int
    target_rows_after: int
    status: Literal["success", "missing_target", "skipped", "error"]
    skipped_columns: list[str]
    load_order_position: int
    in_cycle: bool = False
    error_msg: str = ""


@dataclass
class DumpAuditSummary:
    """Métricas de auditoría de inserts extraídas del CSV de ``bulk.audit`` al finalizar el volcado.

    Solo se popula cuando ``DumpConfig.bulk_audit_path`` está configurado y el CSV
    contiene entradas del rango temporal del volcado.

    Attributes:
        total_operaciones: Número de lotes INSERT registrados en auditoría.
        total_filas: Suma de filas insertadas según el CSV de auditoría.
        tiempo_total_seg: Tiempo total de inserción (segundos) según auditoría.
        tiempo_promedio_seg: Tiempo medio por lote INSERT.
        tablas_auditadas: Número de tablas distintas con al menos un INSERT registrado.
        tabla_mas_activa: Tabla con mayor número de lotes INSERT (``None`` si no hay datos).
        audit_path: Ruta del CSV de auditoría consultado.
    """

    total_operaciones: int
    total_filas: int
    tiempo_total_seg: float
    tiempo_promedio_seg: float
    tablas_auditadas: int
    tabla_mas_activa: str | None
    audit_path: Path


@dataclass
class DumpResult:
    """Resultado completo de un volcado.

    Attributes:
        table_results: Resultado por tabla volcada (o intentada).
        constraint_results: Resultado por constraint al rehabilitar.
        load_order: Orden topológico de carga aplicado.
        cycles_detected: Grupos de tablas con FK circular (cargadas al final).
        report: Ruta del informe Excel generado (3 hojas).
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
