# TRACEABILITY

## Session metadata
- id: 2026-09-26zb-q9b-reflect-sin-fk
- fecha: 2026-09-26
- rama: develop (base `d2729f8`)
- skill: performance-audit-dump (resto de Q9: reflexión de `BulkCrud` en SQL Server)
- origen: pendiente anotado en `2026-09-26za-q9-mssql-fk-por-esquema` («Adelante con lo pendiente»)

## PLAN
- **Medición** (`reflect_cost.py`: 200 tablas en SQL Server, en serie).
  - `BulkCrud.reflect_table`: **32 ms/tabla**.
  - Con `get_foreign_keys` anulado: **16 ms/tabla**. Las FK son el 53 % de la reflexión.
  - `BulkCrud` no usa las FK de la tabla reflejada: no hay usos en `bulk/`, y el PK sync solo usa la identidad.
- **Restricción de SQLAlchemy 2.0.50**: no hay opción pública para no reflejar las FK.
  - `Table(autoload_with=…)` crea su propio Inspector con `_construct`, que sustituye la clase por
    `dialect.inspector`. Ni una subclase ni un método sustituido en la instancia llegan a usarse.
  - `Inspector.reflect_table(table, None)` es el patrón público documentado. Llama a `self._get_reflection_info` →
    `self.get_multi_foreign_keys` de la misma instancia, así que basta sustituir ese método en la instancia.
- **API**: opción aditiva `reflect_foreign_keys: bool = True` en `BulkCrud` y en `ParallelBulkLoader`.
  - Con `True` se mantiene el código anterior, `Table(autoload_with=engine, resolve_fks=False)`.
  - `dump` pasa `False`.

## AUDIT_PLAN
- **Funcional**: con `False`, la misma `Table` salvo las FK: columnas, tipos, nulabilidad, PK, `autoincrement`,
  identidad, default de servidor e índices. `NoSuchTableError` igual que antes.
- **Técnico**: si una versión futura de SQLAlchemy deja de pedir las FK a `get_multi_foreign_keys`, la sustitución no
  tiene efecto. Se volverían a reflejar (más lento, mismo resultado para `BulkCrud`); el fallo es seguro.
- **Seguridad**: sin cambios (reflexión de metadatos).

## IMPLEMENT
- `bulk/crud.py`:
  - `_no_foreign_keys`;
  - parámetro `reflect_foreign_keys`;
  - `reflect_table` con las dos ramas;
  - `_reflect_without_foreign_keys` (`inspect(conn)` + `reflect_table`).
- `bulk/_execution/parallel_loader.py`: el parámetro llega a la `BulkCrud` de cada partición y a `_resolve_table`.
- `dump/orchestrator.py`: `reflect_foreign_keys=False` en `_make_worker_crud` y en el `ParallelBulkLoader` de los
  rangos de PK.
- Documentación: `docs/api/bulk-crud.md` y `docs/api/bulk-parallel.md` (firma y tabla de parámetros), `CHANGELOG.md`
  (*Added* en bulk, *Changed* en dump).

## Validación
- **Integración** (`test_reflect_without_foreign_keys_matches_default_reflection`): la firma de la tabla es idéntica
  con las dos opciones en SQLite, PostgreSQL, MySQL, MariaDB, SQL Server y Oracle, con identidad, FK, default de
  servidor e índice. Los 28 tests de integración de `dump` (identidad, PK sync, FK) pasan por la ruta nueva.
- **Unitarios** (`tests/unit/bulk/test_reflect_without_foreign_keys.py`, 6):
  - misma tabla sin FK;
  - las FK no se leen (el `get_multi_foreign_keys` de la clase está parcheado para fallar);
  - caché;
  - `NoSuchTableError`;
  - el loader pasa la opción a sus dos `BulkCrud`;
  - `dump` crea sus `BulkCrud` con `False`.
  Mutación comprobada: sin la sustitución fallan 2 tests.
- **Rendimiento**: 200 tablas en SQL Server, **15,8 → 14,0 / 14,6 s**. `reflect` pasa de 6,2 a 3,55 s y ya no queda
  ninguna consulta de FK. Frente a v0.16.1 (33,9 s): **−58 %**.
- **Calidad**: `ruff check` y `ruff format` limpios; `mypy` sin errores. Suite con las URLs del banco: **5278 passed**.
  `mkdocs build --strict` sin errores.

## AUDIT_CODE
- Con el valor por defecto, el código de reflexión no cambia.
- `_reflect_without_foreign_keys` abre una conexión para toda la reflexión. Antes, `Table(autoload_with=engine)`
  hacía lo mismo por dentro, con `_inspection_context`.
- `type: ignore[method-assign]` justificado en el docstring.

## VERSION
- Commit: `perf(bulk,dump): reflejar las tablas destino del volcado sin sus FK (Q9, reflect_foreign_keys)`
- Rollback: `git revert <commit>`. La opción es aditiva y su valor por defecto mantiene el comportamiento.

## Directrices para Futuras IAs
- **[SQLAlchemy/reflexión]**: `Table(autoload_with=…)` no respeta un Inspector personalizado: `_inspection_context` →
  `_construct` usa `dialect.inspector`. Para personalizar la reflexión, crea `Table(nombre, md)` y llama a
  `inspect(conn).reflect_table(tabla, None)`.
- **[bulk]**: `BulkCrud` solo usa de la `Table` reflejada las columnas, la PK y la identidad; las FK sobran.
- **[dump/SQL Server]**: tras Q9 no queda ninguna llamada a la consulta `fk_info` de SQLAlchemy en un volcado. El coste
  fijo por tabla restante (≈ 70 ms) se reparte entre la reflexión (≈ 18 ms), los conteos, la rehabilitación de
  constraints y la carga.

## Veredicto final
Veredicto: CLOSED
