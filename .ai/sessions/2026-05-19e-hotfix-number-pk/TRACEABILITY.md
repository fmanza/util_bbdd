# TRACEABILITY

## Session metadata
- id: 2026-05-19e-hotfix-number-pk
- fecha: 2026-05-19
- rama: develop
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued
```
/hotfix en el módulo los NUMBER que son primary key convertir a int
```

## Context supplied
- `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` — transformer Oracle→MariaDB
- `src/util_bbdd/migrate/_compat/type_map.py` — `resolve_number_type()`
- `src/util_bbdd/migrate/ir/models.py` — `CanonicalColumn.is_primary_key`
- `src/util_bbdd/migrate/extractors/oracle.py` — setea `col.is_primary_key = True`
- `tests/unit/migrate/test_transformer.py` — suite transformer (28 tests previos)

## Bug

**Síntoma**: Una columna Oracle `NUMBER` sin precisión explícita (p.ej. `ID NUMBER PRIMARY KEY`)
que es clave primaria se mapeaba a `DOUBLE` en MariaDB, en lugar de `INT`.

**Consecuencia encadenada**: `_handle_pk_auto_increment` rechazaba marcar la columna como
`AUTO_INCREMENT` porque `DOUBLE ∉ _INT_TYPES_AUTOINCREMENT`. El PK quedaba sin AUTO_INCREMENT.

## Causa raíz

En `_transform_column` ([oracle_to_mariadb.py:109](../../../../src/util_bbdd/migrate/transformers/oracle_to_mariadb.py)),
el bloque NUMBER llamaba a `resolve_number_type(None, None, "DOUBLE")` → devolvía `"DOUBLE"` sin
consultar si `col.is_primary_key` era True.

## Fix aplicado

Añadido guard en el bloque NUMBER de `_transform_column`:

```python
if col.is_primary_key and col.precision is None:
    target_type = "INT"
    ddl_comment = None
    # emite MigrationWarning INFO: "NUMBER sin precisión en columna PK inferido como INT"
```

**Alcance del fix**: solo cuando `precision is None` AND `is_primary_key`. Casos con precisión
explícita (NUMBER(10,2), NUMBER(20,0), etc.) permanecen sin cambio.

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Transformer | `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` | Guard PK+NUMBER→INT (líneas 110-119) |
| Tests | `tests/unit/migrate/test_transformer.py` | 2 tests nuevos en `TestPKAutoIncrement` |

## Tests nuevos

| Test | Descripción | Resultado |
|---|---|---|
| `test_number_no_precision_pk_maps_to_int_not_double` | NUMBER sin precisión + PK → INT + AUTO_INCREMENT | PASS |
| `test_number_no_precision_non_pk_still_double` | NUMBER sin precisión + no-PK → DOUBLE (sin cambio) | PASS |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 94 | 96 |
| Tests total suite migrate | 100 | 100 (0 regresiones) |

## Veredicto final
CLOSED — fix mínimo aplicado, 0 regresiones, 2 tests nuevos cubren el caso corregido y el invariante preservado.
