# TRACEABILITY — Fase 3 Estructural (comparar/ + doc/)

**Sesión:** 2026-04-21-fase3-estructural
**Estado:** CLOSED
**Fecha cierre:** 2026-04-21
**Skill:** refactor
**Predecesora:** 2026-04-21-tech-debt-comparar-doc (Fases 1+2)

## Fases ejecutadas

| Fase | Artefacto | Estado |
|------|-----------|--------|
| PLAN | Sección PLAN en esta sesión | ✅ |
| AUDIT_PLAN | Sección AUDIT_PLAN en esta sesión | ✅ |
| IMPLEMENT | 5 ítems implementados | ✅ |
| AUDIT_CODE | Mypy strict + ruff clean | ✅ |
| VERSION | Commit atómico por ítem | pendiente commit |

## Ítems implementados

### D1 — I/O en constructor (doc/)

**Archivos:** `src/util_bbdd/doc/database_documentation.py`, `tests/unit/test_database_documentation.py`

- Eliminada llamada `self._create_documents()` del `__init__`
- Renombrado `_create_documents()` → `generate()` (método público)
- Actualizado test: 4 call sites `doc._create_documents()` → `doc.generate()`

**Breaking change:** `DatabaseDocumentation.__init__` ya NO genera documentos. Llamar `.generate()` explícitamente.

### D5 — Granularidad de ports (doc/)

**Archivos:** `src/util_bbdd/doc/application/ports.py` (reducido a 8 ports externos), `src/util_bbdd/doc/application/_internal_ports.py` (nuevo, 8 ports internos)

Ports movidos a `_internal_ports.py`:
- `PrintConfigPolicyPort`, `HeadersRuntimePort`, `MetadataRuntimePort`, `MetadataRuntimeFactoryPort`
- `StorageReportServicePort`, `RendererFactoryPort`, `RendererRegistrationPort`, `RendererRegistryPort`

Consumers actualizados (6 archivos): `application/__init__.py`, `use_cases/documentation_orchestrator.py`, `infrastructure/runtime/metadata_runtime.py`, `infrastructure/runtime/headers_runtime.py`, `infrastructure/storage/runtime.py`, `infrastructure/renderers/registry.py`

### D4 — Port circular (doc/)

**Archivo:** `src/util_bbdd/doc/application/ports.py`

- `DocumentationDataProviderPort(DocumentationManagerPort, Protocol)` → `DocumentationDataProviderPort(Protocol)`
- Mantiene `imprimir_config: dict[str, Any]` y `db_manager: DocumentationManagerPort`
- `DocumentRendererPort.generate_document.data_provider` alineado a `DocumentationManagerPort` (tipo que usan las implementaciones concretas)

### C9 — Unificación DDL (comparar/)

**Archivos:** `src/util_bbdd/comparar/reporters/_base.py`, `src/util_bbdd/comparar/comparator.py`

- Eliminado `SchemaComparator._DDL_STRIP_RULES` (11 patrones)
- Eliminado `SchemaComparator._strip_dialect_artifacts()`
- `DdlNormalizer` ampliado con:
  - `_COMPARISON_EXTRA_PATTERNS` (6 nuevos patrones: Oracle FORCE header, SQL Server brackets/WITH, PostgreSQL LANGUAGE/SECURITY/STRICT)
  - `DdlNormalizer.strip_dialect_artifacts(ddl)` — strip sin lowercase (mantiene backward compat para tests)
  - `DdlNormalizer.normalize_for_comparison(ddl)` — normalización completa = strip + lowercase + colapso espacios
- `SchemaComparator._normalize_ddl()` delega a `DdlNormalizer.normalize_for_comparison()`
- Tests actualizados: `TestDDLStripRules` → usa `DdlNormalizer._VIEW_STRIP_PATTERNS + _COMPARISON_EXTRA_PATTERNS`; `TestStripDialectArtifacts` → usa `DdlNormalizer.strip_dialect_artifacts()`

### C3 — RoutineFetcherRegistry SRP (comparar/)

**Archivos:** `src/util_bbdd/comparar/_routine_fetchers.py` (nuevo), `src/util_bbdd/comparar/comparator.py`, `tests/comparar/test_comparator.py`

- Creado `_routine_fetchers.py` con `RoutineFetcherRegistry` (5 `@staticmethod` + `_PROCEDURE_KIND_MAP`)
- Movida función `_is_safe_identifier` a módulo `_routine_fetchers.py` (módulo-nivel, no método de clase)
- Eliminados de `SchemaComparator`: 5 `_get_routines_xxx` static methods, `_PROCEDURE_KIND_MAP`, `_is_safe_identifier`
- Eliminados imports de `sqlalchemy` que solo usaban los fetchers: `CursorResult`, `Row`, `RowMapping`, `Engine`
- Registro al final de `comparator.py` actualizado: usa `RoutineFetcherRegistry.get_routines_xxx`
- Tests actualizados: `TestRoutineFetchersRegistry`, `TestGetRoutinesMariaDB/Oracle/MSSQL/PostgreSQL/HSQLDB` → referencian `RoutineFetcherRegistry`

## Validación final

```
mypy src        → Success: no issues found in 268 source files
ruff check src tests → All checks passed!
pytest          → 1969 passed, 1 skipped
```

**Baseline preservado** (Fases 1+2 tenían 1969 passed, 1 skipped).

## Cambios de API pública (breaking)

| Cambio | Antes | Después |
|--------|-------|---------|
| `DatabaseDocumentation.__init__` | genera documentos en disco | solo configuración |
| `DatabaseDocumentation.generate()` | no existía (`_create_documents()` privado) | método público explícito |
| `SchemaComparator._get_routines_xxx` | métodos estáticos en clase | movidos a `RoutineFetcherRegistry` |
| `SchemaComparator._DDL_STRIP_RULES` | ClassVar en comparator | `DdlNormalizer._VIEW_STRIP_PATTERNS + _COMPARISON_EXTRA_PATTERNS` |
| `SchemaComparator._strip_dialect_artifacts` | método privado | `DdlNormalizer.strip_dialect_artifacts()` |
| `DocumentationDataProviderPort` | hereda `DocumentationManagerPort` | `Protocol` plano con `db_manager` attr |
| `ports.py` (16 Protocols) | monolítico | 8 externos en `ports.py` + 8 internos en `_internal_ports.py` |
