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

- **Auditoría habilitada**: el parámetro `audit_csv_path` en `BulkCrud` activa el registro automático de cada operación bulk. El CSV resultante incluye tabla, motor, filas, duración y timestamp.
- **Manejo de excepciones**: se captura `ValidationError` (parámetros incorrectos) y `DatabaseException` (error de BD) por separado, siguiendo la jerarquía de excepciones de `util_bbdd`.
- **Normalización automática**: `BulkCrud` normaliza los identificadores de columna según el motor destino (minúsculas para PostgreSQL/Oracle, mayúsculas para MySQL/MariaDB/SQL Server).

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/bulk_insert_csv.py

# Ejecución (requiere BD accesible y CSV de entrada)
python docs/examples/bulk_insert_csv.py
```

El CSV de auditoría se crea en la ruta configurada con columnas: `timestamp`, `tabla`, `motor`, `operacion`, `total_filas`, `tiempo_seg`, `sql`. `tiempo_seg` mide la ejecución en BD (`sql=No`) o, con `generar_sql=True`, la generación del fichero SQL (`sql=Sí`).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk-operations.md) — objetivo de negocio y reglas de negocio de las operaciones bulk
- **Referencia técnica**: [CRUD Masivo (BulkCrud)](../api/bulk-crud.md) — contratos de API y estrategias INSERT por motor
- **Referencia técnica**: [Auditoría Bulk (AuditManager)](../api/bulk-audit.md) — API de auditoría en CSV
- **Ejemplos relacionados**: [Carga Paralela de Millones de Filas](parallel_bulk_insert.md) — carga en paralelo con múltiples workers
