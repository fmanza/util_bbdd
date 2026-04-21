# Tech Debt v0.8.1 — comparar/ y doc/

**Fecha análisis:** 2026-04-21
**Base:** v0.8.0 (commit eb6edd1)
**Veredicto:** DEUDA_SIGNIFICATIVA

---

## Resumen ejecutivo

Post-v0.8.0 (cobertura completa de type system) se identificaron **21 ítems de deuda técnica** en los módulos `comparar/` y `doc/`. Tres son bugs de correctitud activos listos para Fase 1; el resto afecta mantenibilidad, testabilidad y seguridad.

---

## Ítems por prioridad

### Quick Wins (Fase 1)

| ID | Módulo | Descripción |
|----|--------|-------------|
| C1 | `comparar/comparator.py:26,243,709,825` | Logging triple: unificar en `self.logger` |
| C2 | `comparar/comparator.py:1099–1107` | `_ROUTINE_FETCHERS.update()` en nivel de módulo → mover a cuerpo de clase |
| C3/QW-3 | `comparar/reporters/sql_reporter.py:683` | **Bug**: doble `;` en ADD COLUMN (template ya incluye `;`) |
| C6 | `comparar/comparator.py:352–366` | Dead code: `_compare_columns`/`_compare_comments` |
| C7 | `comparar/comparator.py:765` | Fallback SA 1.4 `inspector.bind` — eliminar |
| D3 | `doc/database_documentation.py:61–79` | Atributos de instancia declarados como anotaciones de clase |

### Fase 2 — Correcciones con test requerido

| ID | Módulo | Descripción |
|----|--------|-------------|
| C10 | `comparar/reporters/facade.py:181` | `render_all` silencia todas las excepciones |
| C12 | `comparar/reporters/sql_reporter.py:263` | Cache `_col_cache` no se resetea entre llamadas a `render()` |
| C14 | `comparar/reporters/sql_reporter.py:236` | `_EXISTS_VALUES` mezcla semántica dominio con fixtures legacy |
| **C15** | `comparar/reporters/sql_reporter.py:1019` | **Bug**: routines `modified` no emiten DROP IF EXISTS antes del CREATE — falla en MariaDB |
| D2 | `doc/database_documentation.py:80` | `_LAST_AUTO_OUTPUT_BY_KEY: ClassVar[dict]` mutable — singleton no thread-safe |
| D4 | `doc/application/ports.py:169` | Port circular: `DocumentationDataProviderPort` depende de `DocumentationManagerPort` |
| D6 | `doc/` | Sin excepciones tipadas (`DocumentationError`) — errores como `Exception` genérica |
| C4 | `comparar/comparator.py:93` | `_DB_TYPE_TO_DIALECT` es documentación muerta — no filtra en `_get_routines_safe` |
| C5 | `comparar/comparator.py:720` | `cast(Literal[...])` sin validación real de `routine_type` |
| **C8** | `comparar/comparator.py:878` | **Seguridad**: SQL injection MariaDB fetcher (escape manual insuficiente) |

### Fase 3 — Deuda estructural

| ID | Módulo | Descripción |
|----|--------|-------------|
| C3 | `comparar/comparator.py` | SRP violado: 5 fetchers de routines inline en `SchemaComparator` (~350 LOC) |
| C9 | `comparar/reporters/_base.py:117` | `DdlNormalizer` duplica `SchemaComparator._DDL_STRIP_RULES` — dos sistemas paralelos |
| D1 | `doc/database_documentation.py:82` | I/O en constructor (`_create_documents()` en `__init__`) — rompe testabilidad |
| D5 | `doc/application/ports.py` | 16 Protocols en un archivo — granularidad excesiva |

---

## Bugs activos

### C13 / QW-3 — Doble punto y coma en ADD COLUMN

**Archivo:** `sql_reporter.py:683`

```python
# ACTUAL (bug):
lines.append(f"{tpl.format(table=table, col=col_name, definition=definition)};")
# tpl = "ALTER TABLE {table} ADD COLUMN {col} {definition};"  ← ya incluye ;
# Resultado: ALTER TABLE x ADD COLUMN y TEXT;;

# CORRECCIÓN:
lines.append(tpl.format(table=table, col=col_name, definition=definition))
```

### C15 — Routines modified sin DROP IF EXISTS

**Archivo:** `sql_reporter.py:1019–1023`

```python
# ACTUAL (bug para MariaDB/MySQL):
# Solo emite la definición nueva sin DROP previo.
# CREATE PROCEDURE falla si ya existe.

# CORRECCIÓN (Fase 2):
# Para mariadb/mysql: DROP PROCEDURE IF EXISTS name; antes del CREATE
# Para postgresql/oracle: usar CREATE OR REPLACE
```

---

## Plan de versión v0.8.1

```
v0.8.1-dev
├── PR-1: Quick Wins Fase 1 (C1,C2,QW-3,C6,C7,D3)
│   commit: refactor(comparar): quick wins tech-debt Fase 1
│
├── PR-2: Correctitud + seguridad (C8,C12,C15,D2)
│   commit: fix(comparar): cache reset, routines modified DROP, MariaDB identifier validation
│
└── PR-3: Excepciones doc/ + render_all (C10,D6)
    commit: feat(doc): DocumentationError + render_all raise_on_error
```

---

## Referencias

- Sesión: `.ai/sessions/2026-04-21-tech-debt-comparar-doc/`
- Inventario completo: `.ai/sessions/2026-04-21-tech-debt-comparar-doc/01_TECH_DEBT_AUDIT.md`
- Release base: `docs/v0.8.0/RELEASE_v0.8.0.md`
