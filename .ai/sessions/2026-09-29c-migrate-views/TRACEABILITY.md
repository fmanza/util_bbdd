# TRACEABILITY

## Session metadata
- id: 2026-09-29c-migrate-views
- fecha: 2026-09-29
- rama: develop (base `07dc250`, v0.19.0)
- skill: new_feature (PLAN + AUDIT_PLAN) + hotfix (H7); V0–V3 pendientes
- fase: PLAN + AUDIT_PLAN (GO) + IMPLEMENT H7

## Prompt issued
```
Dime que estrategia para, Las vistas de migrate/ se siguen copiando sin reescribir el SQL, con aviso de revisión
manual en el plan. No implementar nada
```
Después: «PLAN Y AUDIT_PLAN»; decisiones: «Sqlglot, auto»; «Si» a empezar por H7.

## Context supplied
- Matriz real de 20 pares de `MigrationPlanner` (sesión `2026-09-29b-feature-mysql-pymysql`): las vistas son lo único
  que no se ejecuta en el destino (esquema origen en la definición, backticks, funciones del dialecto).
- `migrate/transformers/_view_rewriter.py` (regex léxicas solo con origen Oracle).

## AI output summary
- Estrategia: transpilar las vistas con `sqlglot` (dependencia opcional) sobre AST, con fallback a pass-through.
- PLAN/AUDIT_PLAN: entregas V0 (spike con corpus y banco, decide), H7, V1 (base `migrate/views/`, `view_strategy`),
  V2 (fixes por dialecto), V3 (`validate_views`, docs). Veredicto GO_CONDICIONAL → **GO** tras las decisiones del
  usuario: `sqlglot` como extra opcional (`>=30,<31`) y `view_strategy="auto"` por defecto.
- H7 confirmado contra SQL Server 2022 antes de planificar: `INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION` incluye la
  cabecera `CREATE VIEW ... AS` y se trunca a 4000 caracteres (vista de 11 523 → 4000); `OBJECT_DEFINITION` la
  devuelve completa.
- **H7** `hotfix(migrate)`: `metadata/sqlserver/tables.fetch_views_sql` usa `sys.views` + `OBJECT_DEFINITION`;
  `migrate/_compat/sql_view_header.split_create_view_header` quita la cabecera (`OR ALTER`, `WITH SCHEMABINDING/
  ENCRYPTION/VIEW_METADATA`, nombres con corchetes/comillas, comentarios previos, `;` final) y devuelve la lista de
  columnas de la cabecera si la hay; el extractor avisa de esa lista y de las definiciones no disponibles (NULL:
  `WITH ENCRYPTION` o sin permiso). Se retira la heurística «4000 caracteres = posible truncado».
- Verificación real (SQL Server 2022 → MySQL 8.4): vista larga completa (11 506 caracteres), sin cabecera; vista
  portable creada en MySQL (antes `CREATE OR REPLACE VIEW v AS CREATE VIEW v AS ...`).
- Calidad: `ruff`/`mypy` limpios; `pytest` 5499 passed / 205 skipped; integración 344 passed.
- **V0** (spike, `v0/V0_SPIKE.md`, `v0/results.json`): `sqlglot` 30.20.0 con 31 construcciones comunes + 7
  específicas, definición leída del catálogo con los extractores de util_bbdd, ejecutada y comparada en el banco.
  Umbral (≥ 80 % se ejecuta) cumplido en 19/20 pares; PostgreSQL → Oracle 74 %. Fallos: A) artefactos del catálogo
  corregibles en el AST (casts `::text` de PG → `CLOB`, `CHAR charset` de MySQL, `to_days` de MySQL, `YEAR` hacia
  Oracle); B) aritmética dependiente del tipo (fechas, `+` de cadenas) con **errores silenciosos** hacia MySQL/MariaDB;
  C) semántica de Oracle (`''` = `NULL`, concatenación con `NULL`); D) `(+)` de Oracle se crea como join interno
  (**silencioso**), `ROWNUM`/`CONNECT BY` fallan al crear. Propuesta: V1 = base + A + salvaguardas B/D; V2 =
  reescrituras.
- **V1** (aprobada con el alcance ampliado): `migrate/views/` (`_dialects.py`: `view_strategy`/`resolve_view_strategy`;
  `_rewrites.py`: correcciones A (`CHAR charset` y `to_days` de MySQL, casts `::text` de PG), B (aritmética de fechas
  con tipos anotados, `x ± INTERVAL`, `+` de cadenas de SQL Server), destino Oracle (texto → `VARCHAR2(4000)`,
  `DATE_ADD`/`DATEDIFF`/`YEAR` → aritmética y `EXTRACT`, sin envoltorios `TIME_STR_TO_TIME`), destino PG
  (`fecha + INTERVAL` → `DATE`) y salvaguardas (`(+)`, `ROWNUM`, `CONNECT BY` → pass-through); `transpiler.py`:
  `qualify` + `annotate_types` con los tipos del plan, nombres del plan con comillas del destino, alias generados
  entrecomillados, avisos INFO/WARNING y pass-through ante cualquier fallo). `MigrationPlanner(view_strategy="auto")`
  y `_transform_views`; extra `util_bbdd[migrate]` (`sqlglot>=30,<31`) y `sqlglot` en `dev`; guía
  `ddl_migration_guide.md` §3.5 (y matriz de motores con MySQL).
- Verificación V1 (`v1/v1_matrix_views.py`, `v1/results.json`): matriz de 20 pares **a través de `MigrationPlanner`**
  (tablas y vistas del plan creadas en el destino, datos copiados, resultados comparados): **100 % de las vistas
  comunes se crean en los 20 pares**; diferencias de resultado solo por semántica de Oracle (c08/c09/c10/c23/c29,
  cadena vacía y concatenación con NULL). `(+)`, `ROWNUM`, `CONNECT BY` → pass-through (fallan de forma visible);
  `ILIKE` → SQL Server y agregados de texto → PG quedan para V2. Iteración: la primera pasada reveló alias generados
  por `qualify` (`AS 1`, `_col_0`), `alta + INTERVAL` de MySQL y `TIME_STR_TO_TIME` de SQL Server hacia Oracle; se
  corrigieron y la segunda pasada dio 100 %.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación (veredicto GO) | emitido |
| H7 | `src/util_bbdd/metadata/sqlserver/tables.py`, `src/util_bbdd/migrate/extractors/sqlserver.py`, `src/util_bbdd/migrate/_compat/sql_view_header.py` | completado |
| Tests H7 | `tests/unit/migrate/test_sql_view_header.py`, `tests/unit/migrate/test_sqlserver_extractor.py` | completado |
| V0 | `v0/V0_SPIKE.md`, `v0/v0_spike_views.py`, `v0/results.json` | completado |
| V1 | `src/util_bbdd/migrate/views/`, `src/util_bbdd/migrate/planner.py`, `pyproject.toml`, `docs/guides/ddl_migration_guide.md` | completado |
| Tests V1 | `tests/unit/migrate/test_view_strategy.py`, `tests/unit/migrate/test_view_transpiler.py` | completado |
| Verificación V1 | `v1/v1_matrix_views.py`, `v1/results.json` | completado |

## Directrices para Futuras IAs
- **[sqlserver/vistas]**: `INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION` trunca a 4000 caracteres también en SQL Server
  2022 e incluye la cabecera `CREATE VIEW`; usar `OBJECT_DEFINITION(object_id)` (NULL si la vista es `WITH ENCRYPTION`
  o falta el permiso `VIEW DEFINITION`) y `split_create_view_header` para quedarse con la query.
- **[migrate/vistas]**: los emitters no emiten lista de columnas en `CREATE VIEW`; una vista SQL Server con
  `CREATE VIEW v (a, b) AS ...` pierde esos nombres (aviso en el plan). Tenerlo en cuenta en V1.
- **[migrate/vistas]**: V0 demostró que «se ejecuta» no basta: `sqlglot` sin tipos convierte `fecha + 30` de
  PG/Oracle en suma numérica en MySQL (`20240140`) y el `(+)` de Oracle en join interno, sin error. Toda activación
  de `auto` requiere anotación de tipos con el esquema del plan y detección de `(+)`/`ROWNUM`/`CONNECT BY`.
- **[migrate/vistas]**: el texto de catálogo no es el SQL escrito: PG añade casts (`::text`), MySQL reescribe
  `CAST(... AS CHAR(n))` con charset y `DATEDIFF` como `to_days(a) - to_days(b)`, SQL Server incluye la cabecera.
  El corpus de pruebas debe leerse del catálogo, no escribirse a mano.
- **[migrate/vistas]**: el transpilador vive en `migrate/views/transpiler.py` y solo se importa si `view_strategy`
  resuelve a `transpile`; `_rewrites.py` concentra las reescrituras AST (una función por problema, documentada con su
  caso de V0). Recorrer los nodos **de abajo arriba** (`reversed(list(find_all(...)))`) al reemplazar operaciones
  anidadas (`a + ' - ' + b`).
- **[migrate/vistas]**: `qualify` de sqlglot añade alias a todas las proyecciones (`SELECT 1 AS 1`, `COUNT(0) AS
  _col_0`): los identificadores no simples se entrecomillan o MySQL/Oracle rechazan la vista.
- **[migrate/vistas]**: nombres del plan (tablas, vistas, columnas) se emiten entrecomillados como los crean los
  emitters (Oracle en mayúsculas); el resto de identificadores sin comillas. Verificar siempre con la matriz real
  (`v1/v1_matrix_views.py`), no solo con la ejecución: la comparación de resultados es la que detecta lo silencioso.
- **[migrate/vistas]**: plan aprobado: `sqlglot` opcional (`util_bbdd[migrate]`, `>=30,<31`), `view_strategy="auto"`
  (transpila si `sqlglot` está instalado), fallback a pass-through; V0 (spike) decide antes de V1 (umbral ≥ 80 % del
  corpus común por par).

## Veredicto final
Veredicto: GO (sesión IN_PROGRESS)
Pendientes al cierre:
- V2: reescrituras `(+)` → `LEFT JOIN`, `ROWNUM` → `FETCH FIRST`/`LIMIT`/`TOP`, `ILIKE` → `LOWER() LIKE`, agregados de
  texto (`STRING_AGG` con cast); lista de columnas de la cabecera de vistas SQL Server.
- V3: `validate_views`, test de integración de la matriz de vistas, documentación funcional/API.
