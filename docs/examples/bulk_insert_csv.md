# Ejemplo: Bulk Insert desde CSV con Auditoría

## 1. Contexto del Ejemplo

Carga datos de un fichero CSV mediante `pandas`, los inserta masivamente en base de datos con `BulkCrud` y registra cada operación en un CSV de auditoría con timestamps.

Resuelve el patrón ETL más frecuente: "tengo un CSV, quiero cargarlo en BD y tener trazabilidad de cuándo se hizo y cuántas filas se procesaron."

## 2. Implementación de Referencia

```python
--8<-- "examples/bulk_insert_csv.py"
```

## 3. Explicación del Código

El ejemplo demuestra tres aspectos clave:

- **Auditoría habilitada**: `AuditOptions(csv_path=...)` es la ruta del **fichero** CSV de auditoría (el directorio se crea si falta). Cada operación bulk añade una fila con tabla, motor, filas, duración y timestamp. El CSV es tabulado y con coma decimal: se lee con `AuditManager(ruta).leer_auditoria()`, no con `pd.read_csv` por defecto.
- **`generar_sql=False`**: desde 5.0.0 es lo que hace `bulk_insert_from_df` por defecto (ejecutar); hasta 4.x, sin él, generaba un fichero SQL en lugar de ejecutar. Para generar el SQL sin tocar la BD, `dry_run=True` (nombre preferido) con `path_sql`.
- **Tabla destino**: `BulkCrud` no crea tablas; el ejemplo la crea antes de cargar.
- **Columnas**: las del DataFrame se emparejan con las de la tabla sin distinguir mayúsculas.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/bulk_insert_csv.py

# Ejecución contra un PostgreSQL accesible; el ejemplo genera el CSV de entrada
# (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla; ?schema=… elige el schema de la tabla)
export UTIL_BBDD_EXAMPLE_URL="postgresql+psycopg://postgres:secret@localhost:5432/test_db"
python docs/examples/bulk_insert_csv.py
```

El CSV de auditoría se crea en la ruta configurada con columnas: `timestamp`, `tabla`, `motor`, `operacion`, `total_filas`, `tiempo_seg`, `sql`. `tiempo_seg` mide la ejecución en BD (`sql=No`) o, con `generar_sql=True`, la generación del fichero SQL (`sql=Sí`).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk_operations.md) — objetivo de negocio y reglas de negocio de las operaciones bulk
- **Referencia técnica**: [CRUD Masivo (BulkCrud)](../api/bulk_crud.md) — contratos de API y estrategias INSERT por motor
- **Referencia técnica**: [Auditoría Bulk (AuditManager)](../api/bulk_audit.md) — API de auditoría en CSV
- **Ejemplos relacionados**: [Carga Paralela de Millones de Filas](parallel_bulk_insert.md) — carga en paralelo con múltiples workers
