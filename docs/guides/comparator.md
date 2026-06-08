# Guía del Comparador de Esquemas

## 1. Objetivo

Configurar `SchemaComparator` para detectar diferencias de esquema entre dos bases de datos y generar reportes en múltiples formatos.

## 2. Requisitos Previos

- `util_bbdd` instalado: `pip install util_bbdd`
- Dos conexiones activas a las bases de datos a comparar (origen y destino) con permisos de lectura sobre metadatos del esquema
- Para exportar reportes: dependencias adicionales según formato:
  - Word: `python-docx`
  - Excel: `openpyxl`
  - HTML: `Jinja2`
  - Todos: `pip install "util-bbdd[doc]"`

## 3. Pasos

### Paso 1 — Crear los inspectores SQLAlchemy

```python
from sqlalchemy import create_engine, inspect

engine_origen = create_engine("postgresql+psycopg2://user:pass@host/db_origen")
engine_destino = create_engine("postgresql+psycopg2://user:pass@host/db_destino")

inspector_origen = inspect(engine_origen)
inspector_destino = inspect(engine_destino)
```

### Paso 2 — Ejecutar la comparación

```python
from util_bbdd import SchemaComparator

comparador = SchemaComparator()
diff = comparador.compare(
    inspector_origen,
    inspector_destino,
    include_views=True,
    include_routines=False,   # activar solo si se necesitan procedures
)
```

### Paso 3 — Revisar el resultado

```python
if not diff.has_differences:
    print("Esquemas idénticos")
else:
    print(f"Diferencias encontradas: {diff.total_differences}")
    for td in diff.table_diffs:
        print(f"  [{td.status.upper()}] {td.table_name}")
```

### Paso 4 — Generar reportes

```python
from util_bbdd import SchemaDiffReporter
from pathlib import Path

reporter = SchemaDiffReporter(sql_dialect="postgresql")
ficheros = reporter.render_all(
    diff,
    output_dir=Path("reportes"),
    formats=["html", "excel", "sql"],
)
print("Reportes generados:", ficheros)
```

## 4. Verificación

```python
from sqlalchemy import create_engine, inspect
from util_bbdd import SchemaComparator

# Comparar SQLite consigo mismo (debe devolver 0 diferencias)
engine = create_engine("sqlite:///:memory:")
with engine.connect() as conn:
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
inspector = inspect(engine)

diff = SchemaComparator().compare(inspector, inspector)
assert not diff.has_differences, "Debería devolver 0 diferencias"
print("OK: comparación con sí mismo devuelve 0 diferencias")
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `SchemaDiffValidationError` | Formato de reporte no soportado | Usar solo: `"html"`, `"excel"`, `"word"`, `"markdown"`, `"sql"` |
| `DiffReportGenerationError` para Word | `python-docx` no instalado | `pip install "util-bbdd[doc]"` |
| Rutinas no comparadas aunque `include_routines=True` | Motor no soportado (HSQLDB) o permisos insuficientes | Verificar permisos sobre catálogos del sistema (`pg_proc`, `ALL_PROCEDURES`, `sys.procedures`) |
| Índices anónimos no detectados | Los índices sin nombre se ignoran por diseño | Dar nombre explícito a los índices en el esquema |
| Diferencias de comentarios faltantes | Solo se comparan columnas comunes a ambos esquemas | *No aplica para este módulo.* Es una limitación del módulo. |
