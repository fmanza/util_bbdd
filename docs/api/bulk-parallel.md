# API — Carga masiva paralela (`ParallelBulkLoader`)

`ParallelBulkLoader` inserta varias **particiones** de datos en paralelo, una `BulkCrud` por hilo. Es un **mecanismo** agnóstico del origen: cada partición se describe con un *lector* que produce los chunks ya listos para insertar; el llamador decide de dónde salen (p.ej. `pandas.read_sql` con un `WHERE pk BETWEEN` por rango).

Esta separación permite que `util_bbdd.dump` retenga solo la **política** (qué leer, cómo particionar) y delegue el **mecanismo** (hilos + inserción) en `bulk`.

---

## Imports canónicos

```python
from util_bbdd.bulk import ParallelBulkLoader, ParallelLoadResult
```

---

## ParallelBulkLoader

```python
class ParallelBulkLoader:
    def __init__(
        self,
        engine: Engine,
        *,
        chunk_size: int = 5000,
        max_workers: int = 4,
        commit_every_n_chunks: int | None = None,
        audit_csv_path: Path | None = None,
        enable_fast_executemany: bool = True,
    ) -> None: ...

    def load(
        self,
        tabla_destino: str,
        partition_readers: Sequence[Callable[[], Iterable[pd.DataFrame]]],
        *,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> ParallelLoadResult: ...
```

### Parámetros del constructor

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `engine` | `Engine` | — | Engine SQLAlchemy de destino. Debe ser **thread-safe** (lo es por defecto vía pool). |
| `chunk_size` | `int` | `5000` | Filas por lote en cada worker |
| `max_workers` | `int` | `4` | Hilos concurrentes. Debe ser ≥ 1 (`ValueError` si no). Se acota internamente al número de particiones. **El pool del engine debe tener capacidad ≥ `max_workers`.** |
| `commit_every_n_chunks` | `int \| None` | `None` | Propagado a cada `BulkCrud` worker (cadencia de commit) |
| `audit_csv_path` | `Path \| None` | `None` | CSV de auditoría. Las escrituras concurrentes son seguras (lock por-ruta en `bulk.audit`) |
| `enable_fast_executemany` | `bool` | `True` | Propagado a cada worker (SQL Server + pyodbc) |

### `load(...) → ParallelLoadResult`

Carga todas las particiones en `tabla_destino`. Cada `partition_reader` es un `Callable[[], Iterable[pd.DataFrame]]` invocado **dentro de su hilo worker**, que produce los chunks de su partición.

- **Las particiones deben ser disjuntas** (p.ej. rangos de PK no solapados) para que los inserts concurrentes en la misma tabla no colisionen.
- **Best-effort**: un fallo en una partición se captura en `ParallelLoadResult.partition_errors` sin abortar las demás.
- Cada partición se carga con su **propia** `BulkCrud` (no thread-safe) y su propia conexión vía `bulk_insert_from_chunks`.
- Sin particiones (`[]`) → `ParallelLoadResult()` vacío.

---

## ParallelLoadResult

```python
@dataclass
class ParallelLoadResult:
    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)
```

| Atributo | Tipo | Descripción |
|---|---|---|
| `total_rows` | `int` | Suma de filas insertadas en todas las particiones |
| `partition_errors` | `list[str]` | Un mensaje por partición que falló (`"partición {i}: ..."`). Vacío si todo fue bien |

---

## Ejemplo: particionar una tabla por rangos de PK

```python
from pathlib import Path
from sqlalchemy import create_engine, text
import pandas as pd

from util_bbdd.bulk import ParallelBulkLoader

# El pool destino debe tolerar max_workers conexiones concurrentes
target = create_engine("postgresql+psycopg2://user:pw@host/db", pool_size=4, max_overflow=2)
source = create_engine("mssql+pymssql://user:pw@host/db", pool_size=4, max_overflow=2)

# Rangos disjuntos de PK entera (calculados por el llamador = política)
ranges = [(1, 250_000), (250_000, 500_000)]  # (lo, hi_exclusivo)

def make_reader(lo: int, hi: int):
    def _reader():
        sql = "SELECT id, name FROM big_table WHERE id >= :lo AND id < :hi"
        with source.connect() as conn:
            yield from pd.read_sql(text(sql), conn, params={"lo": lo, "hi": hi}, chunksize=10_000)
    return _reader

loader = ParallelBulkLoader(target, chunk_size=10_000, max_workers=2)
result = loader.load("public.big_table", [make_reader(lo, hi) for lo, hi in ranges])

print(f"Filas insertadas: {result.total_rows}")
for err in result.partition_errors:
    print(f"Error: {err}")
```

!!! info "Uso desde el volcado"
    `DumpOrchestrator` usa `ParallelBulkLoader` internamente cuando se configura `DumpConfig.parallel_pk_ranges > 1`: calcula `MIN/MAX` de la PK, divide en rangos contiguos y construye un lector por rango. Ver [Volcado de Datos](dump.md).

!!! warning "Triggers per-fila e integridad"
    Las particiones se insertan concurrentemente y sin orden global garantizado. El destino **no** debe tener triggers per-fila dependientes del orden de inserción. Las particiones disjuntas por PK evitan colisiones de clave.

---

## Ver también

- [CRUD Masivo (`BulkCrud`)](bulk-crud.md) — `bulk_insert_from_chunks` es la primitiva de inserción que usa cada worker
- [Volcado de Datos (`dump`)](dump.md) — orquestador que alimenta `ParallelBulkLoader` con lectores de rango
