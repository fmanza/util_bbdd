# TRACEABILITY

## Session metadata
- id: 2026-10-09l-plan-pendientes-doc
- fecha: 2026-10-09
- rama: develop
- skill: PLAN + AUDIT_PLAN (pendientes de `documentation-architecture-audit`)
- fase: PLAN + AUDIT_PLAN; tras la aprobación («Sí a todo», 2026-10-10): P0 (`v0.41.0`), P1–P4 (`v0.41.1`), P5–P7

## Prompt issued
```text
PLAN y AUDIT_PLAN de lo Pendiente
```

## Context supplied
- `.ai/sessions/2026-10-09k-doc-architecture-audit/06_VERIFY.md` § 3 y `TRACEABILITY.md` (pendientes al cierre).
- Banco docker (6 motores + HSQLDB) para las comprobaciones de § 1.

## AI output summary
- B-04: sonda contra HSQLDB 2.7.4: `LISTAGG … WITHIN GROUP (ORDER BY ORDINAL_POSITION)` y `GROUP_CONCAT` funcionan; la
  rama de vistas usa `INFORMATION_SCHEMA.VIEWS.TEXT`, que no existe; los `CASE` dejan relleno de `CHAR`.
- S-02: vista con `'&amp;<b>'` en los 6 motores: todos devuelven el texto sin entidades → la decodificación de HTML es
  un bug de fidelidad, no una protección.
- Orden del inventario: `ORDER BY total_mb DESC` sin desempate en MySQL/MariaDB; sin `ORDER BY` en PostgreSQL y SQLite.
- Oracle: el contexto de metadatos es siempre el usuario conectado → el dorado aislado necesita un usuario propio.
- `mypy --strict`: 72 `type-arg` + 9 python-docx.
- Plan P0–P7 con cinco decisiones pendientes (D1–D5).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-09l-plan-pendientes-doc/PLAN_AUDIT_PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[HSQLDB/DDL]**: en HSQLDB 2.7 `INFORMATION_SCHEMA.VIEWS` tiene `VIEW_DEFINITION`, no `TEXT`; `LISTAGG` exige
  `WITHIN GROUP (ORDER BY …)`; un `CASE` con literales de distinta longitud se tipa `CHAR` y rellena con espacios.
- **[doc/entidades]**: ningún motor del banco devuelve DDL o definiciones con entidades HTML (comprobado con
  `'&amp;<b>'` en PostgreSQL, MySQL, MariaDB, SQL Server, Oracle y SQLite).
- **[HSQLDB/DDL]**: un `CAST(CASE … END AS VARCHAR)` no quita el relleno: el `CHAR` ya está calculado; hay que tipar
  como `VARCHAR` los literales de cada rama. Una columna `PRIMARY KEY` sin `NOT NULL` figura con `IS_NULLABLE = YES`.
- **[tests/Oracle]**: `UTIL_BBDD_TEST_ORACLE_ADMIN_URL` (SYSTEM, misma contraseña del banco) permite crear usuarios
  aislados; un `ALTER SESSION SET CURRENT_SCHEMA` en la misma conexión basta para crear los objetos del otro usuario.
- **[Oracle/contexto]**: `MetadataContextResolver` usa el usuario conectado como schema en Oracle; documentar otro
  owner exige conectar como él.

## Ejecución (2026-10-10)
Decisiones: D1 (a) etiquetar 0.41.0 y publicar los arreglos en 0.41.1; D2 push; D3 (a) usuario Oracle propio; D4 (a);
D5 (b).

| Bloque | Commit | Evidencia |
|---|---|---|
| P0 | `ba387eee` (tag `v0.41.0`, push) | `python -m build`; `test_docs_version.py` |
| P1 | `94a765a7` `hotfix(metadata)` | `tests/integration/test_hsqldb_server.py` (rojo antes, 5 verdes después, con `JAVA_HOME`); PK fuera de alcance del hotfix |
| P2 | `45670f6a` `fix(doc)` | e2e SQLite con `'&amp;<b>'` (rojo antes); sonda de HSQLDB; dorados HTML sin cambios; `sql-highlight.js` probado con Node |
| P3 | `c60a3fc3` `fix(metadata)` | test unitario de orden total; dos snapshots seguidos idénticos (MySQL, MariaDB, SQL Server, Oracle) |
| P4 | `2e1c1bf3` `docs` | `grep DatabaseConnectionError src` vacío |
| Release | `35c2cc62` (tag `v0.41.1`, push) | ruff, mypy, 5483 pasan, `zensical build --strict`, `python -m build` |
| P5 | `506e7912` `test(doc)` | `test_doc_matches_golden[oracle]` pasa dos veces seguidas; `ZZ_GOLD_DOC` borrado (comprobado en `FREEPDB1`) |
| P6 | `bf5dbe5f` `refactor(doc)` | `mypy --strict` 81 → 9 (python-docx); override `disallow_any_generics` comprobado con un fichero de prueba |
| P7 | `66102057` `security(analysis)` + `73b9112f` `test(analysis)` | `matplotlib_graph.py` 27 % → 93 %; S-04 también en matplotlib (encontrado al escribir los tests) |

## Veredicto final
Veredicto: CLOSED — P0–P7 completados (P0–P4 en `v0.41.0`/`v0.41.1`; P5–P7 en `develop`, bajo `[Unreleased]`)
Pendientes al cierre:
- DDL de tabla de HSQLDB sin clave primaria (mejora, no entra en un hotfix).
- Los 9 `no-untyped-call` de python-docx (dependen de los tipos de la librería).
