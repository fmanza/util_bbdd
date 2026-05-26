# TRACEABILITY

## Session metadata
- id: 2026-05-26-comparar-tech-debt
- fecha: 2026-05-26
- rama: develop
- skill: tech_debt
- fase: AUDIT_CODE (análisis) → IMPLEMENT (D1–D12) → VALIDATE

## Prompt issued

```
[TECH_DEBT sobre src/util_bbdd/comparar/]
IMPLEMENT plan D1–D12 por fases
```

Continuación directa de `2026-05-26-comparar-audit-fix` tras auditoría inicial.

## Context supplied
- `src/util_bbdd/comparar/comparator.py`
- `src/util_bbdd/comparar/_routine_fetchers.py`
- `src/util_bbdd/comparar/models.py`
- `src/util_bbdd/comparar/reporters/word_reporter.py`
- `tests/comparar/test_comparator.py`
- Transcript de la sesión compactada anterior

## AI output summary

### Veredicto previo (auditoría): DEUDA_MENOR — 12 ítems D1–D12

### Plan de implementación por fases

| Fase | Ítems | Archivos |
|---|---|---|
| 1 — Quick wins | D1, D2, D3, D4, D5 | `_routine_fetchers.py`, `comparator.py` |
| 2 — Modelo/comparación | D6, D7, D8, D9 | `models.py`, `comparator.py` |
| 3 — Fetchers except | D10 | `_routine_fetchers.py` |
| 4 — Reporters | D12 | `reporters/word_reporter.py` |
| 5 — Validación | — | suite completa + linter |

---

### Fase 1 — Quick wins (D1–D5)

**D1 — Imports de tipo solo bajo `TYPE_CHECKING`**

`_routine_fetchers.py`: `CursorResult`, `Row`, `RowMapping`, `Engine` movidos a bloque
`if TYPE_CHECKING:`. Seguro porque `from __future__ import annotations` está presente.

`comparator.py`: `Callable`, `Mapping` (de `collections.abc`) y `ReflectedTableComment`
(de `sqlalchemy.engine.interfaces`) movidos a `if TYPE_CHECKING:`.
`Callable` solo aparece en `ClassVar[dict[str, Callable[...]]]` y anotaciones de parámetro;
`Mapping` solo en anotación de `_fk_key(fk: Mapping[str, Any])`.

**D2 — `from sqlalchemy import text` a nivel de módulo**

`_routine_fetchers.py`: los 4 imports locales dentro de `get_routines_mariadb`,
`get_routines_oracle`, `get_routines_mssql` y `get_routines_postgresql` eliminados;
import movido al bloque de imports del módulo.

**D3 — Constante `_MIN_PRINTABLE_ORD`**

`_routine_fetchers.py` línea `ord(c) >= 32`:
```python
_MIN_PRINTABLE_ORD: int = 0x20  # primer carácter ASCII imprimible (espacio)
```
Valor `32` reemplazado por la constante en `_is_safe_identifier`.

**D4 — Parámetros no usados en `get_routines_hsqldb`**

Firma cambiada de `(inspector, schema)` a `(_inspector, _schema)` — elimina ARG004.

**D5 — Helper `_parse_url_safe`**

`comparator.py`: extraído método estático:
```python
@staticmethod
def _parse_url_safe(inspector: Inspector) -> Any | None:
    """Parsea la URL del engine; devuelve None si no es posible."""
    engine = getattr(inspector, "engine", None)
    url_raw = getattr(engine, "url", None)
    if url_raw is None:
        return None
    try:
        return make_url(str(url_raw))
    except Exception:
        return None
```
`_build_label` y `_build_short_label` refactorizados para usar `_parse_url_safe`;
la lógica `engine = getattr(...)` + `url_raw = getattr(...)` + `make_url(str(url_raw))`
ya no se duplica.

---

### Fase 2 — Modelo / comparación (D6–D9)

**D6 — `total_leaf_differences` en `SchemaDiff`**

`models.py` — nueva property backward-compatible:
```python
@property
def total_leaf_differences(self) -> int:
    table_leaves = sum(
        len(t.column_diffs) + len(t.index_diffs) + len(t.fk_diffs) + len(t.comment_diffs)
        for t in self.table_diffs
    )
    return table_leaves + len(self.view_diffs) + len(self.routine_diffs)
```
`total_differences` (conteo de primer nivel) conservado sin cambios.

**D7 — `_compare_comments_from_raw` cubre columnas exclusivas**

`comparator.py` — iteración cambiada de intersección a unión:
```python
# ANTES (missing diffs en columnas solo en source o solo en target)
for col_name in sorted(set(source_cols) & set(target_cols)):
    s_col_comment = str(source_cols[col_name].get("comment") or "")

# DESPUÉS
for col_name in sorted(set(source_cols) | set(target_cols)):
    s_col_comment = str((source_cols.get(col_name) or {}).get("comment") or "")
```

**D8 — `status` en `CommentDiff`**

`models.py`:
```python
@dataclass(frozen=True)
class CommentDiff:
    ...
    status: Literal["modified"] = "modified"  # siempre modified; por consistencia con otros diffs
```
Backward-compatible (campo con valor por defecto).

**D9 — Clave compuesta `name:type` en `_compare_routines`**

`comparator.py` — evita colisión cuando existe una PROCEDURE y una FUNCTION con
el mismo nombre:
```python
source_map = {f"{r['name']}:{r.get('type', 'PROCEDURE')}": r for r in ...}
target_map = {f"{r['name']}:{r.get('type', 'PROCEDURE')}": r for r in ...}
```
El loop extrae `r["name"]` para `RoutineDiff.routine_name` en lugar de usar la clave compuesta.

---

### Fase 3 — Fetchers except más específico (D10)

`_routine_fetchers.py` — añadido:
```python
from sqlalchemy.exc import DatabaseError, OperationalError, ProgrammingError
```

8 `except Exception` reemplazados:

| Contexto | Antes | Después |
|---|---|---|
| Fallback conexión (MariaDB, Oracle, MSSQL, PostgreSQL) × 4 | `except Exception as exc` | `except (OperationalError, DatabaseError) as exc` |
| DDL individual (Oracle DBMS_METADATA, MSSQL sql_modules ×2, PG pg_get_functiondef) × 4 | `except Exception:` | `except (ProgrammingError, DatabaseError):` |

Justificación: errores de conexión/auth → `OperationalError`; errores de permisos/DDL
SQL no disponible → `ProgrammingError`; errores de infraestructura general → `DatabaseError`.

---

### Fase 4 — Reporters (D12)

`reporters/word_reporter.py`:

- **TID252**: `from ..models import ...` y `from ._base import ...` convertidos a
  imports absolutos:
  ```python
  from util_bbdd.comparar.models import RoutineDiff, SchemaDiff, TableDiff, ViewDiff
  from util_bbdd.comparar.reporters._base import STATUS_ES, DdlNormalizer, build_diff_summary
  ```
- **EM102**: f-strings en `raise FileNotFoundError(...)` extraídas a variable `msg`:
  ```python
  msg = f"Plantilla no encontrada: {resolved}"
  raise FileNotFoundError(msg)
  ```

**Ítems no aplicados** (reglas no activas en config ruff del proyecto):
- `sql_reporter.py` FBT001/FBT002 (`or_replace: bool = False`) — requeriría refactorizar call sites;
  descartado ya que ruff no lo reporta con la config vigente.
- TC002/TC003 en reporters — descartado por la misma razón.

---

### Resultado final

| Métrica | Antes | Después |
|---|---|---|
| Tests | 279/279 passed | 279/279 passed |
| `ruff check src tests` | All checks passed | All checks passed |
| `_routine_fetchers.py` imports inline | 4 (`from sqlalchemy import text`) | 0 |
| `except Exception` en fetchers | 8 | 0 |
| `Callable`/`Mapping`/`ReflectedTableComment` runtime | 3 imports nivel módulo | 0 (bajo `TYPE_CHECKING`) |
| Duplicación URL parse logic | 2 métodos | 1 helper `_parse_url_safe` |

Archivos modificados: 4
- `src/util_bbdd/comparar/_routine_fetchers.py`
- `src/util_bbdd/comparar/comparator.py`
- `src/util_bbdd/comparar/models.py`
- `src/util_bbdd/comparar/reporters/word_reporter.py`

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| D1 TYPE_CHECKING imports | `_routine_fetchers.py`, `comparator.py` | completado |
| D2 text top-level | `_routine_fetchers.py` | completado |
| D3 _MIN_PRINTABLE_ORD | `_routine_fetchers.py` | completado |
| D4 ARG004 hsqldb | `_routine_fetchers.py` | completado |
| D5 _parse_url_safe | `comparator.py` | completado |
| D6 total_leaf_differences | `models.py` | completado |
| D7 _compare_comments unión | `comparator.py` | completado |
| D8 CommentDiff.status | `models.py` | completado |
| D9 clave name:type routines | `comparator.py` | completado |
| D10 except específico | `_routine_fetchers.py` | completado |
| D11 ComparisonOptions dataclass | — | DIFERIDO — deuda_estructural, requiere PLAN+AUDIT_PLAN |
| D12 TID252+EM102 word_reporter | `reporters/word_reporter.py` | completado |

## Directrices para Futuras IAs

- **[comparar/D9]**: `_compare_routines` usa clave `f"{r['name']}:{r.get('type','PROCEDURE')}"`.
  NO usar solo `r["name"]` como clave de dict — colisiona cuando PROCEDURE y FUNCTION comparten nombre.

- **[comparar/D7]**: `_compare_comments_from_raw` itera `set(source) | set(target)` (unión).
  Columnas exclusivas de un lado también se comparan (comentario del lado ausente = `""`).

- **[comparar/D10]**: Los `except` de los fetchers son `(OperationalError, DatabaseError)` para
  errores de conexión y `(ProgrammingError, DatabaseError)` para DDL individual.
  NO ampliar a `Exception` genérico — oculta errores de programación en los fetchers.

- **[comparar/D11 — PENDIENTE]**: `ComparisonOptions` dataclass para los 10 parámetros de `compare()`
  sigue pendiente como deuda_estructural. Requiere sesión PLAN+AUDIT_PLAN independiente antes de implementar.

- **[comparar/D12]**: `word_reporter.py` usa imports absolutos `util_bbdd.comparar.*`.
  NO volver a imports relativos de padre (`..models`) — TID252 corregido.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- D11: `ComparisonOptions` dataclass — deuda_estructural, diferida; requiere PLAN+AUDIT_PLAN por alcance amplio
