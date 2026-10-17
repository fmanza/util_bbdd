# Ejemplo: Auditoría Común de Carga y Volcado

## 1. Contexto del Ejemplo

`bulk`, `dump` y `migrate` emiten sus eventos de auditoría con un modelo común (`AuditEvent`) hacia un mismo destino
(`AuditSink`). Con `JsonLinesAuditSink`, una carga masiva y un volcado posterior quedan en el mismo fichero, una línea
JSON por evento, y los eventos de cada ejecución se pueden separar por su `run_id`.

El ejemplo carga 100 filas con `BulkCrud`, las vuelca a otra base con `DumpOrchestrator` y lee el fichero resultante.
Usa dos ficheros SQLite; no requiere servidor.

## 2. Implementación de Referencia

```python
--8<-- "examples/audit_events.py"
```

## 3. Explicación del Código

- **Un destino para todo**: el mismo `sink` se pasa a `AuditOptions(sink=...)` de `BulkCrud` y a
  `DumpConfig(audit_sink=...)`. Para `migrate`, se pasa a `plan.execute(..., audit_sink=sink)`.
- **CSV heredado**: `AuditOptions(csv_path=...)` mantiene además el CSV de auditoría de `bulk`, con su formato de
  siempre. Los dos son independientes: se puede usar uno solo.
- **`run_id`**: todos los eventos de un volcado llevan `DumpResult.audit_run_id`. Eso incluye las escrituras que el
  volcado hace a través de `bulk` (el evento `bulk` con `run_id` del volcado). La carga del paso 1 tiene su propio
  `run_id`.
- **`rows` en `bulk`**: son las filas **enviadas**, igual que en el CSV.
- **Cierre**: `sink.close()` en un `finally`; después no admite más escrituras.
- **Datos en el fichero**: `message` lleva el texto de los errores, que en un `IntegrityError` incluye valores de
  clave. Trata el fichero como un dato más.

Salida de error: los dos engines se verifican al empezar (bloques «ENGINE READINESS REPORT», ver
[Condiciones del Motor](engine_readiness_advisor.md)) y el volcado avisa de las limitaciones de SQLite como origen.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/audit_events.py

# Ejecución (crea origen.db, destino.db, logs/ y reports/ en el directorio actual)
python docs/examples/audit_events.py
```

Resultado esperado (salida estándar):

```text
carga    bulk  operation  INSERT  clientes filas=100 ok
volcado  bulk  operation  INSERT  clientes filas=100 ok
volcado  dump  table      LOAD    clientes filas=100 ok
volcado  dump  run        DUMP    None filas=100 ok
eventos por origen: {'bulk': 2, 'dump': 2}
```

Además del JSON Lines quedan `logs/auditoria.csv` y el informe `reports/dump_report_<fecha>.xlsx`.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Auditoría centralizada](../functional/audit.md) — qué se audita y para qué
- **Referencia técnica**: [Auditoría centralizada](../api/audit.md) — `AuditEvent`, destinos y equivalencias con
  OpenTelemetry
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — el CSV de auditoría heredado;
  [Volcado de Datos entre Motores](dump_data_export.md) — el volcado entre servidores
