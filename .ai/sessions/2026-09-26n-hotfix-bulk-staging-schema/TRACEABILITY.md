# TRACEABILITY

## Session metadata
- id: 2026-09-26n-hotfix-bulk-staging-schema
- fecha: 2026-09-26
- rama: develop (base `e3d7449`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-12, detectado al validar PF-09 (`2026-09-26m-feature-mariadb-connector-executemany`)

## Prompt issued
```
/hotfix PD-12: en MySQL/MariaDB, bulk_update_from_df por staging crea la tabla temporal sin esquema; sin base de datos
por defecto en la conexión y con la tabla destino como esquema.tabla falla con "No database selected" (1046), con
PyMySQL y con Connector/Python. Criterios: UPDATE correcto en los cuatro casos (con/sin BD por defecto × ambos drivers);
test.
```

## RCA
- `MySQLStagingUpdateStrategy.execute` crea `Table(f"tmp_bulkupd_…", MetaData(), …, prefixes=["TEMPORARY"])` **sin `schema`**, aunque la tabla destino (`self._table`) lo tenga.
- Si la conexión no tiene base de datos por defecto (URL sin `database`), `CREATE TEMPORARY TABLE tmp_bulkupd_…` no sabe dónde crearla: error 1046. Con base de datos por defecto funcionaba (la temporal se creaba allí y el `UPDATE … JOIN` cualificaba la destino).
- Reproducido en MariaDB 11.4 con PyMySQL y con Connector/Python (sesión PF-09). No depende del driver.

## FIX (mínimo)
- `bulk/_execution/batch.py`: la tabla temporal se crea con `schema=self._table.schema`. El `CREATE`, la carga (`insert(staging)`), el `UPDATE … JOIN` y el `DROP TEMPORARY TABLE` usan esa `Table` y quedan cualificados. Sin esquema en la destino, la temporal tampoco lo tiene (como antes).
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Test**: `tests/unit/bulk/test_staging_update.py::test_staging_table_uses_the_schema_of_the_target_table` (temporal con el esquema de la destino; `UPDATE dst.t, dst.tmp_… … WHERE dst.t.id = dst.tmp_….id`; `DROP TEMPORARY TABLE IF EXISTS dst.tmp_…`). Falla sin el arreglo. `test_creates_loads_updates_and_drops_the_staging_table` (sin esquema) sigue igual.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4570 passed**.
- **Servidores reales** (`bulk_update_from_df` de 2 filas, tabla `zz_pd12` borrada al terminar):

| Driver / motor | Sin BD por defecto, `esquema.tabla` | BD por defecto, `tabla` |
|---|---|---|
| MariaDB 11.4 + PyMySQL | OK (antes `No database selected`) | OK |
| MariaDB 11.4 + Connector/Python | OK (antes `No database selected`) | OK |
| MySQL 8.4 + PyMySQL | OK | OK |

## AUDIT_CODE
- **Sin esquema**: comportamiento idéntico (test existente).
- **Con esquema y BD por defecto distinta**: la temporal va al esquema de la destino, no a la BD por defecto; el `UPDATE … JOIN` ya cualificaba ambas.
- **Colisiones**: nombre aleatorio (`uuid`), y una temporal oculta a una tabla real del mismo nombre solo en esa sesión.
- **Privilegios**: `CREATE TEMPORARY TABLES` en el esquema de la destino (antes, en la BD por defecto); la vía de fallback por privilegio denegado no cambia.
- **Compatibilidad**: sin cambios de API.

## VERSION
- Commit: `fix(bulk): tabla temporal del UPDATE por staging en el esquema de la destino (PD-12)`
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[bulk/mysql]**: toda tabla auxiliar (temporal o de staging) debe crearse en el esquema de la tabla destino; no asumas que la conexión tiene base de datos por defecto (el banco de `dump` conecta sin ella).

## Veredicto final
Veredicto: CLOSED
