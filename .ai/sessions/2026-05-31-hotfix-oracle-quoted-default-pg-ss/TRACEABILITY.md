# TRACEABILITY

## Session metadata
- id: 2026-05-31-hotfix-oracle-quoted-default-pg-ss
- fecha: 2026-05-31
- rama: develop
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

```
El mismo patrón afecta a los emitters de PostgreSQL y SQL Server (misma lógica)
```

(Continuación de la sesión `2026-05-31-hotfix-oracle-quoted-default-mariadb`)

## Context supplied
- `src/util_bbdd/migrate/emitters/postgresql.py` — función `_format_default_postgresql`
- `src/util_bbdd/migrate/emitters/sqlserver.py` — función `_format_default_sqlserver`
- `tests/unit/migrate/test_emitter_postgresql.py` — clase `TestFormatDefaultPostgreSQL`
- `tests/unit/migrate/test_emitter_sqlserver.py` — clase `TestFormatDefaultSQLServer`

## Root cause

Idéntico al hotfix anterior (sesión `2026-05-31-hotfix-oracle-quoted-default-mariadb`):
`_format_default_postgresql` y `_format_default_sqlserver` no tenían el guard para
literales ya entrecomillados. El valor `'6'` procedente de Oracle producía `'''6'''`
en ambos emitters destino.

## Fix aplicado

En `_format_default_postgresql` y `_format_default_sqlserver`, entre el bloque
numérico y el bloque "String literal sin entrecomillar", se añade el mismo guard:

```python
# String literal ya entrecomillado (Oracle almacena DATA_DEFAULT con comillas, p.ej. '6')
if len(v) >= 2 and v.startswith("'") and v.endswith("'"):
    return v
```

## Artefactos generados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Fix emitter PostgreSQL | `src/util_bbdd/migrate/emitters/postgresql.py` | +4 líneas (guard pre-quoted) |
| Fix emitter SQL Server | `src/util_bbdd/migrate/emitters/sqlserver.py` | +4 líneas (guard pre-quoted) |
| Tests PG numérico | `tests/unit/migrate/test_emitter_postgresql.py` | +test `test_oracle_quoted_numeric_default_not_double_quoted` |
| Tests PG string | `tests/unit/migrate/test_emitter_postgresql.py` | +test `test_oracle_quoted_string_default_not_double_quoted` |
| Tests PG vacío | `tests/unit/migrate/test_emitter_postgresql.py` | +test `test_oracle_empty_string_default_preserved` |
| Tests SS numérico | `tests/unit/migrate/test_emitter_sqlserver.py` | +test `test_oracle_quoted_numeric_default_not_double_quoted` |
| Tests SS string | `tests/unit/migrate/test_emitter_sqlserver.py` | +test `test_oracle_quoted_string_default_not_double_quoted` |
| Tests SS vacío | `tests/unit/migrate/test_emitter_sqlserver.py` | +test `test_oracle_empty_string_default_preserved` |

**Tests resultado**: 86/86 passed (`test_emitter_postgresql.py` + `test_emitter_sqlserver.py`);
1333/1333 passed (módulo completo migrate).

## Directrices para Futuras IAs

- **[migrate/emitters] guard pre-quoted completo**: los tres emitters que reciben
  `CanonicalColumn.default` desde Oracle (mariadb, postgresql, sqlserver) tienen el guard
  `startswith("'") and endswith("'")` en su respectiva `_format_default_*`. El emitter
  Oracle no necesita el guard porque no migra desde sí mismo con este patrón.

- **[migrate/emitters] consistencia entre emitters**: cualquier cambio en la lógica de
  `_format_default` de un emitter debe replicarse en los otros tres. El patrón es idéntico
  salvo por las funciones SQL específicas de cada dialecto en los diccionarios de mappings.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. 1333 tests verdes.
