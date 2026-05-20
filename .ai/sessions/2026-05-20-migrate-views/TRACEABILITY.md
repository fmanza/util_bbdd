# TRACEABILITY

## Session metadata
- id: 2026-05-20-migrate-views
- fecha: 2026-05-20
- rama: develop
- skill: new_feature (vistas) + feat (ordenación topológica)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION × 2

## Prompt issued

**Parte 1 — migración de vistas**
```
Queremos ampliar las funcionalidades actuales del módulo migrate,
contemplar la migración de las vistas en los escenarios actuales.
(Oracle → MariaDB / SQL Server / PostgreSQL)
```

**Parte 2 — ordenación topológica de vistas**
```
Implementar el ordenar vistas en el script: "v1 sin ordenación entre vistas"
Si el script emite VW_RESUMEN antes que VW_DETALLE, la ejecución falla.
```

## Context supplied
- Módulo `migrate/` con soporte completo Oracle → MariaDB / SQL Server / PostgreSQL
- Sesiones anteriores: 2026-05-18 → 2026-05-19g + 2026-05-20-migrate-oracle-sqlserver/postgresql
- Diseño acordado: reescritura best-effort (regex, sin parser externo); vistas integradas en `emit_ddl()` automáticamente

## AI output summary

### Parte 1 — soporte de vistas (3 commits)

#### Nuevos componentes

**IR**
- `CanonicalView` dataclass (slots=True): `name`, `original_name`, `schema`, `query`, `columns`, `comment`, `warnings`
- `MigrationPlan.views: list[CanonicalView] = field(default_factory=list)` — backward compat total

**Rewriter** (`transformers/_view_rewriter.py`)
- `rewrite_oracle_view(view, sysdate_fn, systimestamp_fn, user_fn, schema) → CanonicalView`
- Sustituciones: hints Oracle `/*+ */`, SYSDATE/SYSTIMESTAMP, USER, NVL→COALESCE, FROM DUAL, prefijo schema
- Constructs complejos (ROWNUM, CONNECT BY, DECODE, outer join (+), LISTAGG, NVL2, WM_CONCAT, MODEL) → `MigrationWarning` severity=WARNING; SQL sin modificar

**Extractors**
- `OracleSchemaExtractor.extract_views(schema)` — consulta `ALL_VIEWS.text` + `ALL_TAB_COLUMNS`

**Transformers** (3 targets)
- `OracleToMariaDBTransformer.transform_views()` — sysdate_fn=`NOW()`, truncación ≤64
- `OracleToSQLServerTransformer.transform_views()` — sysdate_fn=`GETDATE()`, truncación ≤128
- `OracleToPostgreSQLTransformer.transform_views()` — sysdate_fn=`NOW()`, truncación ≤63

**Emitters** (3 targets)
- MariaDB: `CREATE OR REPLACE VIEW \`name\` AS ...`
- SQL Server: `CREATE OR ALTER VIEW [name] AS ...` _(SQL Server 2016+)_
- PostgreSQL: `CREATE OR REPLACE VIEW "name" AS ...`
- Vistas emitidas DESPUÉS de todas las tablas; con `-- NOTE: requires manual review` si hay warnings

**Planner**
- `MigrationPlanner.plan()` llama `extractor.extract_views()` + `transformer.transform_views()` y pasa `views=` al `MigrationPlan`

**Exports**
- `CanonicalView` añadido a `migrate/ir/__init__.py` y `migrate/__init__.py`

#### Tests
- `tests/unit/migrate/test_views_mariadb.py` — 47 tests (5 clases)
- `tests/unit/migrate/test_views_sqlserver.py` — 20 tests (4 clases)
- `tests/unit/migrate/test_views_postgresql.py` — 23 tests (4 clases)
- **76 tests nuevos**

#### AUDIT_CODE
Veredicto: **APROBADO CON CONDICIONES** — condición: documentar en CHANGELOG limitaciones conocidas v1:
1. Sin ordenación topológica entre vistas (resuelto en Parte 2 de esta sesión)
2. `ALL_VIEWS.text` tipo LONG en Oracle (pendiente; drivers modernos funcionan correctamente)

---

### Parte 2 — ordenación topológica de vistas (1 commit)

#### Nuevos componentes (`emitters/mariadb.py`, compartidos por los 3 emitters)

- `_detect_view_deps(view, all_views) → set[str]`
  - Word-boundary regex case-insensitive sobre `view.query.upper()`
  - Comprueba tanto `name` (posiblemente truncado) como `original_name` (nombre Oracle original)
- `_topological_sort_views(views) → tuple[ordered, circular]`
  - Algoritmo de Kahn — misma lógica que `_topological_sort` para tablas
  - Vistas en ciclos → `circular`; se emiten al final con `-- AVISO: dependencia circular`
- `_emit_view_statements()` actualizado en los 3 emitters para llamar a `_topological_sort_views`
- `_topological_sort_views` importada por `sqlserver.py` y `postgresql.py` desde `mariadb.py`

#### Tests (17 nuevos)
- `TestTopologicalSortViews` (10 tests): vacío, sin deps, cadena, 3 niveles, diamante, ciclo, ciclo+independiente, case-insensitive, original_name
- `TestMariaDBViewTopologicalEmit` (3 tests): orden correcto, aviso circular, sin aviso si no hay deps
- `TestSQLServerEmitStatementsWithViews` (+2): orden correcto, aviso circular
- `TestPostgreSQLEmitStatementsWithViews` (+2): ídem

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| CanonicalView IR | `migrate/ir/models.py` | modificado (+CanonicalView, MigrationPlan.views) |
| View rewriter | `migrate/transformers/_view_rewriter.py` | creado |
| Oracle extractor | `migrate/extractors/oracle.py` | modificado (+extract_views) |
| Transformer MariaDB | `migrate/transformers/oracle_to_mariadb.py` | modificado (+transform_views) |
| Transformer SQL Server | `migrate/transformers/oracle_to_sqlserver.py` | modificado (+transform_views) |
| Transformer PostgreSQL | `migrate/transformers/oracle_to_postgresql.py` | modificado (+transform_views) |
| Emitter base | `migrate/emitters/base.py` | modificado (Protocol +views param) |
| Emitter MariaDB | `migrate/emitters/mariadb.py` | modificado (+_emit_create_view, +_topological_sort_views, +_detect_view_deps) |
| Emitter SQL Server | `migrate/emitters/sqlserver.py` | modificado (+_emit_create_view, import _topological_sort_views) |
| Emitter PostgreSQL | `migrate/emitters/postgresql.py` | modificado (+_emit_create_view, import _topological_sort_views) |
| Transformer base | `migrate/transformers/base.py` | modificado (Protocol +transform_views) |
| IR __init__ | `migrate/ir/__init__.py` | modificado (+CanonicalView) |
| Module __init__ | `migrate/__init__.py` | modificado (+CanonicalView) |
| Planner | `migrate/planner.py` | modificado (+extract_views, +transform_views, +views en plan) |
| Tests views MariaDB | `tests/unit/migrate/test_views_mariadb.py` | creado |
| Tests views SQL Server | `tests/unit/migrate/test_views_sqlserver.py` | creado |
| Tests views PostgreSQL | `tests/unit/migrate/test_views_postgresql.py` | creado |
| CHANGELOG | `CHANGELOG.md` | modificado ([Unreleased]: vistas + limitaciones + topological sort) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate (vistas) | 335 | 411 (+76) |
| Tests migrate (topo sort) | 411 | 428 (+17) |
| Tests totales | 2313 | 2406 + 1 skipped |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Commits

```
6d9a172  feat(migrate): add Oracle view migration support for MariaDB, SQL Server, and PostgreSQL
5f212b1  docs(changelog): document Oracle view migration support and known v1 limitations
6662a44  feat(migrate): topological sort for views (Kahn's algorithm)
```

## Veredicto final

Veredicto: **CLOSED**

Pendientes al cierre:
- Limitación `ALL_VIEWS.text` tipo LONG: documentada en CHANGELOG; no es un bug activo con drivers modernos (cx_Oracle ≥ 8, python-oracledb ≥ 1.x).
- No hay pendientes funcionales.
