# Progreso y cancelación

`util_bbdd.progress` es el contrato común de las operaciones largas (documentación, grafos, comparación, migración,
volcado y carga bulk) para avisar de su avance y para pararlas de forma cooperativa (v4.1.0). Cada operación lo
acepta con dos parámetros opcionales: `on_progress` (un `ProgressCallback`) y `cancel_token` (un `CancellationToken`).

```python
from util_bbdd.progress import CancellationToken, ProgressEvent

eventos: list[ProgressEvent] = []
token = CancellationToken()
# operacion(..., on_progress=eventos.append, cancel_token=token)
# Desde otro hilo: token.cancel() → la operación para en el siguiente punto seguro y lanza OperationCancelledError
```

- **Progreso**: un evento al empezar cada fase y uno por unidad de trabajo terminada. Un callback que falla se
  registra una vez en el log y deja de llamarse: el progreso nunca hace fallar una operación.
- **Cancelación**: cooperativa. `cancel()` no interrumpe nada; la operación lo comprueba entre unidades de trabajo,
  deja el destino coherente y lanza `OperationCancelledError` (en `util_bbdd.exceptions`).

| Operación (`ProgressEvent.operation`) | Dónde | Fases | Desde |
|---|---|---|---|
| `"documentation"` | `DatabaseDocumentation(on_progress=, cancel_token=)` | `metadata`, `word`, `excel`, `html` | 4.1.0 |
| `"graph"` | `generate_all_tables_graphs_ext(on_progress=, cancel_token=)` | `tables` | 4.1.0 |
| `"compare"` | `SchemaComparator.compare(on_progress=, cancel_token=)` | `metadata`, `tables`, `views`, `routines` | 4.2.0 |
| `"migrate"` | `MigrationPlan.execute(on_progress=, cancel_token=)` | `statements` | 4.3.0 |
| `"dump"` | `DumpOrchestrator.run(on_progress=, cancel_token=)` | `tables`, `rows` | 4.4.0 |
| `"bulk"` | `BulkCrud.bulk_*_from_df(on_progress=, cancel_token=)` y `bulk_*_from_chunks(...)` | `rows` | 4.5.0 |

---

## ProgressEvent

::: util_bbdd.progress.events.ProgressEvent
    options:
      show_source: false
      heading_level: 3

---

## Contrato y cancelación

::: util_bbdd.progress.contracts.ProgressCallback
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.progress.cancellation.CancellationToken
    options:
      show_source: false
      heading_level: 3

---

## Uso dentro de las operaciones

::: util_bbdd.progress.reporter.ProgressReporter
    options:
      show_source: false
      heading_level: 3
