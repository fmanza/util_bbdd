# TRACEABILITY

## Session metadata

- id: 2026-05-31-pk-sync-post-bulk
- fecha: 2026-05-31
- rama: develop
- skill: new_feature (flujo completo: PLAN × 2 → AUDIT_PLAN × 2 → IMPLEMENT → docs)
- fase: PLAN → AUDIT_PLAN → PLAN (revisado) → AUDIT_PLAN (revisado) → IMPLEMENT → DOCS

## Prompt issued

```
Cuando se realiza una carga máxima de datos los contadores relacionados con las
Primary Key no se actualizan. Revisar src\util_bbdd\dump y src\util_bbdd\bulk
para buscar la mejor implementación, teniendo en cuenta los cuatro motores
actuales (Oracle, MariaDB, SQL Server y PostgreSQL).

[Segunda iteración] Revisar el PLAN para incluir versiones superiores o igual a
de Oracle 12c, para el caso de autoincrement. PONER NUEVO PLAN Y AUDIT PLAN.

[Tercera iteración] Implementar plan.
```

---

## Context supplied

- Código fuente: `src/util_bbdd/bulk/` — crud.py, _support/validation.py, _support/sql_helpers.py, _execution/batch.py
- Código fuente: `src/util_bbdd/dump/` — orchestrator.py, _constraints.py, _models.py, _protocols.py
- Suite de tests existente (3566 tests antes de la sesión)

---

## AI output summary

### Diagnóstico inicial

Ni `bulk` ni `dump` ejecutaban resincronización de contadores PK tras insertar datos con PKs explícitas. El problema afecta a todos los motores con columnas auto-increment:

| Motor | Efecto post-bulk sin sync |
|---|---|
| PostgreSQL | `UniqueViolation` en el próximo INSERT sin PK explícita |
| SQL Server | `PK violation` — IDENTITY por detrás del MAX |
| MariaDB | Colisión en siguiente INSERT sin PK |
| Oracle ≥ 12c | `ORA-00001: unique constraint violated` |

---

### PLAN v1 + AUDIT_PLAN v1

Diseño inicial con `PKSequenceSyncer` (clase nueva en `bulk/_support/pk_sync.py`), `PKSyncResult` (dataclass nueva en `bulk/_models.py`), y Fase 6a en `DumpOrchestrator`.

**Veredicto AUDIT_PLAN v1**: GO_CONDICIONAL — Oracle declarado `"unsupported"` en la iteración inicial (sin metadata declarativa para trigger+sequence pre-12c).

---

### PLAN v2 + AUDIT_PLAN v2 — Oracle 12c+

Segunda iteración del plan incorporando soporte nativo para Oracle ≥ 12c a través de `ALL_TAB_IDENTITY_COLS` / `USER_TAB_IDENTITY_COLS` y `ALTER SEQUENCE ... RESTART START WITH n`.

Cambios respecto a v1:

| Aspecto | v1 | v2 |
|---|---|---|
| Oracle | `"unsupported"` global | ≥ 12c soportado via `ALL_TAB_IDENTITY_COLS` + `ALTER SEQUENCE RESTART` |
| Oracle < 12c | — | `status="unsupported"` explícito (trigger+sequence sin metadata declarativa) |
| Detección | `col.autoincrement or col.identity` | Igual; `col.identity is None` identifica pre-12c |
| Vista Oracle schema | — | `ALL_TAB_IDENTITY_COLS` con schema / `USER_TAB_IDENTITY_COLS` sin schema |

**Veredicto AUDIT_PLAN v2**: GO_CONDICIONAL — 7 condiciones definidas (C1: quoting de `$` en Oracle, C2: separación ALL/USER views, C3: pre-12c unsupported, C4: reutilizar reflect_table cache, C5: opt-out en DumpConfig, C6: tests 5 casos, C7: documentar limitación IDENTITY seed no estándar en MSSQL).

---

### IMPLEMENT

#### Archivos creados

| Archivo | Descripción |
|---|---|
| `src/util_bbdd/bulk/_models.py` | `PKSyncResult` dataclass — 5 campos, `status` Literal con 5 valores |
| `src/util_bbdd/bulk/_support/pk_sync.py` | `PKSequenceSyncer` — clase con dispatch por dialecto + `_get_identity_pk_cols()` helper |
| `tests/unit/bulk/__init__.py` | Paquete de tests para el módulo bulk |
| `tests/unit/bulk/test_pk_sync.py` | 28 tests unitarios (28/28 verdes) |

#### Archivos modificados

| Archivo | Cambio |
|---|---|
| `src/util_bbdd/bulk/crud.py` | +`sync_pk_sequences(tables?)` público; imports `PKSyncResult`, `PKSequenceSyncer` |
| `src/util_bbdd/bulk/__init__.py` | Re-exporta `PKSyncResult` |
| `src/util_bbdd/dump/_models.py` | `DumpConfig` +`sync_pk_sequences: bool = True`; `DumpResult` +`pk_sync_results`; import `PKSyncResult` |
| `src/util_bbdd/dump/orchestrator.py` | +`_sync_pk_sequences()` Fase 6a; `run()` integra resultado; import `PKSyncResult` |
| `src/util_bbdd/dump/__init__.py` | Re-exporta `PKSyncResult` |

#### SQL por motor (producción)

| Motor | Operación |
|---|---|
| **PostgreSQL** | `SELECT setval(pg_get_serial_sequence(tabla, col), MAX(col), true/false)` |
| **SQL Server** | `DBCC CHECKIDENT ('schema.tabla', RESEED, MAX(col))` |
| **MariaDB/MySQL** | `ALTER TABLE tabla AUTO_INCREMENT = MAX(col) + 1` |
| **Oracle ≥ 12c** | `ALTER SEQUENCE schema.ISEQ$$_* RESTART START WITH MAX(col) + 1` |

#### Integración en DumpOrchestrator

Fase 6a insertada **después** del `ConstraintManager.__exit__()` y **antes** de `DumpReporter.generate()`. Usa `crud._table_cache` para evitar segunda ronda de introspección. Opt-out con `DumpConfig.sync_pk_sequences=False`. Best-effort: errores por tabla se capturan en `PKSyncResult.status="error"`.

#### Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3566 | 3594 |
| Tests nuevos | — | +28 |
| ruff | ✅ | ✅ |
| mkdocs build | ✅ | ✅ (sin errores nuevos) |

---

### DOCS

Tres documentos actualizados:

| Archivo | Cambio |
|---|---|
| `docs/api/dump.md` | `DumpConfig` +`sync_pk_sequences`; `DumpResult` +`pk_sync_results`; nueva sección `PKSyncResult` (tabla de status + permisos); imports actualizados; `run()` describe 7 fases |
| `docs/functional/dump-data-export.md` | Diagrama Mermaid: 7 fases con Fase 6a visible; descripción Fase 6a con tabla por motor; "No soporta secuencias" → descripción correcta del soporte actual |
| `docs/api/bulk-crud.md` | `sync_pk_sequences()` en tabla API pública; "Contrato de salida" actualizado para `list[PKSyncResult]` |

---

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| PKSyncResult dataclass | `bulk/_models.py` | ✅ Creado |
| PKSequenceSyncer | `bulk/_support/pk_sync.py` | ✅ Creado |
| BulkCrud.sync_pk_sequences() | `bulk/crud.py` | ✅ Modificado |
| PKSyncResult re-export | `bulk/__init__.py` | ✅ Modificado |
| DumpConfig.sync_pk_sequences | `dump/_models.py` | ✅ Modificado |
| DumpResult.pk_sync_results | `dump/_models.py` | ✅ Modificado |
| DumpOrchestrator Fase 6a | `dump/orchestrator.py` | ✅ Modificado |
| PKSyncResult re-export dump | `dump/__init__.py` | ✅ Modificado |
| Tests unitarios pk_sync | `tests/unit/bulk/test_pk_sync.py` | ✅ Creado (28 tests) |
| Doc API dump | `docs/api/dump.md` | ✅ Modificado |
| Doc funcional dump | `docs/functional/dump-data-export.md` | ✅ Modificado |
| Doc API bulk-crud | `docs/api/bulk-crud.md` | ✅ Modificado |

---

## Directrices para Futuras IAs

- `PKSequenceSyncer` sigue el mismo patrón que `ConstraintManager` (dispatch por dialecto, best-effort, resultados como lista de dataclasses). Para añadir un nuevo motor, implementar `_sync_<dialect>(self, conn, table, col)` y registrarlo en `_get_handler()`.
- Oracle pre-12c (trigger + sequence manual) tiene `status="unsupported"`. El soporte requiere definir la naming convention canónica de sequences del proyecto y leer `ALL_TRIGGERS` con regex. Abrir issue dedicado antes de implementar.
- `PKSequenceSyncer` NO está en el protocolo `BulkInserter` (LSP intacto). `DumpOrchestrator` instancia `PKSequenceSyncer` indirectamente a través de `BulkCrud.sync_pk_sequences()`.
- `DumpConfig.sync_pk_sequences=False` para usuarios que gestionan resincronización manualmente o sin los permisos requeridos por motor (ver tabla de permisos en `docs/api/dump.md`).
- `OLD_VALUE` fue excluido de `PKSyncResult` deliberadamente (requería una query extra por motor). Si el informe Excel lo requiere en el futuro, añadir campo opcional con `None` por defecto.
- La Fase 6a se ejecuta SIEMPRE después del `ConstraintManager.__exit__()`, incluso si `enable_all()` falló parcialmente. El sync sobre contadores PK es independiente del estado de las constraints.

## Veredicto final

**CLOSED** — 3594/3594 tests verdes. `mkdocs build` sin errores nuevos. Sin deuda nueva introducida.
