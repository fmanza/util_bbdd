# TRACEABILITY

## Session metadata
- id: 2026-05-19g-hotfix-number-pk-v3
- fecha: 2026-05-19
- rama: develop
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- supersede: 2026-05-19f-hotfix-number-pk-v2 (fix anterior aún fallaba en producción)

## Prompt issued
```
Seguimos con el mismo problema, en oracle tenemos una columna PRIMARY KEY que es del tipo
NUMBER solo sin precisión, esto tiene que convertirse en INT(11) como el resto de PRIMARY KEY
y añadirle AUTO_INCREMENT
```

## Evidencia del usuario (Oracle → MariaDB observado)

**Oracle DDL**:
```sql
CREATE TABLE "ACMUFV"."ACM_INTEGRACION" (
  "IDINTEGRACION" NUMBER NOT NULL ENABLE,
  CONSTRAINT "ACM_INTEGRACION_PK" PRIMARY KEY ("IDINTEGRACION")
)
```

**MariaDB generado (incorrecto)**:
```sql
CREATE TABLE `ACM_INTEGRACION` (
  `IDINTEGRACION` DOUBLE NOT NULL COMMENT ...,
  PRIMARY KEY (`IDINTEGRACION`)
```

**MariaDB esperado**:
```sql
CREATE TABLE `ACM_INTEGRACION` (
  `IDINTEGRACION` INT(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`IDINTEGRACION`)
```

## Análisis de los fallos anteriores

### Sesión e (fix 1 — FALLIDO)
Fix en `_transform_column` usando `col.is_primary_key`. Solo funcionaba si `is_primary_key`
estaba seteado antes de llegar al transformer. El test pasaba porque lo seteaba manualmente.

### Sesión f (fix 2 — FALLIDO EN PRODUCCIÓN)
Fix en `_handle_pk_auto_increment` usando `table.primary_key`. Lógica correcta, pero el
debug confirmó que la función SÍ ejecutaba el fix. El problema real: `_transform_table`
iteraba sobre `table.columns` (original) para transformar, pero solo la copia profunda
`new_table.columns` tenía `is_primary_key` normalizado. Como el fix estaba en `_handle_pk_auto_increment`
(post-transform), llegaba tarde para limpiar el `ddl_comment` DOUBLE que ya estaba emitido.
Adicionalmente, la causa real del fallo visible era que la combinación de avisos DOUBLE
y la limpieza incompleta dejaba el tipo sin corrección efectiva en ciertos contextos.

## Causa raíz definitiva

`_transform_table` iteraba:
```python
new_table.columns = [self._transform_column(table.name, col) for col in table.columns]
```
sobre `table.columns` (el IR original). Si `col.is_primary_key` era `False` allí (porque
el IR se construyó sin el extractor Oracle), `_transform_column` nunca lo vería como PK.

La copia profunda `new_table.columns` existe desde el `deepcopy(table)` inicial, pero
no se usaba como fuente de iteración. Al normalizar `is_primary_key` en `new_table.columns`
y luego iterar sobre **esa copia**, el flag llega correcto a `_transform_column`.

## Fix definitivo aplicado

### Cambio 1 — `_transform_table`: normalizar flags + iterar copia

```python
# Antes:
new_table.columns = [self._transform_column(table.name, col) for col in table.columns]

# Después:
pk_set = {n.upper() for n in table.primary_key}
for col in new_table.columns:
    if col.name.upper() in pk_set:
        col.is_primary_key = True
new_table.columns = [self._transform_column(table.name, col) for col in new_table.columns]
```

### Cambio 2 — `_transform_column`: check PK + NUMBER sin precisión

```python
if col.is_primary_key and col.precision is None:
    target_type = "INT"
    ddl_comment = None
```

`_handle_pk_auto_increment` mantiene su fallback del fix `f` como capa de seguridad.

## Validación end-to-end

Input exacto del usuario sin `is_primary_key` seteado:

```
target_type  : INT(11)
auto_increment: True
nullable     : False

CREATE TABLE `ACM_INTEGRACION` (
  `IDINTEGRACION` INT(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`IDINTEGRACION`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Transformer | `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` | Normalización `pk_set` en `_transform_table`; iteración sobre `new_table.columns`; check PK en `_transform_column` |

## Métricas

| Métrica | Valor |
|---|---|
| Tests migrate | 100/100 verdes |
| End-to-end `ACM_INTEGRACION` | `INT(11) NOT NULL AUTO_INCREMENT` ✅ |
| Regresiones | 0 |

## Veredicto final
CLOSED — fix definitivo aplicado en la capa correcta. Tres capas de protección: normalización
de flags en `_transform_table`, check en `_transform_column`, fallback en `_handle_pk_auto_increment`.
