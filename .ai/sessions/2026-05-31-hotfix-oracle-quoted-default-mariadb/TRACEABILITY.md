# TRACEABILITY

## Session metadata
- id: 2026-05-31-hotfix-oracle-quoted-default-mariadb
- fecha: 2026-05-31
- rama: develop
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

```
en src\util_bbdd\migrate cuando se realiza la migración de Oracle a MariaDB,
se detecta que el valor por defecto viene entre comillado:
Ejemplo: `IDAPLICACION` INT(11) NOT NULL DEFAULT '''6''' y falla al ejecutar
```

## Context supplied
- `src/util_bbdd/migrate/emitters/mariadb.py` — función `_format_default`
- `src/util_bbdd/migrate/extractors/oracle.py` — `default_raw = str(row[4]).strip()`
- `src/util_bbdd/migrate/ir/models.py` — campo `CanonicalColumn.default`
- `tests/unit/migrate/test_emitter.py` — tests previos de DEFAULT

## Root cause

Oracle almacena `DATA_DEFAULT` en `ALL_TAB_COLUMNS` **incluyendo las comillas simples**
cuando el valor por defecto es un literal de texto (p.ej. `'6'`, `'ACTIVO'`).
El extractor Oracle guarda ese valor tal cual en `CanonicalColumn.default`.
`_format_default` en `mariadb.py` recibía `'6'` y, al no reconocerlo como numérico
ni como función SQL, escapaba las comillas internas (`'` → `''`) y envolvía en
comillas externas → `'''6'''`. El DDL resultante fallaba al ejecutar en MariaDB.

## Fix aplicado

En `_format_default` (mariadb.py), entre el bloque numérico y el bloque
"String literal sin entrecomillar", se añade un guard:

```python
# String literal ya entrecomillado (Oracle almacena DATA_DEFAULT con comillas, p.ej. '6')
if len(v) >= 2 and v.startswith("'") and v.endswith("'"):
    return v
```

El valor se devuelve tal cual, sin doble escape.

## Artefactos generados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Fix emitter MariaDB | `src/util_bbdd/migrate/emitters/mariadb.py` | +4 líneas (guard pre-quoted) |
| Test regresión numérico | `tests/unit/migrate/test_emitter.py` | +test `test_oracle_quoted_numeric_default_not_double_quoted` |
| Test regresión string | `tests/unit/migrate/test_emitter.py` | +test `test_oracle_quoted_string_default_not_double_quoted` |
| Test regresión vacío | `tests/unit/migrate/test_emitter.py` | +test `test_oracle_empty_string_default_preserved` |

**Tests resultado**: 28/28 passed (`test_emitter.py`); 1327/1327 passed (módulo completo migrate).

## Directrices para Futuras IAs

- **[migrate/extractors/oracle.py] DATA_DEFAULT con comillas**: Oracle almacena el valor
  `DATA_DEFAULT` de `ALL_TAB_COLUMNS` incluyendo las comillas simples cuando es un literal
  de texto. `CanonicalColumn.default` recibe `'6'` (con comillas), no `6`. Los emitters
  deben detectarlo con `startswith("'") and endswith("'")` y devolverlo sin re-entrecomillar.

- **[migrate/emitters] guard pre-quoted**: el guard está en los tres emitters que reciben
  data de Oracle (mariadb, postgresql, sqlserver). Si se añade un nuevo emitter destino
  desde Oracle, incluir el mismo guard en `_format_default_*`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. 1327 tests verdes.
