# API Autodoc

Documentación generada automáticamente desde los docstrings del código fuente.

!!! tip "Referencia rápida"
    Para una tabla de métodos y firmas en formato compacto, ver [API Reference](intro.md).

## Módulos disponibles

| Módulo | Descripción |
|--------|-------------|
| [Managers](managers.md) | `SyncDatabaseManager`, `AsyncDatabaseManager` |
| [Comparador](comparator.md) | `SchemaComparator`, modelos `SchemaDiff` |
| [Reporters](reporters.md) | `SchemaDiffReporter`, `HtmlDiffReporter`, `SqlDiffReporter`, `MarkdownDiffReporter`, `ExcelDiffReporter`, `WordDiffReporter` |
| [Bulk Operations](bulk.md) | `BulkCrud`, `ParallelBulkLoader` y auxiliares de `util_bbdd.bulk` |
| [Excepciones](exceptions.md) | `util_bbdd.exceptions`: `DatabaseException` y toda la jerarquía |

---

## Tipos de retorno (`results/`)

Los métodos de `SyncDatabaseManager` y `AsyncDatabaseManager` devuelven estos tipos:

| Tipo | Definición | Uso |
|------|-----------|-----|
| `Row` | `tuple[Any, ...]` | Fila única devuelta por un cursor DB-API |
| `Rows` | `list[Row]` | Colección materializada de filas |
| `RowOrNone` | `Row \| None` | Resultado para operaciones 0/1 fila (`execute_custom_one`) |
| `QueryResult` | `RowOrNone \| Rows` | Unión interna; no usar directamente en código cliente |

**Importación:**
```python
from util_bbdd.results import Row, Rows, RowOrNone, QueryResult, ResultNormalizer
```

---

## Utilidades async (`async_utils`)

### `maybe_await`

Resuelve valores awaitables o directos con una única API. Útil al implementar código
que puede recibir tanto valores síncronos como corutinas.

```python
from util_bbdd.async_utils import maybe_await

async def ejemplo():
    resultado = await maybe_await(alguna_funcion_o_corutina())
```

---

## Capacidades por motor (`core/capabilities`)

### `is_async_supported(db_type)`

Indica si un motor de BD soporta operaciones async:

```python
from util_bbdd.core.capabilities import is_async_supported

is_async_supported("postgresql")  # True
is_async_supported("hsqldb")      # False
is_async_supported("desconocido") # None
```

Motores con soporte async: `mariadb`, `mysql`, `oracle`, `postgresql`, `sqlserver`, `sqlite`.
Sin soporte async: `hsqldb`.
