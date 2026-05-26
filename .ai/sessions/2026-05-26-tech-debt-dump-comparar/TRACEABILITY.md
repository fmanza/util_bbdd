# TRACEABILITY

## Session metadata
- id: 2026-05-26-tech-debt-dump-comparar
- fecha: 2026-05-26
- rama: develop
- skill: tech_debt → implement → sonarqube
- fase: AUDIT_CODE → IMPLEMENT (Fases 0–3) → VALIDATE (S3776/Pylance/S1481)

## Prompt issued
```
@#sym:tech_debt

Revisa src\util_bbdd\dump y src\util_bbdd\comparar, tiene dependencias, revisar.
Quiero quick wins, prioridades y plan por fases.
```
Seguido de: `IMPLEMENT Plan por fases`
Seguido de: diagnósticos SonarQube S3776 en `_routine_fetchers.py:73` y `_constraints.py:207`
Seguido de: diagnóstico Pylance `reportArgumentType` en `_constraints.py:234`
Seguido de: diagnósticos SonarQube S1481 en `test_orchestrator.py:228,234`

## Context supplied
- `src/util_bbdd/dump/` — orchestrator.py, _constraints.py, _models.py, reporters.py
- `src/util_bbdd/comparar/` — comparator.py, _routine_fetchers.py, reporters/_base.py
- `tests/unit/dump/` — test_constraints.py, test_orchestrator.py
- Estado git: rama develop, commits previos de audit+tech-debt sobre ambos módulos

## AI output summary

### Plan de fases (dump + comparar cross-module)

| Fase | Ítems | Módulos |
|---|---|---|
| Fase 0 — Quick wins | CP1, CP2, CP4, RF1, RF2, R1, B1, O3 | comparar + dump |
| Fase 1 — Modelos | M1 (ConstraintResult → _models.py) | dump |
| Fase 2 — Conexiones + bug | C1+C3 (PostgreSQL savepoints), C2 (Oracle batch) | dump |
| Fase 3 — Column mapping | O1 (_common_columns case map) | dump |
| Post — SonarQube | S3776 × 2, Pylance reportArgumentType, S1481 × 2 | ambos |

---

### Fase 0 — Quick wins

**CP4** (`comparator.py`): separador de clave de routine map cambiado de `:` a `\x00`
para evitar colisión con nombres de rutinas que contienen `:`.
```python
source_map = {f"{r['name']}\x00{r.get('type', 'PROCEDURE')}": r for r in ...}
```

**CP1** (`comparator.py`): `_parse_url_safe` return type `Any | None` → `URL | None`;
`URL` movido a `if TYPE_CHECKING:`.

**CP2** (`comparator.py`): nuevo `@staticmethod _mask_url(s: str) -> str` que encapsula
`re.sub(_URL_CREDENTIALS_RE, ...)`. `_build_label` y `_build_short_label` refactorizados
para eliminar duplicación de la expresión regular inline.

**RF1** (`_routine_fetchers.py`): loop manual `name_counts` → `Counter(str(row["proname"])
for row in rows_list)`.

**RF2** (`_routine_fetchers.py`): `db_name` simplificado a
`schema or str(getattr(getattr(engine, "url", None), "database", "") or "")`.

**R1** (`reporters.py`): `_sheet_missing_columns` refactorizado con list comprehension +
`enumerate` en lugar de bucle con índice manual y guarda `if row == 2:`.

**B1** (`reporters/_base.py`): docstring de `strip_dialect_artifacts` aclarado con nota
sobre el doble espacio intencional en el ejemplo.

**O3** (`orchestrator.py`): `_get_source_tables` retorna `sorted(self._cfg.tables)` cuando
las tablas son explícitas, garantizando orden determinista en los tests.

---

### Fase 1 — M1: ConstraintResult movido a _models.py

`_models.py`: `ConstraintResult` dataclass añadida antes de `DumpConfig`.
`_constraints.py`: definición eliminada; import actualizado a `from ._models import ConstraintResult`.
`Literal` y `dataclass` eliminados de `_constraints.py` (ya no necesarios).

---

### Fase 2 — C1/C2/C3: Conexiones batch + bug PostgreSQL

**C1+C3** (`_constraints.py: _enable_postgresql`):
- Reescrito con dos fases dentro de una sola conexión.
- Fase A: reactivar TRIGGER ALL por tabla; registrar en `failed_trigger` si falla.
- Fase B: validar FKs solo en tablas sin trigger fallido (C3); savepoints PostgreSQL
  para aislar fallos por constraint (`SAVEPOINT sp_validate` / `RELEASE` / `ROLLBACK TO`).
- Una sola conexión del pool en lugar de N `engine.begin()`.

**C2** (`_constraints.py: _disable_oracle` → `_exec_disable_oracle_batch`):
- Nuevo método privado `_exec_disable_oracle_batch(table, names)` que abre una conexión
  por tabla (no por constraint), reduciendo overhead del pool en Oracle.

---

### Fase 3 — O1: Column case mapping

`orchestrator.py: _common_columns` ahora retorna 3-tuple `(common, skipped, name_map)`:
- `dst_by_lower`: dict `lowercase → nombre_real_destino`.
- `name_map = {src_name: dst_by_lower[src_name.lower()]}`.
- `_process_table` aplica `df.rename(columns=name_map)` antes del INSERT para normalizar
  case en BDs case-sensitive (p.ej. origen `UserID` → destino `userid`).

---

### Post — SonarQube S3776 × 2

**S3776 en `_routine_fetchers.py:73`** (cognitive complexity 16 → 10):
Extraído `_mariadb_ddl_from_row(row_or_none, col) → str` como función de módulo.
Reemplaza los dos ternarios `str(row[col] or "") if row else ""` dentro de
`get_routines_mariadb`, eliminando 6 puntos de complejidad cognitiva.

**S3776 en `_constraints.py:207`** (cognitive complexity 16 → 8):
Extraído `_validate_fks_pg(self, conn, table, fks, results) → None` como método privado.
Reemplaza el bloque `for fk in fks: if/try/except` de Fase B en `_enable_postgresql`,
eliminando 8 puntos de complejidad cognitiva.

---

### Post — Pylance reportArgumentType

`_constraints.py: _validate_fks_pg`: parámetro `fks` cambiado de `list[dict[str, Any]]`
a `Sequence[Mapping[str, Any]]` (covariant) para aceptar `list[ReflectedForeignKeyConstraint]`.
`Mapping` y `Sequence` añadidos a `from collections.abc import ...`.

---

### Post — SonarQube S1481 en tests

`test_orchestrator.py:228,234`: `name_map` → `_` en los dos tests que desempaquetan
el 3-tuple de `_common_columns` pero no usan el mapa de nombres.

---

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| CP1/CP2/CP4 | `src/util_bbdd/comparar/comparator.py` | completado |
| RF1/RF2 + S3776 + `_mariadb_ddl_from_row` | `src/util_bbdd/comparar/_routine_fetchers.py` | completado |
| B1 docstring | `src/util_bbdd/comparar/reporters/_base.py` | completado |
| M1 ConstraintResult | `src/util_bbdd/dump/_models.py` | completado |
| C1+C2+C3 + S3776 + Pylance + `_validate_fks_pg` | `src/util_bbdd/dump/_constraints.py` | completado |
| O1+O3 column case mapping | `src/util_bbdd/dump/orchestrator.py` | completado |
| R1 sheet refactor | `src/util_bbdd/dump/reporters.py` | completado |
| Tests C3+TC6 | `tests/unit/dump/test_constraints.py` | completado |
| Tests O1+O3+S1481 | `tests/unit/dump/test_orchestrator.py` | completado |

## Directrices para Futuras IAs

- **[dump/_constraints.py] `_validate_fks_pg`**: acepta `Sequence[Mapping[str, Any]]`, no
  `list[dict]`. SQLAlchemy devuelve `list[ReflectedForeignKeyConstraint]` (TypedDict), que
  es invariante respecto a `list[dict]` pero covariant respecto a `Sequence[Mapping]`.

- **[dump/_constraints.py] PostgreSQL Fase B savepoints**: el savepoint se llama
  `sp_validate`; si se añade otro nivel de savepoints en el mismo bloque, usar nombres
  distintos para evitar conflicto con el `ROLLBACK TO SAVEPOINT sp_validate` existente.

- **[comparar/comparator.py] separador `\x00`**: la clave del routine map usa `\x00`
  como separador entre nombre y tipo. No cambiar a `:` — colisiona con nombres que contienen `:`.
  Ver CP4 en sesión `2026-05-26-comparar-tech-debt`.

- **[dump/orchestrator.py] `_common_columns`**: retorna 3-tuple `(common, skipped, name_map)`.
  El tercer elemento es el mapa de renombrado `{src_col: dst_col}` para BDs case-sensitive.
  Tests que no usan el mapa deben desempaquetar con `_` para evitar S1481.

- **[comparar/_routine_fetchers.py] `_mariadb_ddl_from_row`**: helper de módulo (no método
  de clase). Si se añade soporte de nuevos campos DDL de MariaDB, reutilizar este helper
  en lugar de reintroducir el ternario `str(row[col] or "") if row else ""`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. Tests, ruff y mypy limpios. Todos los diagnósticos SonarQube/Pylance resueltos.
