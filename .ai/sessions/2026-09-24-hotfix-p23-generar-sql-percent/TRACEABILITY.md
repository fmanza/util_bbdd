# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p23-generar-sql-percent
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y paso al `/hotfix` de P-23?". Antes se hicieron los commits `527ceb0` y `3e4fbbd` de P-20.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-23)
- `src/util_bbdd/bulk/_support/sql_helpers.py` (`compile_stmt_with_binary_support`)
- SQLAlchemy 2.0.50: `sql/sqltypes.py:245` (`String.literal_processor`), `dialects/mysql/base.py:2646`, `sql/compiler.py:2681/2686/3455/7611/7691` (`_double_percents`), `dialects/mssql/pymssql.py:48` y `postgresql/pg8000.py:404` (lo desactivan)

## AI output summary
- **RCA**:
  - Con paramstyle `format`/`pyformat`, `IdentifierPreparer._double_percents` es True. SQLAlchemy duplica cada `%` en literales de texto (también el de MySQL con barras invertidas), identificadores, `literal_column` y el operador módulo.
  - Con `literal_binds` no quedan placeholders, así que todo `%` del texto final procede de esa duplicación. El fichero se ejecuta sin parámetros y los datos quedaban con `%%`.
- **Alcance**:
  - Afectados: PostgreSQL con psycopg y psycopg2, MySQL/MariaDB con PyMySQL y mysqlclient.
  - No afectados: SQLite, SQL Server (pymssql lo desactiva; pyodbc es `qmark`), Oracle (`named`) y `mariadbconnector` (`qmark`).
- **Fix**: en la vía `literal_binds` de `compile_stmt_with_binary_support`, si `dialect.identifier_preparer._double_percents`, `sql.replace("%%", "%")`. Es la inversa exacta: un dato `"%%"` compila como `"%%%%"` y vuelve a `"%%"`. La vía de respaldo para binarios no se toca: sustituye los valores sin duplicarlos (solo quedarían afectados identificadores con `%`, un caso muy raro).
- **Tests**:
  - `tests/unit/bulk/test_generate_sql_percent.py` (13): INSERT/UPDATE/DELETE compilados con 6 dialectos reales, sin servidor. Fallaban 6 en los dialectos afectados antes del fix.
  - `tests/integration/test_bulk_engines.py::test_generated_sql_keeps_percent_signs`: ejecuta el SQL generado de INSERT y UPDATE (`a%b`, `100%`, `it's %s`, `%%x`, `50% off`, `LIKE 'a%'`…). Con el fix anulado en memoria falla en PostgreSQL, MySQL y MariaDB; con el fix pasa en SQLite, PostgreSQL, MySQL, MariaDB (PyMySQL y `mariadbconnector`) y SQL Server.
- **Hallazgos colaterales**:
  - **P-24 (MEDIA, previo)**: `generate_sql_filename` exige un nombre de BD en la URL. Con Oracle por `?service_name=...` lanza `ValueError`, y como `generar_sql=True` es el valor por defecto, `bulk_insert_from_df(df, tabla)` sin más argumentos falla. El test de P-23 salta Oracle referenciando P-24.
  - **Observación de SQLAlchemy**: en dialectos posicionales (SQLite), `literal_binds` convierte `'%(nombre)s'` en `'?'` dentro de los literales. Excluido de la matriz del test y anotado en la línea base.
- **Validación**:
  - `ruff check src tests` y `mypy src` limpios.
  - Suite sin URLs de servidor: 4550 passed / 68 skipped. Con las URLs del banco, solo los 3 errores conocidos de `test_update_auto_increment_mariadb.py` (el usuario `bench` no tiene `CREATE DATABASE`).
  - Integración 6 motores: 51 passed / 21 skipped.

## AUDIT_CODE
- Regresiones potenciales: ninguna en los dialectos no afectados (el flag es False). En los afectados, el texto generado recupera exactamente los `%` originales.
- Edge cases: `%%` en los datos se conserva; identificadores con `%` también (vía `literal_binds`).
- Compatibilidad: sin cambio de API. Se lee un atributo interno de SQLAlchemy con `getattr(..., False)`.

## Directrices para Futuras IAs
- **[bulk/generar_sql]**: cualquier texto que salga de `compile(literal_binds=True)` para ejecutarse fuera del driver debe deshacer la duplicación de `%` cuando `identifier_preparer._double_percents` es True.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- P-24 y la observación de SQLAlchemy.
