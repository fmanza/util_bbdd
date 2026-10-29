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
