# Migración a v0.6.0

## Resumen

La versión v0.6.0 introduce un cambio estructural en el subsistema de grafos de relaciones y en la forma de representar diagramas en HTML y Word.

## Cambios relevantes

### Configuración anterior

```toml
[imprimir_config.imprimir.grafo]
enabled = true
show_columns = true
first_level_only = true
images_paginated = true
max_subnodes = 10
```

### Configuración nueva

```toml
[imprimir_config.imprimir.grafo]
enabled = true
show_columns = true
max_depth = 3
direction = "both"
images_paginated = true
max_subnodes = 10

[imprimir_config.imprimir.grafo.columns]
mode = "relations"
max_items = 8
show_data_types = false

[imprimir_config.imprimir.grafo.cardinality]
style = "end_markers"
show_constraint_name = false
```

## Equivalencias de migración

- `first_level_only = true` -> `max_depth = 1`
- `first_level_only = false` -> definir explícitamente `max_depth > 1`
- `show_columns = false` -> `grafo.show_columns = false`
- `show_columns = true` -> `grafo.show_columns = true` y ajustar `columns.mode` según el detalle deseado

## Comportamiento por formato

- HTML: genera pestañas por sentido y por nivel
- Word: mantiene imagen por tabla y añade resumen de niveles totales/no visibles
- Graphviz: marca cardinalidad por extremos y resume niveles en el pie del grafo

## Ejemplo completo recomendado

Si necesitas partir de una configuración completa y comentada del contrato `imprimir_config.imprimir`, usa como referencia:

- [docs/examples/imprimir_config_full_example.toml](docs/examples/imprimir_config_full_example.toml)

Ese ejemplo cubre tanto las opciones generales de documentación como el bloque `grafo` y sus subbloques `columns` y `cardinality`.

## Cambios de imports en analysis

- La implementación real del núcleo de grafos vive únicamente en `util_bbdd.analysis.base`.
- La ruta `util_bbdd.bulk.base` fue eliminada en v0.6.0 y ya no existe como alias ni wrapper.

### Import canónico

```python
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase, GraphDocument, LevelDirection
```

### Migración requerida

```python
# Antes
from util_bbdd.bulk.base import DatabaseRelationshipGraphBase

# Después
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase
```

## Recomendación de adopción

1. Migrar primero el bloque `grafo` de configuración.
2. Validar la profundidad con `max_depth = 1` antes de ampliar a varios niveles.
3. Escoger `columns.mode = "relations"` como modo por defecto para esquemas grandes.
