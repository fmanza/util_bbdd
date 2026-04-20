# TD-09 — Módulo de comparación de esquemas con SQLAlchemy

**Estado:** CLOSED — implementado en `src/util_bbdd/comparar/` y expuesto en `__init__.py` (2026-04-10)
**Prioridad:** Media
**Módulo destino:** `src/util_bbdd/comparar/`
**Dependencias internas:** `factory/sqlalchemy_engine_factory.py`, `factory/async_sqlalchemy_engine_factory.py`

---

## Problema actual

`comparar/` contiene dos scripts monolíticos (`main_MariaDB.py`, `main_Oracle.py`) con:

- Credenciales hardcodeadas en texto plano.
- Lógica duplicada entre motores (`get_schema_info`, `get_indices`, `get_foreign_keys`, `get_views`, `get_procedures`, `generar_script_sql`).
- Dependencia directa de `pandas` y `sqlalchemy.inspect` sin pasar por las factories existentes.
- Sin `__init__.py` — no es un paquete importable.
- Sin tests.

---

## Objetivo

Reemplazar los scripts legacy por un módulo reutilizable que:

1. **Compare dos esquemas** del mismo motor (misma instancia o instancias distintas) usando `sqlalchemy.inspect` como fuente de metadatos.
2. **Use las factories existentes** (`SQLAlchemyEngineFactory` / `AsyncSQLAlchemyEngineFactory`) para crear los engines, eliminando URLs hardcodeadas.
3. **Sea motor-agnóstico** — la lógica de comparación opera sobre la API de `sqlalchemy.engine.Inspector`, no sobre SQL crudo.
4. **Genere un reporte de diferencias** estructurado (dataclass/dict) consumible por los renderers existentes (Word/Excel/HTML/Markdown).

---

## Arquitectura propuesta

### Patrón: Strategy + Factory

```
comparar/
├── __init__.py
├── contracts.py          # Protocol SchemaComparator
├── comparator.py         # SchemaComparator — lógica central
├── models.py             # Dataclasses: SchemaDiff, TableDiff, ColumnDiff, IndexDiff, etc.
├── engine_provider.py    # Usa SQLAlchemyEngineFactory para crear engines desde conn_params
└── reporters/
    ├── __init__.py
    ├── contracts.py      # Protocol DiffReporter
    ├── excel_reporter.py
    └── text_reporter.py
```

### Flujo

```
conn_params_a, conn_params_b
        │
        ▼
 EngineProvider (usa SQLAlchemyEngineFactory)
        │
        ▼
 Inspector A, Inspector B (sqlalchemy.inspect)
        │
        ▼
 SchemaComparator.compare(inspector_a, inspector_b) → SchemaDiff
        │
        ▼
 DiffReporter.render(schema_diff) → archivo/texto
```

### Contratos clave

```python
class SchemaComparatorProtocol(Protocol):
    def compare(
        self,
        source: Inspector,
        target: Inspector,
        *,
        include_tables: bool = True,
        include_views: bool = True,
        include_indices: bool = True,
        include_foreign_keys: bool = True,
        include_routines: bool = False,
    ) -> SchemaDiff: ...

class DiffReporterProtocol(Protocol):
    def render(self, diff: SchemaDiff, output: Path) -> Path: ...
```

### Modelos de diferencia

```python
@dataclass(frozen=True)
class ColumnDiff:
    column_name: str
    attribute: str        # "type", "nullable", "default", etc.
    source_value: str
    target_value: str

@dataclass(frozen=True)
class TableDiff:
    table_name: str
    status: Literal["added", "removed", "modified"]
    column_diffs: tuple[ColumnDiff, ...] = ()
    index_diffs: tuple[IndexDiff, ...] = ()
    fk_diffs: tuple[ForeignKeyDiff, ...] = ()

@dataclass(frozen=True)
class SchemaDiff:
    source_label: str
    target_label: str
    table_diffs: tuple[TableDiff, ...] = ()
    view_diffs: tuple[ViewDiff, ...] = ()
    summary: str = ""
```

---

## Integración con factories existentes

```python
from util_bbdd.factory import SQLAlchemyEngineFactory

engine_a = SQLAlchemyEngineFactory.create_engine(
    db_type="mariadb", conn_params=params_a, database="DB_A"
)
engine_b = SQLAlchemyEngineFactory.create_engine(
    db_type="mariadb", conn_params=params_b, database="DB_B"
)

inspector_a = sqlalchemy.inspect(engine_a)
inspector_b = sqlalchemy.inspect(engine_b)

diff = SchemaComparator().compare(inspector_a, inspector_b)
```

---

## Principios SOLID

| Principio | Aplicación |
|-----------|-----------|
| **SRP** | `SchemaComparator` solo compara; `DiffReporter` solo renderiza; `EngineProvider` solo crea engines |
| **OCP** | Nuevos reporters (Markdown, HTML) se añaden sin modificar el comparador |
| **LSP** | Cualquier `DiffReporterProtocol` es intercambiable |
| **ISP** | Contratos separados para comparación y reporte |
| **DIP** | El comparador recibe `Inspector` (interfaz SQLAlchemy), no engines concretos |

---

## Qué eliminar

- `comparar/main_MariaDB.py` — reemplazado por el módulo genérico.
- `comparar/main_Oracle.py` — reemplazado por el módulo genérico.
- Todas las credenciales hardcodeadas.

---

## Dependencias

- `sqlalchemy` (ya existente en el proyecto).
- `pandas` — evaluar si es necesario o si los dataclasses son suficientes para el reporte.

---

## Estrategia de tests

- Tests unitarios con `Inspector` mockeado (sin BD real).
- Tests de integración con SQLite in-memory (dos schemas con diferencias conocidas).
- Cobertura mínima: 85%.

---

## Riesgos

- `Inspector` de SQLAlchemy no expone routines (procedures/functions) de forma uniforme entre motores — puede requerir queries complementarias por motor.
- Las diferencias de tipo entre motores (e.g. `VARCHAR(100)` vs `VARCHAR2(100)`) necesitan normalización configurable.
- `pandas` puede ser excesivo si solo se usa para formatear — preferir dataclasses + reporters dedicados.
