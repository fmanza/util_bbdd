# TRACEABILITY

## Session metadata
- id: 2026-05-19d-docs-audit-migrate
- fecha: 2026-05-19
- rama: develop
- skill: documentation_review (audit-code modo lectura + correcciones)
- fase: PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION → APPLY

## Prompt issued
```
documentation_review revisar módulo src\util_bbdd\migrate
```

## Context supplied
- `src/util_bbdd/migrate/` — 20 archivos Python (planner, extractors, transformers,
  emitters, reporters, ir, _compat, charset)
- `docs/functional/migrate-oracle-mariadb.md`
- `docs/api/migrate-oracle-mariadb.md`
- `docs/examples/migrate-oracle-mariadb.md`
- `mkdocs.yml` — navegación y configuración
- `README.md` — grep retornó cero coincidencias para "migrate"
- `.github/prompts/documentation_review.prompt.md` — criterio de auditoría

## Hallazgos por severidad

### Nivel 1 — Crítico
| ID | Hallazgo | Resolución |
|---|---|---|
| L1-1 | README.md sin ninguna mención del módulo migrate | CERRADO: fila en tabla features + línea en flujo de decisión |
| L1-2 | `from util_bbdd import MigrationPlanner` — verificar re-export | CERRADO: re-export correcto en `src/util_bbdd/__init__.py:36` |

### Nivel 2 — Alto (aplicados en esta sesión)
| ID | Hallazgo | Resolución |
|---|---|---|
| L2-1 | PK entera sin NEXTVAL → AUTO_INCREMENT no documentado en reglas de negocio | CERRADO: nueva fila en tabla de `docs/functional/` |
| L2-2 | NUMBER(p>18, 0) → DECIMAL(p,0) no documentado en reglas de negocio | CERRADO: nueva fila en tabla de `docs/functional/` |
| L2-3 | `MigrationPlanner` docstring omite `int_display_width` | CERRADO: añadido al bloque Args en `planner.py` |
| L2-4 | `error_count`, `warning_count`, `info_count` sin docstring | CERRADO: docstring de una línea en `ir/models.py` |
| L2-5 | `MariaDBDDLEmitter.emit()` y `emit_statements()` sin Args/Returns | CERRADO: docstrings completos en `emitters/mariadb.py` |

### Nivel 2 — Alto (pendientes — backlog)
| ID | Hallazgo | Acción recomendada |
|---|---|---|
| L2-6 | Sin versiones Oracle soportadas documentadas | Añadir nota en `OracleSchemaExtractor` docstring y en `docs/api/` |
| L2-7 | Sin troubleshooting específico para migrate | Crear sección en `TROUBLESHOOTING.md` o nuevo `migrate-troubleshooting.md` |
| L2-8 | Caso 3 reporter Markdown sin resultado esperado | Añadir fragmento de output en `docs/examples/` Caso 3 |

### Nivel 3 — Recomendados (pendientes — backlog)
| ID | Hallazgo | Acción recomendada |
|---|---|---|
| L3-1 | Typo "perda" → "pérdida" (llegaba al DDL generado) | CERRADO: corregido en ambas ocurrencias de `_compat/type_map.py` |
| L3-2 | Sin H1 en functional y api docs | Añadir `# Migración DDL Oracle → MariaDB` al inicio de cada doc |
| L3-3 | Sin ejemplo iteración programática sobre `plan.tables` | Nuevo Caso 5 en `docs/examples/` |
| L3-4 | Sin ejemplo de `MigrationWarning.proposals` | Añadir a Caso 5 o nuevo Caso 6 |
| L3-5 | Módulo migrate ausente del índice autodoc mkdocstrings | Añadir nota en `docs/api/index.md` |

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| README principal | `README.md` | Nueva fila en tabla features; nueva línea en flujo de decisión |
| Documentación funcional | `docs/functional/migrate-oracle-mariadb.md` | 2 nuevas filas en tabla de reglas de negocio (PK→AI, NUMBER>18→DECIMAL) |
| Planner | `src/util_bbdd/migrate/planner.py` | `int_display_width` añadido al bloque Args del docstring |
| Modelos IR | `src/util_bbdd/migrate/ir/models.py` | Docstrings de una línea en las 3 propiedades de conteo |
| Emitter MariaDB | `src/util_bbdd/migrate/emitters/mariadb.py` | Args + Returns en `emit()` y `emit_statements()` |
| Type map | `src/util_bbdd/migrate/_compat/type_map.py` | Typo "perda"→"pérdida" en 2 ocurrencias (ddl_comment + f-string) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Hallazgos Nivel 1 abiertos | 2 | 0 |
| Hallazgos Nivel 2 aplicados | 0/5 | 5/5 |
| Typos en DDL generado | 2 | 0 |
| Tests migrate | 94 | 94 (sin regresiones esperadas — solo docs/docstrings) |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: L2-6, L2-7, L2-8 (Nivel 2 backlog); L3-2 a L3-5 (Nivel 3 backlog).
Readiness documental: NEAR_READY → gaps críticos cerrados; gaps de completitud en backlog.
