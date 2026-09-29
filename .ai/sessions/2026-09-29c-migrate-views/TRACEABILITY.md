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

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | conversación (veredicto GO) | emitido |
| H7 | `src/util_bbdd/metadata/sqlserver/tables.py`, `src/util_bbdd/migrate/extractors/sqlserver.py`, `src/util_bbdd/migrate/_compat/sql_view_header.py` | completado |
| Tests H7 | `tests/unit/migrate/test_sql_view_header.py`, `tests/unit/migrate/test_sqlserver_extractor.py` | completado |

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
- **[migrate/vistas]**: plan aprobado: `sqlglot` opcional (`util_bbdd[migrate]`, `>=30,<31`), `view_strategy="auto"`
  (transpila si `sqlglot` está instalado), fallback a pass-through; V0 (spike) decide antes de V1 (umbral ≥ 80 % del
  corpus común por par).

## Veredicto final
Veredicto: GO (sesión IN_PROGRESS)
Pendientes al cierre:
- V1 (base + correcciones A + salvaguardas B/D), pendiente de aprobación del usuario tras V0.
- V2 (reescrituras `(+)`, `ROWNUM`, `ILIKE`, agregados de texto) y V3 (`validate_views`, docs).
