# Orquestador de Volcado (DumpOrchestrator)

Orquesta la copia completa de datos entre esquemas en 7 fases automáticas: introspección → análisis FK → desactivación de constraints → limpieza → carga → rehabilitación → informe Excel.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A[DumpOrchestrator.run] --> B[Fase 1: Introspección]
    B --> C[Fase 2: Análisis topológico FK]
    C --> D[Fase 3: Desactivar constraints]
    D --> E{truncate_target?}
    E -- Sí --> F[Fase 4: Limpiar destino]
    E -- No --> G
    F --> G[Fase 5: Carga best-effort]
    G --> H[Fase 6: Rehabilitar constraints]
    H --> J{sync_pk_sequences?}
    J -- Sí --> K[Fase 6a: Sincronizar PKs]
    J -- No --> I
    K --> I[Fase 7: Generar informe Excel]
    I --> Z[DumpResult]
```

## 2. Modelo de Datos / Contratos

### API pública

#### Clase `DumpOrchestrator`

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `DumpOrchestrator` | `(config: DumpConfig)` | Prepara inspectores; no abre conexiones hasta `run()` | `DumpOrchestrator` |
| `run` | `()` | Ejecuta las 7 fases y retorna resultado completo | `DumpResult` |

#### Dataclass `DumpConfig` (parámetros principales)

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `source_engine` | `Engine` | — | Engine de origen (lectura) |
| `target_engine` | `Engine` | — | Engine de destino (escritura) |
| `source_schema` / `target_schema` | `str \| None` | `None` | Schema a volcar; `None` usa default del engine |
| `tables` | `list[str] \| None` | `None` | Tablas a volcar; `None` = todas las del origen |
| `chunk_size` | `int` | `5000` | Filas por chunk de lectura del origen; también el lote de escritura salvo lo que diga `write_batch_size` |
| `write_batch_size` | `int \| None` | `None` | Filas por lote de escritura. `None`: 20 000 con destino PostgreSQL (`COPY`; −31 % a 3,5M filas) y `chunk_size` en el resto (en SQL Server los lotes grandes son más lentos); con `commit_every_n_chunks`, siempre `chunk_size`. Un entero fija el lote en todos los motores |
| `output_dir` | `Path` | `Path()` | Directorio donde guardar el informe Excel |
| `truncate_target` | `bool` | `True` | Vaciar destino antes de cargar: `TRUNCATE TABLE`; en PostgreSQL, un único `TRUNCATE` con todas las tablas del volcado (tabla a tabla si falla); `DELETE FROM` en SQLite (no tiene `TRUNCATE`) y en las tablas de SQL Server referenciadas por FK |
| `sync_pk_sequences` | `bool` | `True` | Resincronizar contadores PK tras la carga |
| `manage_indexes` | `bool` | `False` | Deshabilitar/reconstruir índices secundarios no únicos (no aplica en MySQL/MariaDB). Medido a 3,5M filas con 2 índices secundarios: Oracle −14 %, SQL Server −8 %, PostgreSQL sin ganancia; compensa más con muchos índices |
| `max_parallel_tables` | `int` | `1` | Tablas en paralelo dentro del mismo nivel FK |
| `parallel_pk_ranges` | `int` | `1` | Rangos de PK para particionar tablas grandes (PK de una columna entera). Medido con 4 rangos a 3,5M filas frente a la carga secuencial: SQL Server −37 % (recomendado); PostgreSQL −9 % y Oracle −2 %; MySQL/MariaDB casi el doble de tiempo (no recomendado, WARNING); SQLite se fuerza a 1. Necesita un pool con capacidad ≥ rangos × `max_parallel_tables` |
| `bulk_audit_path` | `Path \| None` | `None` | CSV de auditoría de los inserts en destino; `None` = sin auditoría |
| `bulk_audit_strict` | `bool` | `False` | Se pasa como `audit_strict` a cada `BulkCrud` y `ParallelBulkLoader`. `False`: un fallo al escribir el CSV no interrumpe la carga y se cuenta en `audit_summary.audit_failures`. `True`: el fallo deshace la carga de esa tabla (o partición) y queda como error de la tabla |

#### Dataclass `DumpResult`

| Atributo | Tipo | Descripción |
|---|---|---|
| `table_results` | `list[TableDumpResult]` | Resultado por tabla (incluye faltantes) |
| `constraint_results` | `list[ConstraintResult]` | Resultado de rehabilitación de constraints |
| `load_order` | `list[str]` | Orden topológico aplicado |
| `cycles_detected` | `list[list[str]]` | Grupos de tablas con FK circular |
| `report` | `Path` | Ruta del fichero Excel generado |
| `audit_summary` | `DumpAuditSummary \| None` | Métricas de auditoría del volcado leídas del CSV (`total_operaciones`, `total_filas`, tiempos, tablas) y contadores del propio volcado: `audit_failures` (registros que no se pudieron escribir), `audited_rows` (filas que este volcado escribió en el CSV), `unaudited_committed_rows` (filas confirmadas por commits periódicos que no constan en el CSV) y `audit_uncommitted_records` (con `bulk_audit_strict`, registros escritos antes de un commit que falló). `None` si no hay `bulk_audit_path` o si el CSV no tiene entradas del volcado y no hubo incidencias |
| `pk_sync_results` | `list[PKSyncResult] \| None` | Resultado sincronización PK; `None` si desactivado |
| `index_results` | `list[IndexActionResult] \| None` | Resultado gestión índices; `None` si desactivado |

`total_filas` sale del CSV filtrado por la hora de inicio, así que incluye lo que otros procesos escriban en el mismo
fichero durante el volcado; `audited_rows` cuenta solo lo de este volcado. Si no coinciden se registra un WARNING con
las dos cifras.

### Contrato de entrada

Ver tabla de `DumpConfig` arriba. Los engines deben estar conectables antes de llamar a `run()`.

### Contrato de salida

- `run()` retorna `DumpResult` siempre, incluso si algunas tablas fallaron (comportamiento best-effort).
- El informe Excel se genera siempre en `output_dir`, independientemente de errores parciales. Un `output_dir`
  relativo (el valor por defecto es `Path()`) se resuelve contra el directorio de trabajo del proceso.
- Si falla el resumen del CSV de auditoría (CSV ilegible o sin las columnas esperadas), se registra un WARNING, el
  informe sale sin la hoja «Auditoría Bulk» y `audit_summary` es `None`.
- Si falla el propio informe, la carga ya ha terminado: `run()` lanza `DumpReportError` con el resultado completo en
  `exc.result` (su `report` es la ruta prevista, `exc.output_path`, que no llegó a crearse).
- Los textos del informe se escriben sin caracteres de control, y los que empiezan por `=` se guardan como texto, no
  como fórmula (igual en los informes Excel de `bulk`, `comparar` y `doc`).

```python
from util_bbdd.dump import DumpOrchestrator, DumpReportError

try:
    result = DumpOrchestrator(config).run()
except DumpReportError as exc:
    result = exc.result  # la carga se completó; solo falta el Excel
```

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `SQLAlchemyError` | Conexión a origen o destino falla antes de comenzar |
| `DumpReportError` | No se pudo generar el informe Excel (directorio, permisos, fichero abierto, disco lleno). La carga ya terminó: `exc.result` lleva el `DumpResult` |
| Error capturado en `TableDumpResult.error` | Fallo en carga de una tabla individual; el resto continúa |
| Origen SQLite (WARNING al crear el orquestador) | SQLite no tiene tipos de columna: las fechas se leen como texto y los DECIMAL como `float`. Un destino servidor convierte las fechas; con destino SQLite, las tablas con columnas de fecha terminan en `error`. Los DECIMAL pueden perder precisión |
| Destino SQLite con `parallel_pk_ranges` o `max_parallel_tables` > 1 (WARNING) | SQLite admite un solo escritor: se carga sin paralelismo |
| Destino MySQL/MariaDB con `parallel_pk_ranges` > 1 (WARNING) | La carga por rangos es más lenta que la secuencial en estos motores; se aplica igualmente |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `DumpOrchestrator` | Coordinación de las 7 fases del volcado |
| `DumpConfig` | Configuración inmutable del volcado |
| `DumpResult` | Resultado completo incluyendo ruta del informe Excel |
| `ConstraintManager` | Gestión de desactivación/rehabilitación de constraints por motor |
| `IndexManager` | Gestión de desactivación/reconstrucción de índices secundarios |
| `DumpReporter` | Generación del informe Excel de auditoría |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `sqlalchemy` | Inspector, engines y ejecución SQL | Sí | Módulo no funciona |
| `metadata/sqlserver` (interno) | SQL de las FK de todo el esquema en SQL Server (orden de carga y limpieza en una consulta) | Sí | — |
| `BulkCrud` (interno) | Inserción de datos en destino | Sí | Módulo no funciona |
| `openpyxl` | Generación del informe Excel | Sí | Error al intentar generar el informe |
| `pandas` | Lectura de datos en chunks desde origen | Sí | Sin pandas no se pueden leer datos |

## 5. Ejemplos Relacionados

- [Ejemplo: Volcado de Datos entre Motores](../examples/dump_data_export.md) — PostgreSQL → SQL Server con `DumpOrchestrator`, modo paralelo y auditoría
