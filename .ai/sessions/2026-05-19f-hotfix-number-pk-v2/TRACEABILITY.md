# TRACEABILITY

## Session metadata
- id: 2026-05-19f-hotfix-number-pk-v2
- fecha: 2026-05-19
- rama: develop
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- supersede: 2026-05-19e-hotfix-number-pk (fix anterior era frágil)

## Prompt issued
```
/hotfix revisa este último cambio, se observa que un campo PRIMARY KEY se convierte a DOUBLE
y no se genera ni INT ni el AUTO_INCREMENT
```

## Diagnóstico del fix anterior (2026-05-19e)

El hotfix previo añadió el guard en `_transform_column`:

```python
if col.is_primary_key and col.precision is None:
    target_type = "INT"
```

**Por qué fallaba en producción**: `col.is_primary_key` solo se setea cuando el IR viene
del `OracleSchemaExtractor`. Cualquier camino que construya `CanonicalColumn` directamente
(IR manual, tests sin extractor, planner no-Oracle) deja `is_primary_key = False` aunque
el campo sí aparezca en `table.primary_key`. El test de la sesión `e` pasaba porque
seteaba `col.is_primary_key = True` manualmente, enmascarando el bug real.

## Causa raíz real

`_handle_pk_auto_increment` usa `table.primary_key` (fuente canónica, siempre correcta),
pero cuando el PK column tiene `target_type = "DOUBLE"`, ejecuta `return` temprano sin
corregir el tipo. La corrección debía estar aquí, no en `_transform_column`.

## Fix aplicado

### Paso 1 — Revertir fix frágil en `_transform_column`

Eliminado el bloque `if col.is_primary_key and col.precision is None` de `_transform_column`.
La lógica NUMBER vuelve al estado previo a la sesión `e`.

### Paso 2 — Fix real en `_handle_pk_auto_increment`

Cuando `base_type not in _INT_TYPES_AUTOINCREMENT`:

```python
oracle_base = pk_col.oracle_type.upper().split("(")[0].strip()
if oracle_base != "NUMBER" or pk_col.precision is not None:
    return
pk_col.target_type = self._with_int_width("INT")
pk_col.ddl_comment = None
pk_col.warnings = [w for w in pk_col.warnings if w.severity != "WARNING"]
```

Usa `table.primary_key` (ya presente en el scope de `_handle_pk_auto_increment`) en lugar
de `col.is_primary_key`. Limpia el aviso DOUBLE y el ddl_comment engañosos.

### Paso 3 — Test corregido

`test_number_no_precision_pk_maps_to_int_not_double` ya **no** setea `col.is_primary_key = True`,
probando el camino real (solo `pk=["ID"]` en la tabla).

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Transformer | `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` | Revierte `_transform_column`; amplía `_handle_pk_auto_increment` (líneas 249-254) |
| Tests | `tests/unit/migrate/test_transformer.py` | `test_number_no_precision_pk_maps_to_int_not_double` sin `col.is_primary_key = True` |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 100 | 100 (0 regresiones) |
| Fix correcto sin extractor | ❌ | ✅ |
| Fix correcto con extractor | ✅ | ✅ |

## Veredicto final
CLOSED — fix real aplicado en la fuente canónica (`table.primary_key`); 100 tests verdes;
el test clave ya no requiere setear `is_primary_key` manualmente.
