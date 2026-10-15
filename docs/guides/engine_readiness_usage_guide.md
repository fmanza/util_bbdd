# Guía: Usar el Prompt Integrado de EngineReadinessAdvisor

## Propósito

Fichero: `.github/prompts/engine_readiness_integration.prompt.md`

Integra la información de `EngineReadinessAdvisor` (`src/util_bbdd/connection/performance_advisor.py`)  
en tres contextos **obligatorios**:

1. **Auditoría de rendimiento del módulo `bulk`** ✅ (siempre)
2. **Auditoría de rendimiento del módulo `dump`** ✅ (siempre)
3. **Documentación técnica del módulo `doc`** ✅ (siempre)

---

## 📖 Cómo usar: Contexto por Contexto

### 1️⃣ Auditoría de Rendimiento — Módulo `bulk`

**Cuándo**: Necesitas optimizar operaciones INSERT/UPDATE/DELETE masivas con `BulkCrud`

**Flujo recomendado**:

```markdown
# En Claude Code o Copilot Chat

/performance-audit-bulk

Objetivo: Optimizar velocidad de INSERT con paralelización
Baseline: Medir con `scripts/bench_bulk.py` (100K registros, MySQL)
Dialects: MySQL + PostgreSQL
Timeline: ASAP

Pre-requisito: Leer .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 1: Auditoría de rendimiento — Módulo `bulk`"

Esto asegura que:
- Validaremos readiness del engine ANTES de optimizar
- Identificaremos bloqueadores de configuración pool/driver
- Documentaremos pre-requisitos en deliverables
```

**Qué validarás**:
- ✅ `BulkCrud.__init__()` invoca `EngineReadinessAdvisor.report_once(engine)`
- ✅ Logs muestran checks de pool_size, timeouts, autocommit
- ✅ WARNING o CRITICAL se tratan como bloqueadores de optimización
- ✅ Documentación menciona "Validación de Readiness" antes de tuning

**Resultado esperado** en audit report:
```
## Pre-requisitos de Configuración (Engine Readiness)

Motor: MySQL
Checks críticos:
- pool_size: 5 (mínimo) — ✅ CUMPLIDO
- write_timeout: 30 s (crítico: ≥60 s para bulk) — ⚠️ AVISO
- autocommit: False — ✅ CUMPLIDO

Recomendación: Aumentar `write_timeout` a 60 s antes de paralelización.
```

---

### 2️⃣ Documentación Técnica — Módulo `doc` (OBLIGATORIO)

**Cuándo**: Siempre (parte de cada auditoría)  
**Responsabilidad**: Generar `docs/api/engine_readiness_advisor.md` con diagrama y ejemplos

**Flujo recomendado** (obligatorio):

```markdown
# En Claude Code

Lee .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 2: Documentación técnica — Módulo `doc`"

Genera documentación técnica de src/util_bbdd/connection/performance_advisor.py
usando .github/prompts/technical_doc.prompt.md

Detalles obligatorios:
- Tipo de diagrama: classDiagram (AdvisoryFinding + EngineReadinessAdvisor)
- Ubicación: docs/api/engine_readiness_advisor.md (NUEVA)
- Actualizar mkdocs.yml: Agregar bajo "Técnica > API > Connection"
- Ejemplos: Llamada básica, integración en BulkCrud, con conexión explícita

Validación:
- Diagrama Mermaid válido (zensical build --strict)
- Todos los checks por motor documentados (tabla)
- Ejemplos verificables contra código real
```

**Qué incluirá**:
- ✅ Diagrama Mermaid `classDiagram` de AdvisoryFinding + EngineReadinessAdvisor
- ✅ Tabla de checks disponibles por motor (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake)
- ✅ 3 ejemplos prácticos (básico, integración bulk, con conexión)
- ✅ Contratos de entrada/salida
- ✅ Integración en mkdocs.yml

**Archivo generado**:
- `docs/api/engine_readiness_advisor.md` (nueva)

---

### 3️⃣ Auditoría de Rendimiento — Módulo `dump`

**Cuándo**: Necesitas optimizar operaciones de volcado de datos masivos con `DumpOrchestrator`

**Flujo recomendado**:

```markdown
# En Claude Code o Copilot Chat

/performance-audit-dump

Objetivo: Optimizar volcado PostgreSQL → MySQL (3,5M registros)
Baseline: Medir con `scripts/bench_dump.py` (captura previa)
Dialects: PostgreSQL origen, MySQL destino
Timeline: ASAP

Pre-requisito: Leer .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 3: Auditoría de rendimiento — Módulo `dump`"

Esto asegura que:
- Validaremos readiness AMBOS engines (origen + destino)
- Identificaremos bloqueadores de pool/driver en destino
- Documentaremos checks pre-volcado en deliverables
```

**Qué validarás**:
- ✅ `DumpOrchestrator.run()` invoca `EngineReadinessAdvisor.report_once()` para ambos engines
- ✅ Checks se ejecutan ANTES de deshabilitar constraints (Fase 2)
- ✅ Logs muestran WARNING/CRITICAL bloqueadores para destino
- ✅ Recomendaciones incluyen tuning de engine destino (parallelismo, recovery model, etc.)

**Resultado esperado** en audit report:
```
## Fase 2: Validación de Readiness — Engine Destino

Motor destino: MySQL 8.0
Checks:
- pool_size: 20 (con ParallelBulkLoader) — ✅ OK
- max_allowed_packet: 16 MB, chunk_size*row_width: ~50 MB — 🔴 CRÍTICO
- autocommit: False — ✅ OK

Acción requerida: Aumentar max_allowed_packet a ≥64 MB antes de iniciar volcado.
Timeline: Bloquea implementación.
```

---

## 🚀 Ejemplos de Invocación

### Escenario 1: Solo Auditoría de Bulk

```markdown
# En Claude Code

/performance-audit-bulk

Objetivo: Optimizar INSERT con paralelización
Baseline: MySQL (100K registros)
Timeline: ASAP
Dialects: PostgreSQL + MySQL

Pre-requisito: Leer .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 1"

Entregables:
- Auditoría de rendimiento bulk
- Pre-requisitos de EngineReadinessAdvisor incluidos en report
```

### Escenario 2: Auditoría de Bulk + Dump + Documentación

```markdown
# En Claude Code

# Paso 1: Auditoría bulk

/performance-audit-bulk

Objetivo: Optimizar INSERT con paralelización
Baseline: MySQL (100K registros)
Timeline: ASAP
Dialects: PostgreSQL + MySQL

# Paso 2: Auditoría dump

/performance-audit-dump

Objetivo: Optimizar volcado PostgreSQL → MySQL (3,5M registros)
Baseline: Pre-medición con bench_dump.py
Timeline: ASAP
Dialects: PostgreSQL origen, MySQL destino

# Paso 3: Documentación técnica (OBLIGATORIA)

Lee .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 2: Documentación técnica"

Genera documentación técnica de src/util_bbdd/connection/performance_advisor.py
usando .github/prompts/technical_doc.prompt.md

Tipo de diagrama: classDiagram
Ubicación: docs/api/engine_readiness_advisor.md
Actualizar: mkdocs.yml → Agregar bajo "Técnica > API > Connection"

Validación:
- Diagrama Mermaid válido (zensical build --strict)
- Tabla de checks por motor (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake)
- 3 ejemplos verificables contra código real

Entregables:
- docs/api/engine_readiness_advisor.md (NUEVA)
- mkdocs.yml actualizado
- Diagrama Mermaid validado
```

### Escenario 3: Condiciones del motor en la documentación de la BD (OPCIONAL)

La verificación sale como sección «Condiciones del motor» de `DatabaseDocumentation` (Word, Excel y HTML), al final
del documento como el inventario de almacenamiento:

```python
from pathlib import Path

from util_bbdd import SyncDatabaseManager
from util_bbdd.doc import DatabaseDocumentation

with SyncDatabaseManager("postgresql", conn_params) as manager:
    result = DatabaseDocumentation(
        manager,
        Path("docs_bd"),
        imprimir={
            "tablas": {"imprimir_tablas": True},
            "condiciones_motor": {"imprimir_condiciones_motor": True},
        },
        formatos=["word", "excel", "html"],
    ).generate()

print(result.outputs)  # {"word": Path(...), "excel": Path(...), "html": Path(...)}
```

Sin documentar el esquema, el mismo informe está disponible directamente:

```python
from util_bbdd.connection import EngineReadinessAdvisor

report = EngineReadinessAdvisor().assess("postgresql", {"pool_size": 5})
print(report.supported, report.dynamic, [(f.level, f.param) for f in report.findings])
```

### Escenario 4: Auditoría Completa (Bulk + Dump + Docs + Condiciones del motor)

```markdown
# Paso 1: Auditoría bulk + dump (como Escenario 2)

# Paso 2: Documentación técnica (como Escenario 2)

# Paso 3: Documentación de la BD con la sección de condiciones del motor (Escenario 3)

Lee .github/prompts/engine_readiness_integration.prompt.md
Sección: "Integración 2b: Sección «Condiciones del motor» en DatabaseDocumentation"
```

---

## 🎯 Resumen de Integraciones

| Contexto | Prompt base | Integración | Obligatorio | Entrada | Salida |
|---|---|---|---|---|---|
| **Auditoría bulk** | `.../performance_audit_bulk.prompt.md` | Integración 1 | ✅ | Pool config, timeouts | Pre-requisitos en report |
| **Auditoría dump** | `.../performance_audit_dump.prompt.md` | Integración 3 | ✅ | Engine origen + destino | Checks Fase 2 en report |
| **Documentación doc** | `.../technical_doc.prompt.md` | Integración 2 | ✅ | EngineReadinessAdvisor.py | [`docs/api/engine_readiness_advisor.md`](../api/engine_readiness_advisor.md) |
| **Condiciones del motor en doc** | `.../engine_readiness_integration.prompt.md` | Integración 2b | 🔲 | `imprimir["condiciones_motor"]` | Sección en Word/Excel/HTML |

---

## 🔗 Referencias Rápidas

### Ficheros implicados
- **Fuente**: `src/util_bbdd/connection/performance_advisor.py`
- **Prompts de auditoría**:
  - `.github/prompts/performance_audit_bulk.prompt.md`
  - `.github/prompts/performance_audit_dump.prompt.md`
- **Prompt de documentación**: `.github/prompts/technical_doc.prompt.md`
- **Prompt integrado (este)**: `.github/prompts/engine_readiness_integration.prompt.md`

### Clase principal
```python
from util_bbdd.connection import EngineReadinessAdvisor

advisor = EngineReadinessAdvisor()
# Checks estáticos
findings = advisor.check("postgresql", {"host": "localhost", "pool_size": 5})
# Reporta en una sola llamada al logger
advisor.report("postgresql", conn_params, connection=conn)
# Una sola vez por engine en el proceso (thread-safe)
advisor.report_once(engine)
```

### Motores soportados
`postgresql` | `mysql` | `mariadb` | `oracle` | `mssql` | `sqlserver` | `sqlite` | `snowflake`

### Niveles de hallazgo
`OK` (✅) | `INFO` (ℹ️) | `WARNING` (⚠️) | `CRITICAL` (🔴)

---

## ✅ Checklist Pre-Auditoría

Antes de iniciar cualquier auditoría (bulk, dump o documentación), verifica:

- [ ] He leído `.github/prompts/engine_readiness_integration.prompt.md`
- [ ] He identificado el contexto (bulk, dump, ambas)
- [ ] He leído las secciones "Integración 1" (bulk), "Integración 3" (dump) e "Integración 2" (doc)
- [ ] He localizado el código fuente a auditar (`src/util_bbdd/bulk/crud.py`, `dump/orchestrator.py`, `connection/performance_advisor.py`)
- [ ] He preparado inputs: baseline, dialects, timeline
- [ ] Solicito a usuario: ¿Se ejecuta `report_once()` en el código? (Sí/No)
- [ ] Documentación: Confirmo que `docs/api/` será generado y `mkdocs.yml` será actualizado

---

*Última actualización: 2026-10-15*
