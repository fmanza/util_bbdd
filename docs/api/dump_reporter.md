# Generador de Reportes de Volcado (DumpReporter)

Genera el informe Excel de auditoría para volcados de datos, con múltiples hojas que documentan volumetría, tablas/columnas faltantes, estado de constraints, índices, el resumen de la auditoría de `bulk` y la resincronización de contadores de PK.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A[DumpReporter.generate] --> B[Hoja 1: Auditoría Tablas]
    A --> C[Hoja 2: Tablas Faltantes]
    A --> D[Hoja 3: Columnas Inexistentes]
    A --> E{constraint_reactivation_error?}
    E -- Sí --> E1[Hoja 4: Errores de Reactivación]
    A --> F{index_results?}
    F -- Sí --> F1[Hoja 5: Índices]
    A --> H{audit_summary?}
    H -- Sí --> I[Hoja 6: Auditoría Bulk]
    A --> J{pk_sync_results?}
    J -- Sí --> K[Hoja 7: Secuencias PK]
    B & C & D & E1 & F1 & I & K --> G[Fichero dump_report_YYYYMMDD_HHMMSS.xlsx]
```

## 2. Modelo de Datos / Contratos

### API pública

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `DumpReporter` | `(output_dir: Path)` | Inicializa; `generate()` crea `output_dir` si no existe | `DumpReporter` |
| `generate` | `(table_results, missing_tables, constraint_results, cycles, index_results?, audit_summary?, pk_sync_results?, constraint_reactivation_error?)` | Genera el fichero Excel con auditoría completa | `Path` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `output_dir` | `Path` | Directorio donde guardar el Excel | Se crea al generar si no existe |
| `table_results` | `list[TableDumpResult]` | Resultado por tabla volcada | Estado, volumetría, columnas omitidas, errores |
| `missing_tables` | `list[str]` | Tablas en origen sin equivalente en destino | — |
| `constraint_results` | `list[ConstraintResult]` | Resultados de rehabilitación de constraints | — |
| `cycles` | `list[list[str]]` | Grupos de tablas con ciclos FK | — |
| `index_results` | `list[IndexActionResult] \| None` | Gestión de índices; `None` omite la hoja Índices | Default `None` |
| `audit_summary` | `DumpAuditSummary \| None` | Resumen de la auditoría de `bulk` del volcado (`DumpResult.audit_summary`); `None` omite la hoja Auditoría Bulk | Default `None` |
| `pk_sync_results` | `list[PKSyncResult] \| None` | Resincronización de contadores de PK (`DumpResult.pk_sync_results`); `None` omite la hoja Secuencias PK | Default `None` |
| `constraint_reactivation_error` | `str \| None` | Error general de reactivación de constraints (`DumpResult.constraint_reactivation_error`); `None` omite la hoja Errores de Reactivación | Default `None` |

### Contrato de salida

- Retorna `Path` del fichero Excel generado con nombre `dump_report_YYYYMMDD_HHMMSS.xlsx` (`_2`, `_3`… si ya existe).
- **Hoja 1 — Auditoría Tablas**: tabla, posición de carga, FK circular, filas origen/destino antes/después, filas rechazadas, estado, columnas omitidas, error. Debajo, si las hay, las constraints con estado `FAILED` o `UNVERIFIED` al rehabilitarlas (tabla, constraint, dialect, estado, mensaje).
- **Hoja 2 — Tablas Faltantes**: tablas presentes en origen pero ausentes en destino.
- **Hoja 3 — Columnas Inexistentes**: columnas en origen sin equivalente en destino, agrupadas por tabla.
- **Hoja 4 — Errores de Reactivación** (solo si `constraint_reactivation_error` no es `None`): tipo de error y descripción, con fondo rojo. Incluye nota explicativa sobre la diferencia con fallos por-constraint que aparecen en la hoja "Auditoría Tablas". El error reportado es un fallo general no recuperable de `ConstraintManager.enable_all()` durante la Fase 6.
- **Hoja 5 — Índices** (solo si `index_results` no es `None`): tabla, índice, dialect, acción (`REBUILT`, `RECREATED`, `FAILED`, `UNSUPPORTED`) y mensaje.
- **Hoja 6 — Auditoría Bulk** (solo si `audit_summary` no es `None`): métrica y valor. Ruta del CSV, operaciones y filas del CSV, filas escritas por el volcado (`audited_rows`), tiempos, tablas auditadas y tabla más activa, y los contadores de incidencia. Se resaltan en rojo `audit_failures` y `audit_uncommitted_records` mayores que 0, en naranja `unaudited_committed_rows` mayor que 0, y en amarillo las filas del CSV y las del volcado cuando no coinciden.
- **Hoja 7 — Secuencias PK** (solo si `pk_sync_results` no es `None`): tabla, columna PK, dialect, `MAX(PK)` (`—` si la tabla estaba vacía), estado y mensaje. Estado en verde (`SYNCED`, `NO_ROWS`), amarillo (`SKIPPED`: sin secuencia, p.ej. PK natural), naranja (`UNSUPPORTED`) o rojo (`ERROR`).
- Las hojas opcionales van siempre detrás de las fijas, en el orden 4-5-6-7, para no mover las existentes.
- Ninguna celda se guarda como fórmula: un texto que empieza por `=` (nombre de tabla del catálogo o del CSV, mensaje de error) se escribe como texto en todas las hojas.

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `DumpReportError` | Cualquier fallo al generar el informe: crear `output_dir`, escribir el fichero (permisos, disco lleno, fichero abierto) o un valor que openpyxl no admite; `exc.output_path` lleva la ruta prevista |

## 3. Componentes y Clases

*No aplica para este módulo.* `DumpReporter` es la única clase del módulo.

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `openpyxl` | Generación del fichero Excel | Sí | Error al llamar a `generate()` |

## 5. Ejemplos Relacionados

- [Ejemplo: Volcado de Datos entre Motores](../examples/dump_data_export.md) — Generación e interpretación del informe Excel de auditoría
