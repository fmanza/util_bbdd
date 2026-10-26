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
