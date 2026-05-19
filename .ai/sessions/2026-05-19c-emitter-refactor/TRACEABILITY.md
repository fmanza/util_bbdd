# TRACEABILITY

## Session metadata
- id: 2026-05-19c-emitter-refactor
- fecha: 2026-05-19
- rama: develop
- skill: refactor
- fase: IMPLEMENT + AUDIT_CODE (inline)

## Prompt issued
```
src\util_bbdd\migrate\emitters\mariadb.py:
  Refactor this function to reduce its Cognitive Complexity from 29 to the 15 allowed. [+13 locations]
  (función: _topological_sort, selección IDE en línea 201)
```

## Context supplied
- `src/util_bbdd/migrate/emitters/mariadb.py` — `_topological_sort` monolítica con 3 bloques
  anidados (build_deps, Kahn, FK circulares), complejidad acumulada 29 en 13 ubicaciones

## Análisis de complejidad

Las 13 ubicaciones se distribuían así en la función original:

| Ubicación | Profundidad | Contribución |
|---|---|---|
| `for table in tables:` | 0 | +1 |
| `for fk in table.foreign_keys:` | 1 | +2 |
| `if fk.is_external:` | 2 | +3 |
| `if ref in all_names and ref != table.name:` | 2 | +3 |
| `and` | — | +1 |
| `while queue:` | 0 | +1 |
| `for other, other_deps in deps.items():` | 1 | +2 |
| `if name in other_deps:` | 2 | +3 |
| `if in_degree[other] == 0:` | 3 | +4 |
| `for table in circular_tables:` | 0 | +1 |
| `for fk in table.foreign_keys:` | 1 | +2 |
| `if fk.is_external:` | 2 | +3 |
| `if fk.ref_table not in visited:` | 2 | +3 |
| **Total** | | **29** |

## AI output summary

1. `_topological_sort` conserva únicamente la orquestación (complejidad 0):
   - construye `name_to_table`, `all_names`, `in_degree`
   - llama a `_build_deps`, `_kahn_result`, `_collect_circular_fk_pairs`
   - extend de tablas circulares + retorno

2. Extraído `_build_deps(tables, all_names)` (complejidad ≈ 8):
   - `for/for/if` que construye el grafo de dependencias FK internas
   - condición compacta: `not fk.is_external and fk.ref_table in all_names and fk.ref_table != table.name`
   - elimina el `if fk.is_external: continue` como nivel de nesting separado

3. Extraído `_kahn_result(deps, in_degree, name_to_table)` (complejidad ≈ 10):
   - `while/for/if/if` del algoritmo de Kahn intacto
   - recibe `in_degree` ya calculado (no lo computa internamente)

4. Extraído `_collect_circular_fk_pairs(tables, visited)` (complejidad ≈ 2):
   - list comprehension con `not fk.is_external and fk.ref_table not in visited`
   - elimina el bloque `for/for/if/if` original

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Emitter MariaDB | `src/util_bbdd/migrate/emitters/mariadb.py` | `_topological_sort` descompuesta en 3 helpers; comportamiento idéntico |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Complejidad cognitiva `_topological_sort` | 29 | 0 |
| Complejidad cognitiva `_build_deps` | — | ≈ 8 |
| Complejidad cognitiva `_kahn_result` | — | ≈ 10 |
| Complejidad cognitiva `_collect_circular_fk_pairs` | — | ≈ 2 |
| Tests migrate | 94 | 94 (sin regresiones) |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. API pública intacta (`_topological_sort` visible en tests), comportamiento preservado.
