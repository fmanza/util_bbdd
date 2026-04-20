# SchemaComparator — Comparación de Esquemas de Bases de Datos

`SchemaComparator` permite comparar dos esquemas de base de datos y detectar todas las diferencias: tablas, columnas, índices, claves foráneas, vistas y comentarios.

**Version:** 0.6.7
**Motor-agnóstico:** Funciona con PostgreSQL, MariaDB, SQLite, Oracle, SQL Server, HSQLDB

---

## Conceptos Clave

### ¿Qué es Schema Comparison?

La comparación de esquemas identifica las diferencias estructurales entre dos bases de datos:

- **Tablas:** añadidas, eliminadas o modificadas
- **Columnas:** nuevas, eliminadas, cambios de tipo o nullability
- **Índices:** creados o eliminados
- **Foreign Keys:** nuevo s, eliminados, cambios de reglas
- **Vistas:** nuevas o eliminadas
- **Comentarios:** en tablas y columnas
- **Routines:** procedures y functions (soporte parcial)

### Casos de Uso

1. **Migraciones:** Detectar cambios en desarrollo vs producción
2. **Auditoría:** Verificar integridad de réplicas
3. **Testing:** Validar DDL generado es idéntico al esperado
4. **Documentación:** Generar reportes de cambios
5. **Versionado:** Rastrear evolución del esquema

---

## Instalación

`SchemaComparator` está incluido en `util_bbdd`:

```bash
pip install util_bbdd
```

---

## Uso Básico

### Paso 1: Crear Engines/Inspectors de SQLAlchemy

```python
from sqlalchemy import create_engine, inspect

# BD origen
SOURCE_CONN = "postgresql://user:pass@localhost:5432/db_old"
source_engine = create_engine(SOURCE_CONN)
source_inspector = inspect(source_engine)

# BD destino
TARGET_CONN = "postgresql://user:pass@localhost:5432/db_new"
target_engine = create_engine(TARGET_CONN)
target_inspector = inspect(target_engine)
```

### Paso 2: Comparar Esquemas

```python
from util_bbdd.comparar import SchemaComparator

comparator = SchemaComparator()

schema_diff = comparator.compare(
    source=source_inspector,
    target=target_inspector,
    source_schema="public",  # Opcional; None = schema default
    target_schema="public",
    include_tables=True,
    include_views=True,
    include_indices=True,
    include_foreign_keys=True,
    include_comments=True,
    include_routines=False,  # ⚠️ Soporte motor-specific
)
```

### Paso 4: Generar Reportes de Diferencias (NUEVO en v0.6.7)

La comparación produce un objeto `SchemaDiff`. Para exportar los resultados, usa **`SchemaDiffReporter`** con 6 formatos disponibles:

```python
from util_bbdd.comparar.reporters import SchemaDiffReporter

reporter = SchemaDiffReporter(schema_diff=schema_diff)

# Opción 1: Generar un formato específico
html_content = reporter.render_html()            # HTML con Mermaid (filtrable+búsqueda)
sql_script = reporter.render_sql()               # SQL para normalizar destino a origen
markdown_content = reporter.render_markdown()    # Markdown con tablas
excel_file = reporter.render_excel("./diff.xlsx")  # Excel (múltiples hojas)
word_file = reporter.render_word("./diff.docx")    # Word (formateado)

# Opción 2: Generar todos los reportes de una vez (recomendado)
files = reporter.render_all(
    output_dir="./schema_reports",
    basename="schema_diff",                       # Prefijo de nombres
    include_sql=True,
    sql_dialect="postgresql"                     # postgresql, oracle, mariadb, sqlite, sqlserver
)
# Retorna: {"html": "path/to/schema_diff.html", "sql": "...", ...}
```

#### Ejemplo Completo: Generar Todos los Reportes

```python
from sqlalchemy import create_engine, inspect
from pathlib import Path
from util_bbdd.comparar import SchemaComparator
from util_bbdd.comparar.reporters import SchemaDiffReporter

# 1. Conectar a dos BDs
source_engine = create_engine("postgresql://user:pass@localhost/db_dev")
target_engine = create_engine("postgresql://user:pass@prod-server/db_prod")

source_inspector = inspect(source_engine)
target_inspector = inspect(target_engine)

# 2. Comparar
comparator = SchemaComparator()
schema_diff = comparator.compare(
    source=source_inspector,
    target=target_inspector,
    source_schema="public",
    target_schema="public"
)

# 3. Generar reportes
reporter = SchemaDiffReporter(schema_diff)

output_dir = Path("./reports")
output_dir.mkdir(exist_ok=True)

files = reporter.render_all(
    output_dir=str(output_dir),
    basename="schema_comparison_20260416",
    sql_dialect="postgresql"  # Usa dialecto de la BD de destino
)

# 4. Archivos generados:
for format_name, file_path in files.items():
    print(f"✅ {format_name.upper()}: {file_path}")
```

**Salida:**
```
✅ HTML: ./reports/schema_comparison_20260416.html
✅ SQL: ./reports/schema_comparison_20260416.sql
✅ MARKDOWN: ./reports/schema_comparison_20260416.md
✅ EXCEL: ./reports/schema_comparison_20260416.xlsx
✅ WORD: ./reports/schema_comparison_20260416.docx
```

#### Formatos Disponibles

| Formato | Método | Uso | Dialecto SQL |
|---------|--------|-----|--------------|
| **HTML** | `render_html()` | Interactivo, filtrable, búsqueda + Mermaid ERD | — |
| **SQL** | `render_sql(dialect="postgresql")` | Script para ejecutar en BD destino | postgresql, oracle, mariadb, sqlite, sqlserver |
| **Markdown** | `render_markdown()` | Documentación, GitHub, wikis | — |
| **Excel** | `render_excel(path)` | Análisis en hoja de cálculo | — |
| **Word** | `render_word(path)` | Reporte profesional | — |

---

## Ejemplo Completo

```python
# Resumen de cambios
print("Resumen:", schema_diff.summary)

# Tablas con diferencias
for table_diff in schema_diff.table_diffs:
    if table_diff.status != "unmodified":
        print(f"Tabla '{table_diff.table_name}': {table_diff.status}")

        # Columnas modificadas
        for col_diff in table_diff.column_diffs:
            print(f"  - Columna '{col_diff.column_name}': {col_diff.attribute}:")
            print(f"    Origen: {col_diff.source_value}")
            print(f"    Destino: {col_diff.target_value}")

        # Índices modificados
        for idx_diff in table_diff.index_diffs:
            print(f"  - Índice '{idx_diff.index_name}': {idx_diff.status}")

# Vistas modificadas
for view_diff in schema_diff.view_diffs:
    if view_diff.status != "unmodified":
        print(f"Vista '{view_diff.view_name}': {view_diff.status}")
```

---

## Ejemplo Completo

### Escenario: Detectar cambios entre dev y prod

```python
import sys
from sqlalchemy import create_engine, inspect
from util_bbdd.comparar import SchemaComparator

def compare_databases(source_url: str, target_url: str):
    """Compara dos esquemas y genera reporte."""

    # Crear engines
    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    source_inspector = inspect(source_engine)
    target_inspector = inspect(target_engine)

    # Comparar
    comparator = SchemaComparator()
    diff = comparator.compare(
        source=source_inspector,
        target=target_inspector,
        include_routines=False
    )

    # Generar reporte
    print("=" * 60)
    print("COMPARATIVA DE ESQUEMAS")
    print("=" * 60)
    print(f"\nOrigen: {diff.source_label}")
    print(f"Destino: {diff.target_label}\n")

    print(f"Resumen: {diff.summary}\n")

    # ---- TABLAS ----
    if diff.table_diffs:
        print("-" * 60)
        print("TABLAS")
        print("-" * 60)

        for t_diff in diff.table_diffs:
            status_icon = {
                "added": "➕",
                "removed": "➖",
                "modified": "🔧",
                "unmodified": "✅"
            }.get(t_diff.status, "❓")

            print(f"\n{status_icon} {t_diff.table_name} ({t_diff.status})")

            # Columnas
            if t_diff.column_diffs:
                print(f"  Columnas modificadas:")
                for c_diff in t_diff.column_diffs:
                    print(f"    - {c_diff.column_name}: {c_diff.attribute}")
                    print(f"      Origen: {c_diff.source_value}")
                    print(f"      Destino: {c_diff.target_value}")

            # Índices
            if t_diff.index_diffs:
                print(f"  Índices modificados:")
                for i_diff in t_diff.index_diffs:
                    print(f"    - {i_diff.index_name}: {i_diff.status}")
                    if i_diff.source_columns:
                        print(f"      Origen: {i_diff.source_columns}")
                    if i_diff.target_columns:
                        print(f"      Destino: {i_diff.target_columns}")

            # Foreign keys
            if t_diff.fk_diffs:
                print(f"  Foreign keys modificadas:")
                for fk_diff in t_diff.fk_diffs:
                    print(f"    - {fk_diff.fk_name}: {fk_diff.status}")

            # Comentarios
            if t_diff.comment_diffs:
                print(f"  Comentarios modificados:")
                for cm_diff in t_diff.comment_diffs:
                    if cm_diff.column_name:
                        print(f"    - Colummna '{cm_diff.column_name}':")
                    else:
                        print(f"    - Tabla '{cm_diff.object_name}':")
                    print(f"      Origen: {cm_diff.source_comment}")
                    print(f"      Destino: {cm_diff.target_comment}")

    # ---- VISTAS ----
    if diff.view_diffs:
        print("\n" + "-" * 60)
        print("VISTAS")
        print("-" * 60)

        for v_diff in diff.view_diffs:
            status_icon = {
                "added": "➕",
                "removed": "➖",
                "modified": "🔧",
            }.get(v_diff.status, "❓")

            print(f"\n{status_icon} {v_diff.view_name} ({v_diff.status})")
            if v_diff.source_definition:
                print(f"  Origen: {v_diff.source_definition[:80]}...")
            if v_diff.target_definition:
                print(f"  Destino: {v_diff.target_definition[:80]}...")

    print("\n" + "=" * 60)

# Uso
if __name__ == "__main__":
    SOURCE_DB = "postgresql://user:pass@localhost/db_development"
    TARGET_DB = "postgresql://user:pass@prod-server/db_production"

    compare_databases(SOURCE_DB, TARGET_DB)
```

**Salida esperada:**
```
============================================================
COMPARATIVA DE ESQUEMAS
============================================================

Origen: postgresql://localhost/db_development
Destino: postgresql://prod-server/db_production

Resumen: tablas=3 (0 añadidas, 0 eliminadas, 2 modificadas), ...

------------------------------------------------------------
TABLAS
------------------------------------------------------------

✅ users (unmodified)

🔧 products (modified)
  Columnas modificadas:
    - price: type
      Origen: NUMERIC(10, 2)
      Destino: NUMERIC(12, 2)
    - status: nullable
      Origen: False
      Destino: True

  Índices modificados:
    - idx_product_sku: removed

➕ audit_log (added)
```

---

## Referencia de API

### `SchemaComparator.compare()`

**Firma:**
```python
def compare(
    self,
    source: Inspector,           # SQLAlchemy Inspector de BD origen
    target: Inspector,           # SQLAlchemy Inspector de BD destino
    *,
    source_schema: str | None = None,      # Schema origen (None = default)
    target_schema: str | None = None,      # Schema destino
    include_tables: bool = True,           # Comparar tablas y columnas
    include_views: bool = True,            # Comparar vistas
    include_indices: bool = True,          # Comparar índices
    include_foreign_keys: bool = True,     # Comparar foreign keys
    include_comments: bool = True,         # Comparar comentarios
    include_routines: bool = False,        # Comparar procedures/functions
) -> SchemaDiff:
```

**Parámetros:**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `source` | `Inspector` | Inspector de SQLAlchemy del schema origen |
| `target` | `Inspector` | Inspector de SQLAlchemy del schema destino |
| `source_schema` | `str \| None` | Nombre del schema en la BD origen (requerido en Oracle, opcional en MariaDB) |
| `target_schema` | `str \| None` | Nombre del schema en la BD destino |
| `include_tables` | `bool` | Incluir comparación de tablas y columnas |
| `include_views` | `bool` | Incluir comparación de vistas |
| `include_indices` | `bool` | Incluir comparación de índices |
| `include_foreign_keys` | `bool` | Incluir comparación de FK |
| `include_comments` | `bool` | Incluir comparación de comentarios |
| `include_routines` | `bool` | Incluir comparación de procedures/functions (soporte limitado) |

**Retorna:** `SchemaDiff` — Objeto con todas las diferencias encontradas.

---

### Modelo `SchemaDiff`

```python
@dataclass(frozen=True)
class SchemaDiff:
    source_label: str                    # Etiqueta del origen
    target_label: str                    # Etiqueta del destino
    table_diffs: tuple[TableDiff, ...]   # Diferencias de tablas
    view_diffs: tuple[ViewDiff, ...]     # Diferencias de vistas
    routine_diffs: tuple[RoutineDiff, ...]  # Diferencias de routines
    summary: str                         # Resumen de cambios
```

---

### Modelos de Diferencias

#### `TableDiff`
```python
@dataclass(frozen=True)
class TableDiff:
    table_name: str
    status: Literal["added", "removed", "modified", "unmodified"]
    column_diffs: tuple[ColumnDiff, ...] = ()
    index_diffs: tuple[IndexDiff, ...] = ()
    fk_diffs: tuple[ForeignKeyDiff, ...] = ()
    comment_diffs: tuple[CommentDiff, ...] = ()
```

#### `ColumnDiff`
```python
@dataclass(frozen=True)
class ColumnDiff:
    column_name: str
    attribute: str  # "type", "nullable", "default", "autoincrement"
    source_value: str  # Valor en origen
    target_value: str  # Valor en destino
```

#### `IndexDiff`
```python
@dataclass(frozen=True)
class IndexDiff:
    index_name: str
    table_name: str
    status: Literal["added", "removed", "modified"]
    source_columns: str | None  # "col1, col2"
    target_columns: str | None
    source_is_unique: bool = False
    target_is_unique: bool = False
```

#### `ForeignKeyDiff`
```python
@dataclass(frozen=True)
class ForeignKeyDiff:
    fk_name: str
    table_name: str
    status: Literal["added", "removed", "modified"]
    source_columns: str | None  # "col1, col2"
    target_columns: str | None
    source_referred_table: str | None
    target_referred_table: str | None
    source_referred_columns: str | None
    target_referred_columns: str | None
```

#### `ViewDiff`
```python
@dataclass(frozen=True)
class ViewDiff:
    view_name: str
    status: Literal["added", "removed", "modified"]
    source_definition: str | None  # Definición SQL
    target_definition: str | None
```

#### `CommentDiff`
```python
@dataclass(frozen=True)
class CommentDiff:
    object_name: str       # Nombre de tabla o set column
    column_name: str | None  # None si es comentario de tabla
    source_comment: str
    target_comment: str
```

---

## Soporte por Motor

| Motor      | Tablas | Columnas | Índices | FK | Vistas | Comments | Routines |
|------------|--------|----------|---------|----|----|----------|----------|
| PostgreSQL | ✅     | ✅       | ✅      | ✅ | ✅ | ✅       | ✅       |
| MariaDB    | ✅     | ✅       | ✅      | ✅ | ✅ | ✅       | ✅       |
| SQLite     | ✅     | ✅       | ✅      | ✅ | ✅ | ⚠️ (limitado) | ❌ |
| Oracle     | ✅     | ✅       | ✅      | ✅ | ✅ | ✅       | ✅       |
| SQL Server | ✅     | ✅       | ✅      | ✅ | ✅ | ✅       | ✅       |
| HSQLDB     | ✅     | ✅       | ✅      | ✅ | ✅ | ⚠️ (limitado) | ✅ |

**Leyenda:**
- ✅ Totalmente soportado
- ⚠️ Soporte parcial/limitado
- ❌ No soportado

---

## Casos de Uso Avanzados

### Comparar Múltiples Schemas en PostgreSQL

```python
from sqlalchemy import create_engine, inspect
from util_bbdd.comparar import SchemaComparator

engine = create_engine("postgresql://user:pass@localhost/db")
inspector = inspect(engine)

comparator = SchemaComparator()

# Obtener todos los schemas
schemas = inspector.get_schema_names()

# Comparar schema 'public' vs 'staging'
diff = comparator.compare(
    source=inspector,
    target=inspector,
    source_schema="public",
    target_schema="staging",
)

for table_diff in diff.table_diffs:
    print(f"{table_diff.table_name}: {table_diff.status}")
```

---

### Comparar entre Diferentes Motores

```python
from sqlalchemy import create_engine, inspect
from util_bbdd.comparar import SchemaComparator

# PostgreSQL
postgres_engine = create_engine("postgresql://user:pass@localhost/db_pg")
postgres_inspector = inspect(postgres_engine)

# SQLite
sqlite_engine = create_engine("sqlite:///db.sqlite")
sqlite_inspector = inspect(sqlite_engine)

# Comparar (las diferencias de tipos se normalizarán)
comparator = SchemaComparator()
diff = comparator.compare(
    source=postgres_inspector,
    target=sqlite_inspector,
)

# Notar: tipos VARCHAR vs TEXT, etc., aparecerán como "modified"
for col_diff in [cd for t in diff.table_diffs for cd in t.column_diffs]:
    print(f"{col_diff.column_name}: {col_diff.source_value} → {col_diff.target_value}")
```

---

### Excluir Vistas y Routines

```python
diff = comparator.compare(
    source=source_inspector,
    target=target_inspector,
    include_tables=True,
    include_views=False,        # Ignorar vistas
    include_indices=True,
    include_foreign_keys=True,
    include_comments=True,
    include_routines=False,     # Ignorar routines
)
```

---

### Exportar Resultados a JSON

```python
import json
from dataclasses import asdict

diff = comparator.compare(source_inspector, target_inspector)

# Convertir a dict (requiere conversión de dataclasses)
result = {
    "source": diff.source_label,
    "target": diff.target_label,
    "summary": diff.summary,
    "tables": [asdict(td) for td in diff.table_diffs],
}

print(json.dumps(result, indent=2))
```

---

## Errores Comunes y Soluciones

### Error: "No such table: sqlite_master" (SQLite)

**Causa:** Intento de comparar BD SQLite cerrada o inexistente.

**Solución:**
```python
from sqlalchemy import create_engine, inspect

# ✅ Usar path válido
engine = create_engine("sqlite:///existing_db.db")
inspector = inspect(engine)

# ❌ Evitar indefinido
# engine = create_engine("sqlite:///")  # BD no existe
```

---

### Error: "no schema has been selected to set search_path to" (PostgreSQL)

**Causa:** Schema por default no definido en conexión.

**Solución:**
```python
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    connect_args={"options": "-c search_path=public"}
)
inspector = inspect(engine)

diff = comparator.compare(
    source=inspector,
    target=inspector,
    source_schema="public",  # ← Especificar explícitamente
)
```

---

### Error: "ORA-00600: internal error" (Oracle)

**Causa:** Acceso a routines con privilegios insuficientes.

**Solución:**
```python
# Desactivar comparación de routines
diff = comparator.compare(
    source=oracle_inspector,
    target=oracle_inspector,
    include_routines=False,  # ← Esto
)
```

---

## Próximos Pasos

- Consulta [INSTALLATION.md](INSTALLATION.md) para instalar drivers específicos
- Lee [EXCEPTIONS.md](EXCEPTIONS.md) para manejo de errores
- Explora [Quick Start](index.md#quick-start-5-minutos) para ejemplos básicos
