# Volcado de Datos entre Bases de Datos

Este ejemplo muestra cómo copiar todos los datos de un esquema **PostgreSQL** a un esquema **SQL Server** usando `DumpOrchestrator`.

El mismo patrón funciona para cualquier combinación de motores soportados.

---

## Caso de uso

Un equipo de analítica necesita refrescar su entorno SQL Server con los datos de producción de PostgreSQL. El proceso debe:

1. Respetar el orden de las FKs (no cargar `items` antes que `orders`).
2. Limpiar el destino antes de cargar (modo refresco completo).
3. Continuar aunque alguna tabla falle (best-effort).
4. Generar un informe Excel de auditoría con el resultado.

---

## Código completo

```python
from pathlib import Path
from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator

# 1. Engines
src_engine = create_engine(
    "postgresql+psycopg2://user:password@prod-server:5432/production_db"
)
dst_engine = create_engine(
    "mssql+pymssql://user:password@analytics-server/analytics_db"
)

# 2. Configuración
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    source_schema="public",          # esquema origen en PostgreSQL
    target_schema="dbo",             # esquema destino en SQL Server
    chunk_size=10_000,               # filas por chunk (tuning por volumen)
    output_dir=Path("reports"),      # directorio para el informe Excel
    truncate_target=True,            # vaciar destino antes de cargar
)

# 3. Ejecutar volcado
result = DumpOrchestrator(config).run()

# 4. Revisar resultado
print(f"Informe: {result.report}")
print(f"Orden de carga: {result.load_order}")

if result.cycles_detected:
    print(f"Ciclos FK detectados: {result.cycles_detected}")

for tr in result.table_results:
    print(
        f"  [{tr.status.upper():15}] {tr.table_name:30} "
        f"origen={tr.source_rows:>8}  destino={tr.target_rows_after:>8}"
    )
    if tr.skipped_columns:
        print(f"    Columnas omitidas: {', '.join(tr.skipped_columns)}")
    if tr.error_msg:
        print(f"    ERROR: {tr.error_msg}")

# 5. Constraints con incidencias
failed = [cr for cr in result.constraint_results if cr.status != "enabled"]
if failed:
    print("\nConstraints con incidencias al rehabilitar:")
    for cr in failed:
        print(f"  [{cr.status.upper()}] {cr.table_name}.{cr.constraint_name}: {cr.error_msg}")
```

---

## Volcado selectivo de tablas

Para copiar solo un subconjunto de tablas, especifica la lista en `DumpConfig.tables`:

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    tables=["customers", "orders", "order_items"],  # solo estas 3 tablas
    output_dir=Path("reports"),
)
result = DumpOrchestrator(config).run()
```

El orden topológico se calcula solo sobre las tablas especificadas.

---

## Modo append (sin truncar destino)

Si quieres añadir datos sin borrar los existentes (modo incremental):

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    truncate_target=False,    # no vaciar destino
    output_dir=Path("reports"),
)
```

!!! warning "Duplicados"
    En modo append, si los datos ya existen en destino con las mismas PKs, la carga fallará con `IntegrityError`. Usa este modo solo cuando los datos de origen son estrictamente nuevos.

---

## Interpretar el informe Excel

El fichero `dump_report_<timestamp>.xlsx` contiene tres hojas:

### Hoja 1 — Auditoría Tablas

Muestra el estado de cada tabla con código de colores:

| Color | Significado |
|---|---|
| 🟢 Verde | `SUCCESS` — datos cargados correctamente |
| 🔴 Rojo | `ERROR` — fallo durante la carga (ver columna "Error") |
| 🟡 Amarillo | `SKIPPED` — sin columnas comunes entre origen y destino |
| 🟠 Naranja | `MISSING_TARGET` — tabla no existe en destino |

Al pie de esta hoja aparece una sección con constraints que no pudieron rehabilitarse.

### Hoja 2 — Tablas Faltantes

Lista de tablas presentes en origen que no tienen correspondencia en destino. Para cada una se indica la acción sugerida: crear la tabla con el DDL del origen.

### Hoja 3 — Columnas Inexistentes

Columnas presentes en origen pero ausentes en destino. Estas columnas se omitieron del volcado automáticamente.

---

## Troubleshooting

### La tabla tiene ciclos FK (`in_cycle=True`)

Las tablas con dependencias circulares no pueden ordenarse topológicamente. El módulo las detecta y las carga al final (con constraints ya deshabilitadas). Si la carga falla igualmente, puede indicar que los datos violan la restricción FK.

**Solución:** Revisar los datos circulares en origen. En muchos casos, una de las referencias puede ser nullable y el orden de inserción debe ser manual.

### Columnas omitidas inesperadamente

Si `skipped_columns` contiene columnas que esperabas cargar, verifica que el nombre exacto de la columna coincide en ambos esquemas (incluyendo capitalización).

El módulo usa comparación **case-insensitive**, pero si la columna simplemente no existe en destino, se omite. Crea la columna en destino con el DDL correspondiente.

### Constraint failed al rehabilitar

Si `ConstraintResult.status == "failed"`, significa que los datos cargados infringen la restricción. El informe Excel incluye el mensaje de error de la BD.

**Causas habituales:**
- Datos huérfanos (FK referencia a una fila que no existe en la tabla referenciada)
- Datos duplicados en columnas UNIQUE
- Valores NULL en columnas NOT NULL

**Solución:** Corregir los datos en origen o ajustar el orden de carga mediante `DumpConfig.tables`.

### Performance con tablas grandes

Para tablas con millones de filas, ajusta `chunk_size`:

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    chunk_size=50_000,    # chunks más grandes → menos round-trips
    output_dir=Path("reports"),
)
```

Valores recomendados:
- Tablas < 100 MB: `chunk_size=10_000`
- Tablas 100 MB – 1 GB: `chunk_size=25_000`–`50_000`
- Tablas > 1 GB: `chunk_size=50_000`–`100_000` (según RAM disponible)

---

## Ver también

- [Documentación Funcional — Volcado de Datos](../functional/dump-data-export.md)
- [API Técnica — Volcado de Datos](../api/dump.md)
- [Comparación de Esquemas](schema_comparison.md) — analizar diferencias antes de volcar
