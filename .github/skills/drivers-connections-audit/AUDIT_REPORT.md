# 🔍 Auditoría: drivers-connections-audit SKILL v1.0.0

> **Documento histórico.** Audita la coherencia interna de la skill v1.0.0, no el código. La ejecución de FASE 1
> (2026-10-08) contra el código refutó varias de las premisas que este informe daba por buenas (MySQL sin catálogo,
> duplicidad de pools ~60 %, validadores solapados, seguridad de MariaDB "PASS"…). Ver el
> [anexo al final](#anexo-contraste-con-fase-1-2026-10-08) y `CORRECTIONS_APPLIED.md` (v1.0.3).

**Fecha**: 2026-10-08  
**Alcance**: `.github/skills/drivers-connections-audit/SKILL.md`  
**Auditor**: GitHub Copilot  
**Severidad**: 8 críticas + 4 mayores + 3 menores

---

## 📋 Resumen Ejecutivo

**Veredicto**: 🟡 **GO_CONDICIONAL** (aprobado con correcciones requeridas antes de FASE 1)

**Fortalezas**:
- ✅ Estructura 6-fases clara y ejecutable
- ✅ MariaDB y MySQL diferenciados como auditorías independientes
- ✅ Tabla de duplicidades bien cuantificada (~60% pool, ~50% config)
- ✅ Charset strategy enum bien diseñado (DETECT, UTF8MB4, NATIVE, CUSTOM)
- ✅ Entregas de cada fase explícitas (audit_phase_2a.md, design_phase_2b.md, etc.)
- ✅ ADR template y commit patterns incluidos

**Debilidades**:
- ❌ Inconsistencias críticas entre FASE 2 (TBD) y FASE 6 (decidido)
- ❌ Módulo `managers/` ignorado en auditoría (scope dice aplica, pero no se audita)
- ❌ MySQL introspection gap sin investigación de raíz
- ❌ CharsetStrategy.DETECT marcado "experimental" pero Changelog lo presenta como stable
- ❌ Falta de mapeo claro entre hallazgos → plan → implementación
- ❌ MariaDB 10.x vs 11.x sin propuesta diferenciada
- ❌ Pool sizing questions sin contexto técnico

---

## 🔴 CRÍTICAS (Bloquean FASE 1)

### C1: Inconsistencia FASE 2 (TBD) vs FASE 6 (Decidido)

**Ubicación**: 2.2 línea ~280 vs 6.1 línea ~600 + 6.2 línea ~650

**Problema**:
```
FASE 2.2 (tabla Decisión por motor):
| **MySQL** | ⚠️ **TBD** | Auditoría independiente requerida | ¿Hereda problemas? |

FASE 6.1 (Changelog):
### Added
- **Charset Strategy** (all engines):
  - Replaces ad-hoc fixes (H-32, H-39) with unified approach

FASE 6.2 (ADR):
**Decision**:
1. Refactor connection layer: abstract base classes eliminate 60% pool duplication
```

**Impacto**: ¿MySQL charset strategy es TBD o UTF8MB4 (por defecto)? ¿Opción A aceptada o aún bajo evaluación?

**Recomendación**:
- Decidir: ¿Ejecutar FASE 1-3 (RECONNAISSANCE + PLANNING) sin commitment a FASE 4, O confirmar Opción A + defaults ahora?
- Si se ejecutan FASES 1-3 ANTES de FASE 4: Cambiar 6.1 y 6.2 a "Placeholder (TBD post-FASE-3)"
- Si se confirma Opción A ahora: Cambiar FASE 2.2 de "TBD" a "UTF8MB4" (propuesto, pendiente validación FASE 1)

---

### C2: Módulo `managers/` Ignorado en Auditoría

**Ubicación**: YAML `applies_to` línea 5 + FASE 1.1-1.4 (ninguna mención)

**Problema**:
```
applies_to: "src/util_bbdd/connection/**,src/util_bbdd/_drivers/**,
            src/util_bbdd/metadata/**,src/util_bbdd/managers/**"
```

Pero en toda la auditoría NO hay preguntas sobre:
- ¿Cómo managers (bulk, dump, introspection) usan connection/charset?
- ¿Managers son conscientes de CharsetStrategy?
- ¿Hay duplicación en managers vs connection (charset handling)?
- ¿Pool usage en managers es eficiente?

**Impacto**: Refactorización de `connection/` puede romper `managers/` si no se audita interacción.

**Recomendación**:
```markdown
### 1.5 Auditoría: Managers Integration (NEW)

**Actividades**:
- Mapear qué managers usan connection/<motor> y metadata/<motor>
- ¿Managers dependen de charset_strategy o es transparente?
- ¿Hay charset-handling code en managers/ que duplica metadata/_charset/?
- Performance: ¿managers crean pool conexiones correctamente?
- Tests: ¿managers tests usan all 7 engines o solo subset?

**Entrega**: Matriz de dependencias managers ↔ connection/metadata
```

---

### C3: MySQL Introspection Gap Sin Raíz

**Ubicación**: 1.2 (línea ~95) + 1.3 MySQL (línea ~155)

**Problema**:
```markdown
**Motor SIN módulo separado**: MySQL ← **INVESTIGAR** (gap crítico)
  - ¿MySQL usa reflection genérica de SQLAlchemy?
  - ¿Debería tener `metadata/mysql/catalog.py` como MariaDB?
  - ¿Cuál es la estrategia: reutilización deliberada o negligencia?
```

Pero NO hay instrucción sobre:
1. ¿Cómo averiguarlo? (grep, read, test, ask codebase owner?)
2. ¿Quién decide si crear metadata/mysql/catalog.py? (FASE 3 Clarificación?)
3. ¿Es este un bloqueador para FASE 4 o investigación paralela?

**Impacto**: Sin respuesta, no se sabe si MySQL refactorización es igual a MariaDB o diferente.

**Recomendación**:
```markdown
### 1.4 Investigación Crítica: MySQL Introspection Strategy (FASE 1 pre-requisite)

Antes de avanzar a FASE 2, responder en tests:

1. **Baseline Test**: ¿MySQL usa reflection o direct SQL?
   pytest tests/metadata/test_mysql_introspection_baseline.py -v
   - Verifica si `src/util_bbdd/metadata/mysql.py` existe o no
   - Si no existe, verify: ¿SQLAlchemy reflection funciona? ¿O hay fallback?
   
2. **Comparison**: Diff `metadata/mariadb/catalog.py` vs cómo MySQL hace lo mismo
   - ¿Código idéntico, similar, diferente?
   - ¿MySQL información_schema compatible con MariaDB?

3. **Decision Gate**: ANTES de FASE 2.1 (Propuestas), decidir:
   - A) Crear metadata/mysql/catalog.py (replica MariaDB)
   - B) Mantener reflection, pero centralizar en metadata/_base/
   - C) MySQL como "legacy, no refactor"
```

---

### C4: CharsetStrategy.DETECT Marcado "Experimental" pero Changelog "Unified"

**Ubicación**: 2.2 línea ~270 (DETECT = "experimental") vs 6.1 línea ~615 ("unified approach")

**Problema**:
```
En 2.2:
DETECT = "detect"      # Auto-detectar estado + fallback (experimental)

En 6.1 Changelog:
- Replaces ad-hoc fixes (H-32, H-39) with unified approach
```

**Contradicción**: ¿DETECT es "experimental" (pre-production, riesgoso) o "unified" (production-ready)?

**Impacto**: Si es experimental, no debería ser default para MariaDB. Si es unified, no debería decir "experimental".

**Recomendación**:
Cambiar 2.2 según estado real:
- Si DETECT (v0.33.0+) es **confiable**: Cambiar a `# Auto-detectar estado + fallback (stable, v0.33.0+)`
- Si DETECT tiene regresiones conocidas: Cambiar 2.2 default MariaDB a `UTF8MB4` con nota "DETECT recomendado tras audit validacion"

---

### C5: Falta Mapeo Hallazgos → Plan → Implementación

**Ubicación**: Transición FASE 1 → 2 → 4

**Problema**:
- FASE 1 entrega: tabla de inventario + matriz duplicidades
- FASE 2 entrega: `audit_phase_2a.md` (hallazgos) + `design_phase_2b.md` (plan)
- FASE 4 entrega: 4 sub-fases (4.1, 4.2, 4.3, 4.4)

Pero NO hay:
- Template o estructura de `audit_phase_2a.md`
- ¿Cómo mapear hallazgo "60% pool boilerplate" → tarea en 4.2?
- ¿Quién decide prioridad? ¿Responsable por sub-fase?
- ¿Qué hace "no API break validation" en 4.2? ¿Qué tests?

**Impacto**: FASE 2A puede generar 500+ hallazgos sin priorización → FASE 4 incoordinated.

**Recomendación**:
```markdown
### 2A: Auditoría Profunda (Code Review) — 4-6h

**Output structure** (audit_phase_2a.md):

## Hallazgos Priorizados

### P0 (CRÍTICO - bloquea FASE 4)
- [ ] H.P0.1: MySQL metadata/mysql/catalog.py (¿existe o no?)
- [ ] H.P0.2: CharsetStrategy DETECT stability (production-ready?)

### P1 (MAYOR - impacta arquitectura)
- [ ] H.P1.1: PoolConnection boilerplate (~60% duplication)
  - Archivos: pool_connection_mariadb.py, pool_connection_mysql.py, ...
  - LoC: ~500 (estimado)
  - Refactor → FASE 4.2 (Sub-fase: Base Classes y Pool Genérico)
  
### P2 (MENOR - nice-to-have)
- [ ] H.P2.1: Charset detection latency impact
  - Baseline pytest: test_charset_detect_latency.py
  
## Por Motor: Hallazgos Específicos

### MariaDB (Auditoría Independiente)
- Security: ✅ Pass (charset validation OK per H-32 fix)
- Performance: ⚠️ Charset detection adds X ms per connection (measure?)
- Bugs: ✓ H-32, H-39 resolved, regresiones? (verify)

### MySQL (Auditoría Independiente)
- Introspection: ❓ HOW? (reflection vs catalog.py)
- Charset: ❓ DOES IT INHERIT H-32, H-39? (test)
- Performance: TBD (depends on introspection strategy)
```

---

### C6: Opción A / B / C sin Cuantificación de Esfuerzo

**Ubicación**: 2.1 línea ~150

**Problema**:
```
#### **Opción A: Por Capas Transversales (Recomendada)**
- Beneficios: ✅ Base classes, ✅ Pool genérico (~500 LoC saved)
- Migraciones: 5 pasos

#### **Opción B: Monolítico Mejorado**
- Beneficios: Menos cambios API, adopción gradual
- Drawbacks: Menos limpio, no escala bien
```

Pero NO se menciona:
- ¿Opción A cuántas horas? (¿20h? ¿40h?)
- ¿Opción B cuántas horas?
- ¿Risk de regresión por opción?
- ¿Compatibility layer effort?
- ¿Test writing effort?

**Impacto**: User no puede decidir Opción A vs B sin esfuerzo estimado.

**Recomendación**:
```markdown
| Opción | Esfuerzo (h) | API Break | Regresión Risk | Test Effort | Recomendación |
|---|---|---|---|---|---|
| A | 35-45 | Sí (Level 2: imports change) | MEDIO | 15h | ✅ Si timeline lo permite |
| B | 15-20 | No (Level 0: compatible) | BAJO | 8h | ✅ Si conservador |
| C | 20-30 | No (Level 0) | ALTO (MCP complexity) | 12h | ❌ Not now |
```

---

### C7: MariaDB 10.x vs 11.x Sin Propuesta

**Ubicación**: 1.3 MariaDB (línea ~145)

**Problema**:
```
- **Preguntas**:
  - ¿Se aplica charset strategy solo a MariaDB o debería ser genérico?
  - ¿El módulo `metadata/mariadb/catalog.py` tiene dependencias en charset detection?
  - ¿Necesita MariaDB 10.x vs 11.x handling diferenciado?
```

Pero NO hay:
- ¿Cuáles son las diferencias entre 10.x y 11.x?
- ¿`information_schema` cambió entre versiones?
- ¿Charset strategy diferente para cada?
- ¿Tests por versión? (tox matrix?)

**Impacto**: Sin saber diferencias, auditoría de MariaDB es incompleta.

**Recomendación**:
```markdown
### MariaDB Version Matrix (FASE 1 investigación requerida)

| Versión | Support | info_schema Changes | Charset Issues | Strategy | Test Coverage |
|---|---|---|---|---|---|
| 10.3 (EOL 2023) | ❌ Drop | — | — | — | — |
| 10.4 (EOL 2024) | ⚠️ LTS (2024-09) | — | — | — | pytest + pyodbc |
| 10.5 (EOL 2025) | ✅ LTS | — | — | — | pytest + mariadb |
| 10.6 (EOL 2026) | ✅ LTS | — | — | — | pytest + mariadb |
| 11.0 (Current) | ✅ GA | ❓ Investigar | ❓ H-32/H-39 still valid? | ❓ TBD | pytest + mariadb |
| 11.1+ (Future) | ✅ Future | ❓ TBD | ❓ TBD | ❓ TBD | pytest |

**Pre-FASE 2 Investigation**:
- pytest tests/metadata/test_mariadb_10vs11_info_schema.py -v
- Verify H-32 (UnicodeDecodeError) still occurs on 11.0
- Verify H-39 (charset in pool) still occurs on 11.0
```

---

### C8: CharsetStrategy.DETECT Sin Fallback Definido

**Ubicación**: 2.2 línea ~260

**Problema**:
```python
class CharsetStrategy(Enum):
    DETECT = "detect"  # Auto-detectar estado + fallback (experimental)
    
def resolve_charset(self, server_info: dict) -> str:
    case CharsetStrategy.DETECT:
        return self._detect_and_remediate(server_info)
```

Pero NO se define:
- ¿`_detect_and_remediate()` qué hace si falla?
- ¿Cuál es el fallback? (UTF8MB4? NATIVE?)
- ¿Se loguea? ¿Se lanza excepción?
- ¿retry logic? ¿timeouts?

**Impacto**: DETECT strategy parece "experimental" porque no hay contrato definido.

**Recomendación**:
```python
class CharsetStrategy(Enum):
    DETECT = "detect"  # Auto-detectar estado + fallback a UTF8MB4

def resolve_charset(self, server_info: dict) -> str:
    """
    Resuelve charset según strategy.
    
    CharsetStrategy.DETECT:
      1. Query server CHARSET state (information_schema.SESSION_VARIABLES)
      2. Validate: client_charset == connection_charset == database_charset
      3. If mismatch:
         - Log warning
         - Fallback to UTF8MB4
         - Set connection charset = UTF8MB4
      4. Return final charset
    """
```

---

## 🟠 MAYORES (Recomendaciones Pre-FASE 1)

### M1: Validators Consolidation Sin Detalle

**Ubicación**: 1.2 línea ~130, 1.3 (no mencionado)

**Problema**: Se menciona consolidación de validadores pero NO hay:
- ¿Cuántos `validators/<motor>_validator.py` existen?
- ¿`_drivers/validator.py` cubre qué?
- ¿Cuál es el overlap?

**Recomendación**:
```bash
# FASE 1 tarea concreta
find src/util_bbdd -name "*validator*.py" -type f | grep -E "(validators|_drivers)"
# Esperado: _drivers/validator.py + validators/mariadb_validator.py + ...

# Luego, hacer diff:
diff -u src/util_bbdd/_drivers/validator.py src/util_bbdd/validators/mariadb_validator.py
# ¿Qué funciones se duplican?
```

---

### M2: Pool Sizing "Sensible por Defecto" Sin Contexto

**Ubicación**: 1.3 Rendimiento (línea ~133)

**Problema**: "¿Pool sizing es configurable y sensible por defecto?" no es concreto.

**Recomendación**: Cambiar a:
```markdown
#### **Rendimiento**:
- Pool sizing: ¿Cuál es el default? (min=?, max=?)
  - MariaDB: pool.py → MariaDBPoolConfig defaults
  - MySQL: pool.py → MySQLPoolConfig defaults
  - Per-engine defaults sensatos? (compare con industry standard SQLAlchemy)
```

---

### M3: "Managers Integration" Missing Desde Inicio

**Ubicación**: YAML applies_to vs auditoría

**Recomendación**: Crear sección 1.5 que audite:
- bulk manager: ¿usa connection pool? ¿charset strategy?
- dump manager: ¿schema detection? ¿charset issues?
- introspection manager: ¿depende de metadata/<motor>/catalog.py?

---

### M4: FASE 6.4 Logging Sin Integration

**Ubicación**: 6.4 línea ~670

**Problema**: Se propone logging de charset resolution pero:
- ¿Dónde se loguea? (managers, connection, metadata/_charset/?)
- ¿Qué logger? (util_bbdd.metadata? util_bbdd.connection?)
- ¿Log level? (DEBUG? WARNING?)
- ¿Tests?

**Recomendación**: Concretar en FASE 4.1:
```python
# src/util_bbdd/metadata/_charset/strategy.py

import logging
logger = logging.getLogger("util_bbdd.metadata.charset")

class CharsetStrategy:
    def resolve_charset(self, server_info):
        logger.debug(f"Resolving charset: strategy={self.strategy}, server_info={server_info}")
        ...
        logger.warning(f"Charset fallback: {original} → {fallback}")
```

---

## 🟡 MENORES (Mejoras Opcionales)

### N1: FASE 2.3 "Plan de Ejecución" vs FASE 4 "IMPLEMENT"

¿Cuál es la diferencia? ¿2.3 es alto nivel y 4 es detalle? Clarificar.

### N2: 1.4 "Investigación Requerida" Code Sample Sin tests

Cambiar a:
```bash
# pytest test file template, not pseudocode
pytest tests/metadata/test_charset_investigation.py -v -s
```

### N3: Referencias § No Referencia a `pyproject.toml`

Se menciona en `requires_context` pero no se cita. Agregar referencias a:
- `pyproject.toml` [project.optional-dependencies]
- `pyproject.toml` [project.optional-dependencies.drivers]

---

## 📋 Checklist de Correcciones

**Antes de ejecutar FASE 1:**

- [ ] **C1**: Decidir FASE 2 (TBD) vs FASE 6 (Decidido) → consistencia
- [ ] **C2**: Agregar sección 1.5 "Managers Integration"
- [ ] **C3**: Agregar "1.4 Investigación Crítica: MySQL Introspection Strategy" como pre-requisito
- [ ] **C4**: Resolver CharsetStrategy.DETECT "experimental" vs "unified"
- [ ] **C5**: Template de `audit_phase_2a.md` con estructura clara
- [ ] **C6**: Tabla Opción A/B/C con Esfuerzo y Risk
- [ ] **C7**: Matriz MariaDB 10.x vs 11.x con tests
- [ ] **C8**: Definir fallback de `_detect_and_remediate()` explícitamente
- [ ] **M1**: Inventory existing validators
- [ ] **M2**: Especificar pool sizing defaults por motor
- [ ] **M3**: Sección 1.5 Managers
- [ ] **M4**: Logger names concretos para charset resolution
- [ ] **N1-N3**: Mejoras menores (claridad, referencias)

---

## 🎯 Veredicto Final

**Status**: 🟡 **GO_CONDICIONAL**

**Próximo Paso**:
1. Resolver las 8 CRÍTICAS (C1-C8)
2. Aplicar MAYORES (M1-M4) para precisión
3. Ejecutar FASE 1 RECONNAISSANCE con checklists actualizados
4. Entregar `audit_phase_2a.md` priorizando P0 hallazgos (MySQL introspection, DETECT stability)

**Versión Target**: 1.0.1 (con correcciones pre-FASE-1)

---

*Auditoría completada: 2026-10-08 | Severidad: MEDIA | Bloqueadores: Sí (8 críticas) | Recomendación: Correcciones requeridas antes FASE 1*

---

## Anexo: contraste con FASE 1 (2026-10-08)

Puntos de este informe que la ejecución de FASE 1 sobre el código (v0.35.4) contradice:

| Punto del informe | Lo que dice | Resultado de FASE 1 |
|---|---|---|
| Fortalezas | "Tabla de duplicidades bien cuantificada (~60 % pool, ~50 % config)" | Cifras estimadas, no medidas: 6 pools con 32 % de similitud media; la duplicidad real está en cierre de pools, DSN Oracle, mapeo aiomysql y factories |
| C3 | "MySQL introspection gap" como crítica pendiente | No hay gap: `MySQLCatalog(MariaDBCatalog)` en `metadata/mariadb/catalog.py:476`. Decisión cerrada |
| C3 / C7 / N2 | Tests propuestos (`test_mysql_introspection_baseline.py`, `test_mariadb_10vs11_info_schema.py`, `test_charset_investigation.py`) | No existen |
| C4 / C8 | DETECT a tratar como "stable" | v0.35.4 tiene 5 tests rojos en `test_charset_detection.py`; DETECT solo actúa en sync y sin pool en MySQL |
| C5 | Plantilla con "MariaDB Security: ✅ Pass" | `charset` sin lista blanca, `init_command` libre, `charset`/`init_command` incoherentes |
| M1 | Overlap entre `_drivers/validator.py` y `validators/<motor>_validator.py` | No hay overlap (validan cosas distintas); la divergencia real es entre builder.py, la lista blanca JSON y `*Config.from_params` |
| M3 | bulk/dump "¿usan connection pool?" | No: reciben un `Engine` de SQLAlchemy |
| — (no detectado) | — | Los 5 P0 de FASE 1 (S1, B1, B2, S4, T1) no estaban en el radar de este informe |

El estado vigente está en `SKILL.md` v1.0.3 y en `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md`.
