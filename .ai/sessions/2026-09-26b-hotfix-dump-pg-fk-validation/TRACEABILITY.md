# TRACEABILITY

## Session metadata
- id: 2026-09-26b-hotfix-dump-pg-fk-validation
- fecha: 2026-09-26
- rama: develop (base `ea6e2c9`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-04 (ALTA, integridad) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.5

## Prompt issued
```
/hotfix PD-04: en PostgreSQL, ConstraintManager desactiva las FKs con DISABLE TRIGGER ALL y al rehabilitar ejecuta
VALIDATE CONSTRAINT, que es un no-op porque la FK sigue marcada como válida; el informe la da por 'enabled' aunque haya
filas huérfanas. Criterios: con una fila huérfana, ConstraintResult 'failed'; coste < 2 % del total a 3,5M filas.
```

## RCA
- `_disable_postgresql` usa `ALTER TABLE … DISABLE TRIGGER ALL`: desactiva los triggers de integridad referencial, pero no cambia `pg_constraint.convalidated` (sigue `true`).
- `_enable_postgresql` → `_validate_fks_pg` ejecuta `ALTER TABLE … VALIDATE CONSTRAINT`, que solo recorre la tabla si la FK está `NOT VALID`. Con `convalidated = true` termina al instante sin comprobar nada y el resultado sale `enabled`.
- Reproducido en PostgreSQL real con `DumpOrchestrator`: origen sin FK con una fila huérfana → destino con la FK, 1 fila huérfana cargada y resultado `enabled`.

## FIX (mínimo)
- `dump/_constraints.py`: `_find_fk_orphan_pg` (nuevo) busca, dentro del mismo savepoint y tras el `VALIDATE` de siempre (que sí trabaja si la FK ya era `NOT VALID`), una fila de la hija que incumpla la FK: `SELECT 1 FROM hija c WHERE <columnas FK> IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE …) LIMIT 1`. Si la encuentra, el `ConstraintResult` sale `failed` con el mensaje.
- La definición de la FK sale de `pg_constraint`: tabla referenciada como `confrelid::regclass::text` (citada y con esquema si no está en el `search_path`) y columnas con `quote_ident`, en el orden de la constraint. No se usa `referred_schema` del Inspector, que depende del `search_path`.
- Semántica `MATCH SIMPLE` (la de por defecto): una fila con alguna columna de la FK a NULL cumple.
- **Descartado**: `DROP` + `ADD CONSTRAINT … NOT VALID` + `VALIDATE`. Dejaría el catálogo coherente cuando la validación falla (la FK quedaría `NOT VALID`), pero reconstruye la constraint con DDL: más riesgo del que admite un hotfix. Queda anotado en el mensaje de error que la FK sigue marcada como válida.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests** (`tests/unit/dump/test_constraints.py`): `test_enable_fk_with_orphan_rows_returns_failed` y `test_orphan_query_uses_all_fk_columns_and_skips_nulls` (FK de dos columnas con identificadores citados y esquema). Los dos fallan sin el arreglo. `test_enable_validates_fk_constraints` simula ahora la respuesta del catálogo.
- **Calidad**: `ruff check` limpio; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4522 passed**.
- **PostgreSQL real** (esquemas `zz_pd04_src`/`zz_pd04_dst`, borrados al terminar; origen sin FK, destino con FK; filas `(1,1)`, `(2,NULL)`, `(3,99 | 2)`):

| Caso | Huérfanas en destino | Sin el arreglo | Con el arreglo |
|---|---|---|---|
| Con fila huérfana | 1 | `enabled` | **`failed`** («Hay filas en 'child' que no cumplen la FK 'fk_child_parent'…») |
| Sin huérfanas (con una fila NULL) | 0 | `enabled` | `enabled` |

- **Coste** (`large`, 3,5M filas, 3 repeticiones; `results/`): `constraints_enable` 0,05 → **0,26–0,28 s** (2 FKs, 3M filas hijas; anti-join hash paralelo). Total 16,1–16,4 s (antes 16,4 s): **1,7 % del total**, criterio < 2 % cumplido. Medido en el flujo real, con las tablas recién cargadas.

## AUDIT_CODE
- **Datos limpios**: mismo resultado que antes (`enabled`), un anti-join más por FK.
- **Con huérfanas**: `failed` en lugar de `enabled`. La FK sigue activa para filas nuevas, pero `convalidated` sigue `true` en el catálogo; el mensaje lo dice. Comparación: SQL Server (`WITH CHECK`) y Oracle (`ENABLE VALIDATE`) sí dejan la constraint sin validar cuando fallan.
- **Edge cases**: FK de varias columnas (todas en el `NOT NULL` y en el join, test); referenciada en otro esquema (`regclass`); identificadores con mayúsculas o reservados (`quote_ident`); FK `MATCH FULL` se comprueba como `MATCH SIMPLE` (no detecta filas con NULL parcial; poco habitual); FK sin definición en el catálogo (p. ej. borrada durante el volcado) → no se comprueba.
- **Coste en tablas sin índice en la FK de la hija**: el anti-join recorre la hija y hace hash de la padre; no depende del índice de la hija.
- **Seguridad**: los identificadores salen del catálogo ya citados por PostgreSQL; el nombre de la FK va como parámetro.
- **Compatibilidad**: sin cambios de API.

## VERSION
- Commit: `fix(dump): validar de verdad las FK de PostgreSQL al rehabilitarlas (PD-04)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/pg]**: tras `DISABLE TRIGGER ALL`, `VALIDATE CONSTRAINT` no valida nada. La comprobación real es `_find_fk_orphan_pg`. Si se quisiera dejar el catálogo coherente (`NOT VALID` al fallar), hay que reconstruir la FK (`pg_get_constraintdef`) con DDL: decisión aparte.
- **[dump/pg]**: para la tabla referenciada de una FK usa `confrelid::regclass::text`, no `referred_schema` del Inspector.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-10 (DECIMAL de 38 dígitos en SQL Server), PD-09, PD-06 (SQLite con rangos), PD-07.
