# Migración a la API 5.0

## 1. Objetivo

Adaptar el código que usa `util_bbdd` 4.x a 5.0.0. La 5.0.0 cambia valores por defecto que hasta ahora podían borrar o
sobrescribir datos sin pedirlo. Casi todos se anunciaron en 4.x con un `FutureWarning`: si tu código ya no emite
ninguno con 4.6.0, la mayor parte de esta guía no te afecta.

Para comprobarlo antes de actualizar, ejecuta tus tests con 4.6.0 convirtiendo los avisos en errores:

```bash
python -m pytest -W error::FutureWarning -W error::DeprecationWarning
```

## 2. Qué cambia

| Área | 4.x | 5.0 | Aviso previo |
|---|---|---|---|
| Volcado | `DumpConfig(truncate_target=...)` vale `True` si no se indica: `run()` vacía el destino | Vale `False`: `run()` añade filas sin borrar nada (modo append) | `FutureWarning` desde 4.4.0 |
| Carga masiva | `BulkCrud.bulk_{insert,update,delete}_from_df` sin `generar_sql` ni `dry_run` escribe el SQL y no ejecuta | Ejecuta | `FutureWarning` desde 4.5.0 |
| Documentación | `DatabaseDocumentation` sin `fichero_salida` agrupa en la misma carpeta las generaciones de los 90 s siguientes | Cada generación tiene su carpeta | Ninguno (no es destructivo) |
| Auditoría de bulk | `AuditManager.columnas_auditoria = [...]` cambia la cabecera del CSV | `AttributeError` (solo lectura) | `DeprecationWarning` |
| Conexión MariaDB | `encoding_errors` se acepta (sin efecto) | Se descarta sin aviso; no está en `database_types.json` | `FutureWarning` |

## 3. Volcado: `truncate_target=False` por defecto

Hasta 4.x, un `DumpConfig` sin `truncate_target` vaciaba las tablas del destino antes de cargar. En 5.0 no las toca.

| Tu código en 4.x | Qué pasa en 5.0 | Qué hacer |
|---|---|---|
| `DumpConfig(..., truncate_target=True)` | Igual | Nada |
| `DumpConfig(..., truncate_target=False)` | Igual | Nada |
| `DumpConfig(...)` sin el argumento (con `FutureWarning`) | Ya no vacía el destino: si tenía filas con la misma clave, la carga de esa tabla falla por PK duplicada | Si querías el volcado completo, añade `truncate_target=True` |
| `DumpConfig(..., manage_indexes="all")` sin `truncate_target` | `ValueError: manage_indexes='all' exige truncate_target=True` al construir | Añade `truncate_target=True` |

Antes (4.x, vacía el destino sin decirlo):

```python
from util_bbdd.dump import DumpConfig, DumpOrchestrator

config = DumpConfig(source_engine=origen, target_engine=destino, manage_indexes="all")
DumpOrchestrator(config).run()
```

Después (5.0):

```python
from util_bbdd.dump import DumpConfig, DumpOrchestrator

config = DumpConfig(source_engine=origen, target_engine=destino, manage_indexes="all", truncate_target=True)
DumpOrchestrator(config).run()
```

`DumpConfig` ya no emite el `FutureWarning`, y el campo es un `bool` normal: `dataclasses.fields(DumpConfig)` da
`False` como valor por defecto.

## 4. Carga masiva: `bulk_*_from_df` ejecuta por defecto

Hasta 4.x, `bulk_insert_from_df`, `bulk_update_from_df` y `bulk_delete_from_df` sin `generar_sql` ni `dry_run`
escribían el SQL en `path_sql` y no tocaban la base de datos. En 5.0 **ejecutan**, sin aviso. `dry_run` es el nombre
preferido del modo seco; `generar_sql` se mantiene como alias, sin aviso.

| Tu código en 4.x | Qué pasa en 5.0 | Qué hacer |
|---|---|---|
| `generar_sql=False` o `dry_run=False` | Igual: ejecuta | Nada (puedes quitar el argumento) |
| `generar_sql=True` o `dry_run=True` | Igual: escribe el SQL y no ejecuta | Nada (se prefiere `dry_run=True`) |
| Sin ninguno de los dos (con `FutureWarning`) | **Ejecuta** contra la BD; `path_sql` se ignora | Si querías el fichero SQL, añade `dry_run=True` |
| `generar_sql` y `dry_run` con valores distintos | Igual: `ValueError` | Pasa solo uno |

Antes (4.x, genera el fichero SQL sin decirlo):

```python
crud.bulk_insert_from_df(df, "clientes", path_sql="sql/")
```

Después (5.0, mismo comportamiento):

```python
crud.bulk_insert_from_df(df, "clientes", path_sql="sql/", dry_run=True)
```

`bulk_*_from_chunks` no cambia: siempre ejecutaba.

## 5. Documentación: sin ventana de agrupación por defecto

Hasta 4.x, `DatabaseDocumentation` sin `fichero_salida` reutilizaba durante 90 s el nombre automático
`<bd>-<fecha_hora>`: las generaciones seguidas de la misma base de datos escribían en la misma carpeta, aunque las
lanzaran usuarios o procesos distintos. En 5.0 la ventana por defecto es `0`: cada generación tiene su carpeta. Si dos
caen en el mismo segundo, la segunda lleva el sufijo `-2` (la tercera `-3`…), y no se reutiliza una carpeta que ya
exista en `directorio_salida`.

Este cambio no tuvo `FutureWarning` previo: no borra ni sobrescribe nada, solo crea más carpetas.

| Tu código en 4.x | Qué pasa en 5.0 | Qué hacer |
|---|---|---|
| `fichero_salida=...` | Igual | Nada |
| `batch_window_seconds=N` explícito (también `0`) | Igual | Nada |
| Sin los dos, y cuentas con que varias generaciones seguidas acaben en la misma carpeta | Cada una en su carpeta | Pasa `batch_window_seconds=90` |

## 6. Retiradas: `columnas_auditoria` y `encoding_errors`

Dos cosas que ya avisaban en 4.x desaparecen:

- **`AuditManager.columnas_auditoria`** pasa a ser de solo lectura. Asignarla cambiaba la cabecera del CSV, pero cada
  fila se seguía escribiendo con las 7 columnas fijas y el fichero dejaba de poder leerse. Ahora asignarla da
  `AttributeError`. Leerla sigue igual.
- **`encoding_errors` de MariaDB** deja de ser un parámetro del motor. Nunca tuvo efecto: ningún driver de MariaDB lo
  admite. Se quita de `MariaDBConnectionConfig`, de la validación y de `database_types.json`, que incluye la lista de
  opcionales y la clase del parámetro en `param_kinds`. Si aparece en `conn_params` o en `build_conn_params`, se
  descarta sin aviso, como cualquier parámetro no declarado.

| Tu código en 4.x | Qué pasa en 5.0 | Qué hacer |
|---|---|---|
| `manager.columnas_auditoria = [...]` | `AttributeError` | Quitar la asignación (las columnas son siempre las 7 fijas) |
| `conn_params={..., "encoding_errors": "replace"}` | Se descarta sin aviso | Quitar la clave |
| Un validador propio que acepte solo los parámetros declarados del motor (p. ej. leyendo `database_types.json` o `param_kinds`) | Rechaza `encoding_errors` en conexiones guardadas | Quitar la clave de lo guardado |
