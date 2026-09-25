# TRACEABILITY

## Session metadata
- id: 2026-09-25-hotfix-dump-sqlite-truncate
- fecha: 2026-09-25
- rama: develop (base `aa5829d`)
- skill: hotfix (RCA + FIX + AUDIT_CODE + VERSION)
- origen: observado en `2026-09-25-new-feature-dump-report-pk-sync-sheet`: WARNING "Error limpiando tabla" en SQLite

## Prompt issued
```
Algo que vi y no toqué: en SQLite, run() saca un WARNING al limpiar el destino, porque SQLite no admite
TRUNCATE TABLE. Ya pasaba antes de esta sesión. miralo
```

## RCA
- `DumpOrchestrator._cleanup` (Fase 3, `truncate_target=True`, el valor por defecto) usaba `TRUNCATE TABLE` en todos los motores, salvo en las tablas de SQL Server con FK entrantes (DELETE).
- SQLite no tiene `TRUNCATE`, así que la sentencia fallaba con `OperationalError`. `_cleanup_table` solo reintenta con DELETE en `mssql`; en el resto registra un WARNING y sigue.
- **Impacto real, no solo ruido**: el destino conservaba sus filas.
  - Con PK, la carga chocaba (`IntegrityError`) y la tabla quedaba en `error` sin cargar nada. Reproducido: destino `[1, 9]`, origen `[1, 2]` → `error`, destino sin cambios.
  - Sin PK, se duplicaban filas en silencio.
- Los tests existentes usaban destinos vacíos o motores simulados, así que no lo veían.

## FIX (mínimo)
- `orchestrator.py`: `use_delete = dialect == "sqlite" or (dialect == "mssql" and table.lower() in mssql_referenced)`. En SQLite, un `DELETE FROM` sin `WHERE` es el equivalente a `TRUNCATE`: el motor lo optimiza. Los demás motores no cambian.
- Un test anterior (`test_failed_table_with_periodic_commits_audits_exactly_the_committed_rows`, de `161aae2`) provocaba un choque de PK precargando una fila en el destino, y **solo funcionaba gracias al bug**. Ahora usa `truncate_target=False`, que es lo que necesitaba.
- **Docs**:
  - `docs/api/dump.md`, fila `truncate_target`.
  - Corregido además un error propio de `161aae2`: el párrafo sobre `total_filas`/`audited_rows` estaba dentro de la tabla de `DumpResult` y dejaba fuera de ella las filas `pk_sync_results` e `index_results`. `mkdocs --strict` no lo detectaba; se verificó en el HTML generado.
- `CHANGELOG.md` (*Fixed*).

## Validación
- **Tests**:
  - `test_orchestrator.py::TestCleanup::test_delete_used_for_sqlite`;
  - E2E `test_non_empty_sqlite_target_is_cleaned_before_loading`: el destino con `[1, 9]` queda en `[1, 2, 3]` y la tabla en `success`.
  - Sin el arreglo (`git stash` del fuente), **los dos fallan**.
- **Calidad**:
  - `ruff check` limpio;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio;
  - `pytest tests/unit`: **4425 passed**;
  - `mkdocs build --strict`: exit 0; la tabla de `DumpResult` tiene sus 8 filas en el HTML.

## AUDIT_CODE
- Solo cambia SQLite. PostgreSQL, MySQL, MariaDB y Oracle siguen con TRUNCATE; SQL Server, con su estrategia híbrida.
- **No se generaliza** el reintento con DELETE a todos los motores cuando falla TRUNCATE. Es un cambio de comportamiento más amplio (p.ej. Oracle ORA-02266 con FK activas) y queda fuera de un hotfix.
- **Observado, fuera del alcance**: `ConstraintManager` avisa "Dialect 'sqlite' no soportado para gestión de constraints". Es informativo: SQLite no aplica FKs salvo con `PRAGMA foreign_keys=ON`.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[dump / tests]**: para provocar un fallo de carga precargando filas en el destino, poner `truncate_target=False`. Con la limpieza activa, esas filas se borran antes de cargar.
- **[docs / tablas Markdown]**: `mkdocs build --strict` no detecta una tabla partida por un párrafo o una línea en blanco. Si se añade texto junto a una tabla, comprobar las filas en el HTML generado.

## Veredicto final
CLOSED
