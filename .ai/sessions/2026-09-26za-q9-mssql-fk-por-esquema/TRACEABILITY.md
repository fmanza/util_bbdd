# TRACEABILITY

## Session metadata
- id: 2026-09-26za-q9-mssql-fk-por-esquema
- fecha: 2026-09-26
- rama: develop (base `3a3bc17`)
- skill: performance-audit-dump (paso 3.2 / Q9 del roadmap)
- origen: el usuario eligió Q9 tras la medición de Q8

## PLAN
- **Medición** (`q9_profile.py`: volcado de 200 tablas pequeñas en SQL Server, tiempo por sentencia SQL y por método del
  Inspector). La consulta de FK de SQLAlchemy para SQL Server (`WITH fk_info AS …` sobre `INFORMATION_SCHEMA`) se
  ejecutaba **600 veces: 20,6 s de 33,9 s (61 %)**. Origen de las llamadas:
  - 200 del análisis: grafo FK de origen en `_topological_sort`;
  - 200 de la limpieza: `_get_dst_fk_referenced_tables`;
  - 200 de `BulkCrud.reflect_table` (`Table(autoload_with=…)`).
  `get_columns` solo sumaba 1,5 s.
- **Cambio**: una consulta por esquema a `sys.foreign_keys` para el análisis y la limpieza. La reflexión de `bulk` queda
  fuera de alcance, ya anotado en el roadmap.
- **Regla #1 de arquitectura**: el SQL de introspección solo vive en `metadata/`. Va en
  `metadata/sqlserver/constraints.py::fetch_schema_fk_references_sql()`. Su parámetro es `:schema` (estilo de `text()`),
  válido con pymssql y con pyodbc; el estilo `%(name)s` de `migrate` solo funciona con pymssql.
- Import nuevo `dump → metadata` (capa 7 → capa 5: permitido). Sin coste de importación, porque `util_bbdd/__init__`
  ya importa `metadata`.

## AUDIT_PLAN
- **Funcional**: mismo resultado que `get_foreign_keys`.
  - Se devuelven las FK de las tablas del esquema, también las deshabilitadas y las que apuntan a otro esquema.
  - Solo cuenta el nombre de la tabla referida, como antes.
  - `DumpConfig.tables` con otro case: se busca también en minúsculas.
- **Técnico**: si la consulta falla (p. ej. sin permiso sobre `sys.*`), se vuelve a `get_foreign_keys` tabla a tabla. En
  la limpieza, una tabla que falla se omite; el `DELETE` de respaldo tras un `TRUNCATE` fallido sigue cubriendo ese caso.
- **Seguridad**: el esquema va como parámetro; no hay SQL construido con nombres.

## IMPLEMENT
- `src/util_bbdd/metadata/sqlserver/constraints.py`: `fetch_schema_fk_references_sql()`.
- `src/util_bbdd/dump/orchestrator.py`:
  - `_referred_tables(tables, inspector, schema)`: tabla → tablas referidas, una entrada por FK;
  - `_mssql_referred_tables`: consulta por esquema, o `None` si falla;
  - `_build_fk_graph` y `_get_dst_fk_referenced_tables` usan `_referred_tables`.
- `scripts/gen_arquitectura_capas.py`: `("dump", "metadata")` en `DRAWN`; la nota «analysis/, doc/ y dump/ también
  importan de metadata/». SVG regenerado y revisado en PNG, sin solapes. Pie de figura de `docs/architecture.md`
  actualizado (342 ficheros).
- `docs/api/dump.md` (dependencias), `CHANGELOG.md` (`[Unreleased]` → *Changed*).

## Validación
- **Equivalencia** (`q9_equiv.py`, pyodbc y pymssql): `_referred_tables` coincide con `get_foreign_keys` tabla a tabla
  en `dump_src`, en `dump_dst` y con `schema=None`. El orden topológico no cambia.
- **Integración**: `test_mssql_fk_references_by_schema_match_the_inspector`. Cubre:
  - dos FK a la misma tabla;
  - una FK a sí misma;
  - una FK hacia otro esquema;
  - `schema=None` y el esquema por defecto explícito;
  - nombres en mayúsculas;
  - que `get_foreign_keys` no se llama (parcheado para fallar).
  Detecta la mutación «filtrar por el esquema de la tabla referida».
- **Unitarios** (`TestReferredTables`, 5): una consulta, esquema por defecto, vuelta a la ruta por tabla si la consulta
  falla, otros motores (con tablas que fallan) y orden topológico sin `get_foreign_keys`.
- **Rendimiento**:
  - 200 tablas en SQL Server: **33,9 → 15,8 s (−53 %)**; análisis 9,6 → 1,7 s, limpieza 7,7 → 0,7 s. 200/200 `success`.
  - Datos `large` (3 tablas): 59,1 → 57,8 s de mediana (neutro). Resultados en `results/`.
- **Calidad**: `ruff check` y `ruff format` limpios; `mypy` sin errores. Suite con las URLs del banco: **5266 passed**.
  `mkdocs build --strict` sin errores.

## AUDIT_CODE
- **Rutas**: solo cambia la ruta de SQL Server. En el resto de motores, `_referred_tables` hace el mismo recorrido por
  tabla que antes.
- **Diferencia menor en la limpieza**: antes, un error en cualquier tabla vaciaba el conjunto de tablas referenciadas
  (todas probaban `TRUNCATE` y, si fallaba, `DELETE`). Ahora solo se omite esa tabla. La red de seguridad es la misma.
- **Coste**: `_topological_levels` (carga en paralelo) repite la consulta por esquema: una consulta de ms, frente a las
  llamadas por tabla que antes cacheaba el Inspector.
- **Lo que queda en SQL Server**: 200 llamadas de `BulkCrud.reflect_table` (≈ 6,2 s en `reflect` con 200 tablas).

## VERSION
- Commit: `perf(dump): leer las FK de todo el esquema en una consulta en SQL Server (Q9)`
- Rollback: `git revert <commit>` (sin cambios de API ni de datos).

## Directrices para Futuras IAs
- **[dump/SQL Server]**: `Inspector.get_foreign_keys` de SQLAlchemy para mssql cuesta ≈ 12–34 ms por tabla. Para muchas
  tablas, usa `DumpOrchestrator._referred_tables`, que resuelve todo el esquema con una consulta.
- **[metadata]**: el SQL que `dump` ejecuta con `sqlalchemy.text` lleva parámetros `:name`. El estilo `%(name)s` de
  `metadata/sqlserver` para `migrate` solo funciona con pymssql, no con pyodbc.
- **[medición]**: para aislar el coste de introspección, cronometra por sentencia con `before/after_cursor_execute` y por
  método del Inspector (`q9_profile.py`). Con el lector en paralelo, las fases del banco se solapan.
- **[pendiente]**: la reflexión de `BulkCrud.reflect_table` en SQL Server sigue haciendo una consulta de FK por tabla.

## Veredicto final
Veredicto: CLOSED
