# 01_TECH_DEBT_AUDIT — comparar/ + doc/

**Sesión:** 2026-04-21-tech-debt-comparar-doc
**Veredicto global:** DEUDA_SIGNIFICATIVA

---

## Inventario de deuda — comparar/

### Módulo comparator.py

| ID | Línea(s) | Tipo | Prioridad |
|----|----------|------|-----------|
| C1 | 26, 243, 709, 825 | Logging triple inconsistente (`self.logger` + `logger` módulo + `logging.getLogger()` directo) | `quick_win` |
| C2 | 1099–1107 | `_ROUTINE_FETCHERS.update()` en nivel de módulo — estado mutable fuera de clase | `quick_win` |
| C3 | 50–87, ~350 LOC | SRP violado: 5 métodos `_get_routines_xxx` inline en SchemaComparator | `deuda_estructural` |
| C4 | 93–100, 845 | `_DB_TYPE_TO_DIALECT` documentación muerta — no filtra dialect_name en `_get_routines_safe` | `fase_media` |
| C5 | 720–731 | `cast(Literal[...])` sin validación real; `prokind="w"` puede pasar al RoutineDiff como tipo inválido | `fase_media` |
| C6 | 352–366, 592–607 | `_compare_columns` y `_compare_comments` dead code (overloads no usados en flujo principal) | `quick_win` |
| C7 | 765 | Fallback SA 1.4 `getattr(inspector, "bind", None)` — SA 2.0+ garantiza `.engine` | `quick_win` |
| C8 | 878 | SQL injection MariaDB: f-string con escape manual de backticks en SHOW CREATE PROCEDURE | `fase_media` |

### reporters/_base.py

| ID | Línea(s) | Tipo | Prioridad |
|----|----------|------|-----------|
| C9 | 117–131 vs comparator.py:66–87 | `DdlNormalizer._VIEW_STRIP_PATTERNS` duplica `SchemaComparator._DDL_STRIP_RULES` — dos sistemas de normalización paralelos | `deuda_estructural` |

### reporters/facade.py

| ID | Línea(s) | Tipo | Prioridad |
|----|----------|------|-----------|
| C10 | 181 | `render_all`: `except Exception` sin re-raise — salida parcial sin aviso programático | `fase_media` |
| C11 | 104–113 | Todos los reporters instanciados en `__init__` aunque se use solo uno (no lazy) | `quick_win` |

### reporters/sql_reporter.py

| ID | Línea(s) | Tipo | Prioridad |
|----|----------|------|-----------|
| C12 | 263–270 | `_col_cache/_fk_cache/_idx_cache` no se resetean entre llamadas a `render()` — cache contaminada | `fase_media` |
| C13 | 683 | Doble `;` en `_render_add_column_with_type` (template ya incluye `;`) | `quick_win` |
| C14 | 236–239 | `_EXISTS_VALUES` incluye valores legacy de fixtures (`"present"/"absent"`) mezclados con semántica de dominio | `fase_media` |
| C15 | 1019–1023 | Rutinas `modified` no emiten DROP antes de recrear — falla en MariaDB/MySQL sin CREATE OR REPLACE PROCEDURE | `fase_media` |

---

## Inventario de deuda — doc/

| ID | Archivo:línea | Tipo | Prioridad |
|----|---------------|------|-----------|
| D1 | database_documentation.py:82–151 | I/O en constructor (`_create_documents()` en `__init__`) — rompe testabilidad | `deuda_estructural` |
| D2 | database_documentation.py:80–81 | `_LAST_AUTO_OUTPUT_BY_KEY: ClassVar[dict]` mutable — singleton implícito no thread-safe | `fase_media` |
| D3 | database_documentation.py:61–79 | Atributos de instancia declarados como anotaciones de clase | `quick_win` |
| D4 | application/ports.py:169–172 | `DocumentationDataProviderPort` circular (Port que depende de Port del mismo nivel) | `fase_media` |
| D5 | application/ports.py (general) | 16 Protocols en un archivo — granularidad excesiva, algunos solo usados internamente | `deuda_estructural` |
| D6 | doc/ (sin archivo) | Sin excepciones tipadas propias (`DocumentationError`) — errores como `Exception` genérica | `fase_media` |

---

## Plan por fases

### Fase 1 — Quick Wins (< 1h total, sin riesgo de regresión)
- QW-1: Logging unificado comparator.py (C1)
- QW-2: _ROUTINE_FETCHERS init en clase (C2)
- QW-3: Corregir doble `;` sql_reporter.py (C13)
- QW-4: Eliminar dead code `_compare_columns`/`_compare_comments` (C6)
- QW-5: Eliminar fallback SA 1.4 (C7)
- QW-6: Atributos instancia en database_documentation.py (D3)

### Fase 2 — Correcciones con test requerido
- C10: render_all — añadir parámetro raise_on_error
- C12: Cache reset en SqlDiffReporter.render()
- C14: Limpiar _EXISTS_VALUES/_ABSENT_VALUES
- C15: Rutinas modified — añadir DROP IF EXISTS antes del CREATE
- D2: ClassVar mutable → dict de instancia o mecanismo de reset
- D4: Resolver Port circular
- D6: Crear DocumentationError en _core/exceptions.py

### Fase 3 — Deuda estructural (requiere PLAN+AUDIT_PLAN propios)
- C3+C9: Separar RoutineFetcherRegistry + unificar normalización DDL
- D1: DatabaseDocumentation constructor → factory/generate() explícito
- D5: Consolidar Protocols en doc/application/ports.py
- C4: Hacer _DB_TYPE_TO_DIALECT funcional
- C5: Validación real de routine_type
- C8: Validación de identificador en _get_routines_mariadb

---

## Veredicto por módulo

- `comparar/`: **DEUDA_SIGNIFICATIVA** — Correctitud (C13, C15), duplicación estructural (C9), riesgo seguridad (C8)
- `doc/`: **DEUDA_SIGNIFICATIVA** — I/O en constructor (D1), ClassVar mutable (D2), sin excepciones tipadas (D6)
