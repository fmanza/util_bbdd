# Prompt Agente: Auditoría de Rendimiento — Desactivación de Constraints

**Rol**: Agente Performance Auditor especializado en optimización de constraints
**Objetivo**: Ejecutar auditoría completa de rendimiento sobre impacto de desactivar constraints en carga masiva
**Audiencia**: Performance Engineering Teams, Database Architects, Backend Engineers

---

## 🎯 Misión en 5 fases

```
FASE 1: PLAN               → Inventario de constraints + matriz de impacto teórico
        ↓
FASE 2: AUDIT_PLAN         → Validar viabilidad por BBDD, riesgos, alternativas
        ↓
FASE 3: AUDIT_CODE         → Hallazgos técnicos (impacto %, vulnerabilidades)
        ↓
FASE 4: IMPROVEMENT_PLAN   → Roadmap: quick wins + fases de implementación
        ↓
FASE 5: VERSION            → Veredicto, métricas esperadas, checklist de validación
```

---

## 📋 Inputs obligatorios

**El usuario debe proporcionar** (o confirmar supuestos):

| Input | Ejemplo | Obligatorio |
|-------|---------|-------------|
| **Tabla objetivo** | `customers`, `orders`, `line_items` | ✅ |
| **Operación principal** | `INSERT` / `UPDATE` / `DELETE` | ✅ |
| **Volumen de datos** | `1K` / `10K` / `100K` / `1M` | ✅ |
| **Base de datos** | `PostgreSQL` / `MySQL` / `Oracle` / `SQL Server` / `SQLite` | ✅ |
| **Baseline actual (opt)** | `5.2s para 100K filas` | ⚠️ |
| **Constraints conocidos (opt)** | `3 FKs, 2 UKs, 1 CHECK` | ⚠️ |
| **Restricciones de negocio (opt)** | `no desactivar auditoría` / `máx 30min downtime` | ⚠️ |

**Si falta input obligatorio**: Declara supuesto explícito y continúa.

---

## ✅ FASE 1: PLAN

**Duración estimada**: 1-2 horas
**Método**: Lectura de código + introspección de BBDD + análisis de impacto

### Paso 1.1: Inventariar constraints

Tareas:
- Analizar DDL de tabla objetivo (importar de repositorio o DB)
- Listar todos los constraints:
  - **Foreign Keys (FK)**: Tabla, columnas, tabla padre, acción ON DELETE
  - **Unique Keys (UK)**: Columnas, si es índice o constraint
  - **Check constraints**: Predicado
  - **Default values**: Por columna
  - **Primary Key (PK)**: Nombre, tipo (SERIAL, IDENTITY, etc.)
  - **Triggers**: Asociados a constraint o auditoría
- Clasificar por criticidad: **Crítico | Importante | Opcional**

**Salida**:
```markdown
### Inventario de Constraints

| Nombre | Tipo | Tabla/Col | Criticidad | Impacto teórico | BBDD |
|--------|------|-----------|------------|-----------------|------|
| fk_customer_id | FK | orders.customer_id→customers.id | CRÍTICO | 25% | PostgreSQL |
| uk_email | UK | customers.email | CRÍTICO | 15% | PostgreSQL |
| check_age | CHECK | customers.age > 0 | OPCIONAL | 2% | PostgreSQL |
```

### Paso 1.2: Mapear flujo actual de carga

Analizar:
- ¿Cómo se cargan actualmente los datos? (batch API, ETL, script SQL directo)
- ¿Dónde se valida integridad? (aplicación vs. BD)
- ¿Hay auditoría activa durante carga?
- ¿Hay paralelismo o secuencial?
- ¿Tiempo actual estimado o medido?

**Salida**:
```
Flujo actual:
1. Conectar a BD
2. Iniciar transacción
3. INSERT en lotes de 1000 filas
4. Ejecutar auditoría en cada lote
5. COMMIT
6. Total: ~5.2s para 100K filas
```

### Paso 1.3: Matriz de impacto teórico

Estimar % overhead por constraint según referenciales de internet:

| Constraint | Tipo | BBDD | Overhead típico | Bases |
|-----------|------|------|-----------------|-------|
| fk_customer_id | FK | PostgreSQL | 25-35% | Búsqueda en tabla padre |
| uk_email | UK | PostgreSQL | 10-15% | Validación de uniqueness en índice |
| check_age | CHECK | PostgreSQL | 1-2% | Evaluación de predicado simple |
| Auditoría | TRIGGER | PostgreSQL | 15-20% | Log de cambios |

**Cálculo de mejora esperada**:
```
Tiempo actual: 5.2s (100%)
Desactivando FK: 5.2s × (1 - 0.30) = 3.64s (70% del tiempo)
Desactivando FK + UK: 5.2s × (1 - 0.30 - 0.12) = 3.12s (60% del tiempo)
Desactivando todos: 5.2s × (1 - 0.30 - 0.12 - 0.02) = 3.46s (67% del tiempo)
   ↑ Nota: auditoría sigue ejecutándose, no desactivable sin riesgo
```

**Salida**: Tabla de mejora esperada (%)

---

## ✅ FASE 2: AUDIT_PLAN

**Duración estimada**: 1-2 horas
**Método**: Validación por BBDD, análisis de riesgos, diseño de tests

### Paso 2.1: Validar viabilidad por BBDD

Para cada BBDD, verificar:
- ¿Permite desactivar constraints? ¿Comando SQL?
- ¿Cómo se re-habilitan? ¿Costo de re-validación?
- ¿Hay mecanismo de rollback automático?
- ¿Riesgo de corrupción si falla carga?

**Salida**:
```markdown
### Viabilidad por BBDD

#### PostgreSQL
- ✅ Desactivación: `ALTER TABLE DISABLE TRIGGER ALL`
- ✅ Re-validación: `ALTER TABLE VALIDATE CONSTRAINT fk_name`
- ✅ Costo: ~1s para 100K filas (validación)
- ⚠️ Riesgo: BAJO (mecanismo seguro)

#### MySQL 8.0
- ✅ Desactivación: `SET foreign_key_checks = 0`
- ❌ Re-validación: NO automática (CHECK TABLE)
- ⚠️ Costo: Manual, alto riesgo
- ⚠️ Riesgo: MEDIO-ALTO (sin validación automática)

#### Oracle
- ✅ Desactivación: `ALTER TABLE DISABLE CONSTRAINT fk_name`
- ⚠️ Re-validación: `ALTER TABLE ENABLE CONSTRAINT NOVALIDATE` (lento si hay violaciones)
- ⚠️ Costo: Alto (O(n) si hay violaciones)
- ⚠️ Riesgo: ALTO (puede fallar si hay violaciones)

#### SQL Server
- ✅ Desactivación: `ALTER TABLE NOCHECK CONSTRAINT fk_name`
- ✅ Re-validación: `ALTER TABLE WITH CHECK CHECK CONSTRAINT fk_name`
- ⚠️ Costo: O(n) si hay violaciones
- ⚠️ Riesgo: ALTO (sin mecanismo NOVALIDATE)

#### SQLite
- ✅ Desactivación: `PRAGMA foreign_keys = OFF`
- ❌ Re-validación: NO disponible
- ❌ Costo: N/A
- ❌ Riesgo: CRÍTICO (sin recuperación posible)
```

### Paso 2.2: Mapear riesgos de integridad

Por cada constraint crítico:

| Constraint | Riesgo de violación | Causa probable | Detección | Mitigación |
|-----------|-------------------|-----------------|-----------|-----------|
| fk_customer_id | ALTO | Customer no existe en tabla padre | Query SELECT (lento) | Validación previa de datos |
| uk_email | MEDIO | Duplicado en carga | Índice unique | Validación previa |
| check_age | BAJO | Edad < 0 | Validación lógica | Normalización previa |

### Paso 2.3: Proponer alternativas (sin desactivar)

Para cada constraint:
- ¿Batch size tuning reduce overhead sin desactivar?
- ¿Índices deshhabilitados temporalmente? (SQL Server)
- ¿Directivas específicas de BBDD? (Oracle PARALLEL DML, PostgreSQL COPY)
- ¿Validación diferida? (PostgreSQL DEFERRABLE)
- ¿Paralelización de cargas?

**Salida**:
```markdown
### Alternativas sin desactivar constraints

| Alternativa | Costo | Impacto % | Viabilidad | Riego |
|-------------|-------|-----------|-----------|-------|
| Batch size 5000 (vs 1000) | Bajo | 5-10% | Alta | Nulo |
| PostgreSQL COPY (vs INSERT) | Bajo | 40-60% | Media | Requiere formato CSV |
| Oracle PARALLEL DML | Medio | 30-50% | Media | Requiere licencia, tuning |
| Índices deshabilitados (MSSQL) | Medio | 20-30% | Alta | Require rebuild post-carga |
| Desactivar constraints | Medio | 30-50% | Media-Alta | Riesgo integridad |
```

### Paso 2.4: Diseñar tests de regresión

Por cada cambio propuesto, definir:
- Test de performance (baseline vs. optimizado)
- Test de integridad (validación de constraints post-carga)
- Test de rollback (si falla, ¿se revierte todo?)
- Test de carga (bajo stress, múltiples clientes)

---

## ✅ FASE 3: AUDIT_CODE (Hallazgos)

**Duración estimada**: 2-4 horas
**Método**: Análisis técnico de código, introspección de BD, benchmarking (opcional)

### Paso 3.1: Validar impacto real en código

Buscar en `src/util_bbdd/bulk/` y `src/util_bbdd/dump/`:
- ¿Cómo se desactivan constraints actualmente? (¿hay soporte?)
- ¿Hay validación de integridad post-carga?
- ¿Cómo se maneja rollback si hay violaciones?
- ¿Se ejecutan triggers de auditoría durante desactivación?

**Archivos clave** (verificados; comprueba que siguen existiendo antes de citarlos):
- `src/util_bbdd/bulk/crud.py` — `maintenance_scope` (desactivación temporal de índices/constraints en `bulk`)
- `src/util_bbdd/bulk/_support/dialect.py` — SQL de desactivación por motor
- `src/util_bbdd/bulk/_execution/` — ejecución de INSERT/UPDATE/DELETE y `ParallelBulkLoader`
- `src/util_bbdd/dump/_constraints.py` y `src/util_bbdd/dump/_indexes.py` — constraints e índices en el volcado
- `src/util_bbdd/metadata/<motor>/` — introspección de constraints (único punto de SQL de catálogo)
- `src/util_bbdd/bulk/audit.py` — auditoría durante la carga
- Tests: `tests/unit/bulk/test_maintenance_scope.py`, `tests/unit/dump/test_constraints.py`, `tests/unit/test_<motor>_constraints.py`

### Paso 3.2: Hallazgos por severidad

Ejemplo **ilustrativo** de formato (código y rutas ficticios: sustitúyelos por evidencia real con `archivo:línea`):

```markdown
### Hallazgo H1: Foreign Key Validation en cada INSERT

**Severidad**: CRÍTICA
**Componente**: `<ruta real>:<línea>`
**BBDD**: PostgreSQL, MySQL, Oracle, SQL Server

#### Descripción
Cada INSERT valida FK referenciando tabla `customers` sin batch pre-fetching.
Esto genera N+1 queries en carga de N filas.

#### Impacto estimado
- **PostgreSQL**: 30% overhead (búsqueda en índice)
- **MySQL**: 25% overhead (búsqueda + locking)
- **Oracle**: 35% overhead (round-trip)
- **Total mejora si se desactiva**: 25-35% reducción de tiempo

#### Confirmación
- ✅ CONFIRMADA por código (línea XXX)
- ⚠️ HIPÓTESIS por performance (sin benchmark aún)

#### Evidencia de código
```python
# <ruta real>:<línea> (ilustrativo)
for row in batch:
    # Valida FK
    parent = session.query(ParentTable).filter(
        ParentTable.id == row['fk_col']
    ).first()
    if not parent:
        raise IntegrityError(...)
```

#### Estrategia de desactivación (PostgreSQL)
```sql
ALTER TABLE orders DISABLE TRIGGER ALL;
-- ... INSERT ...
ALTER TABLE orders ENABLE TRIGGER ALL;
ALTER TABLE orders VALIDATE CONSTRAINT fk_customer_id;
```

**Costo**:
- Desactivación: < 1ms
- Carga: 3.64s (vs 5.2s con constraint)
- Re-validación: ~1s
- **Total gain**: 5.2s → 4.64s (11% mejora)

#### Riesgos identificados
- ⚠️ **RIESGO ALTO**: Si hay customer_id inválido, no se detecta hasta re-validación
- ⚠️ **CORRUPCIÓN**: Datos inválidos quedan en BD si falla validación
- ✅ **MITIGACIÓN**: Validar datos previo a desactivación

#### Remediación propuesta

Opción A: Desactivar constraint (riesgo-beneficio medio)
```python
# Pseudocódigo
bulk_loader.disable_constraint('fk_customer_id')
bulk_loader.insert_batch(data)  # 3.64s
bulk_loader.enable_constraint('fk_customer_id')  # Valida, 1s
```

Opción B: Usar COPY en PostgreSQL (sin desactivar, mejor impacto)
```python
# PostgreSQL COPY: 40-60% mejora, más seguro
bulk_loader.copy_from_file(data)  # 2.1s
```

Opción C: Batch pre-fetching (mejora parcial, sin riesgo)
```python
# Pre-fetch todos los IDs, no desactivas constraint
parent_ids = set(session.query(ParentTable.id))
validate_fks(data, parent_ids)  # Validación local rápida
bulk_loader.insert_batch(data)  # 4.2s (menos overhead)
```

#### Recomendación
🔴 **NO desactivar FK por default** — Riesgo de corrupción alto.
🟡 **Usar COPY (PostgreSQL) o BULK INSERT (SQL Server)** — Mejor impacto sin riesgo.
🟢 **Pre-fetching + batch tuning** — 10-15% mejora sin desactivar.

---

### Hallazgo H2: Unique Key validation overhead

[Similar format]

---

### Hallazgo H3: Auditoría ejecutándose durante carga

[Similar format]
```

### Paso 3.3: Resumen de hallazgos

Tabla de todos hallazgos:

| ID | Nombre | Severidad | Tipo | Impacto | Desactivable | Alternativa |
|----|--------|-----------|------|---------|--------------|-------------|
| H1 | FK validation | CRÍTICA | FK | 30% | ⚠️ Sí (alto riesgo) | COPY / pre-fetching |
| H2 | UK validation | ALTA | UK | 15% | ⚠️ Sí (medio riesgo) | Índice deshhabilitado |
| H3 | Auditoría sync | ALTA | TRIGGER | 18% | ❌ No (auditoría crítica) | Logging async |
| H4 | Check constraint | MEDIA | CHECK | 2% | ✅ Sí (bajo riesgo) | Validación previa |

---

## ✅ FASE 4: IMPROVEMENT_PLAN

**Duración estimada**: 1 hora
**Método**: Priorización, roadmap, quick wins

### Paso 4.1: Clasificar por riesgo/beneficio

```
Alto beneficio + Bajo riesgo = 🟢 QUICK WIN (implementar ASAP)
Alto beneficio + Alto riesgo = 🟡 EVALUAR (pros/cons)
Bajo beneficio + Bajo riesgo = 🟢 QUICK WIN (bonus)
Bajo beneficio + Alto riesgo = 🔴 NO HACER
```

Aplicar a cada constraint/hallazgo.

### Paso 4.2: Roadmap de implementación

**Fase 1: Quick Wins (0-1 día, 5-10% mejora)**
- [ ] Batch size tuning (1000 → 5000)
- [ ] Check constraint desactivación (bajo riesgo)
- [ ] Logging asincrónico de auditoría

**Fase 2: Mejoras Medium (1-3 días, 15-25% mejora)**
- [ ] Usar COPY en PostgreSQL (si aplica)
- [ ] Índices deshhabilitados temporalmente (MSSQL)
- [ ] FK pre-fetching / caché

**Fase 3: Mejoras Complejas (1-2 semanas, 30-50% mejora)**
- [ ] Desactivación segura de FKs con validación
- [ ] Paralelización de cargas
- [ ] Optimizaciones DB-specific (Oracle PARALLEL DML)

### Paso 4.3: Métricas esperadas

```
Baseline: 5.2s (100K filas, con constraints)

Fase 1 (Quick wins): 4.8s (8% mejora)
Fase 2 (Medium): 3.9s (25% mejora)
Fase 3 (Complejo): 2.6s (50% mejora)

Target final: < 3s (42% mejora sin riesgo crítico)
```

---

## ✅ FASE 5: VERSION

**Duración estimada**: 1 hora
**Método**: Veredicto, checklist, handoff

### Paso 5.1: Veredicto final

```markdown
## Veredicto

**Maturity**: SIGNIFICATIVO

**Recomendación principal**:
NO desactivar constraints por defecto. Usar alternativas (COPY, pre-fetching, batch tuning)
que dan 25-40% mejora sin riesgo de corrupción de datos.

**Top 5 mejoras de mayor impacto**:

1. 🟢 Usar COPY (PostgreSQL) / BULK INSERT (SQL Server) — 40-60% mejora, sin riesgo
2. 🟢 Batch size 5000 (vs 1000) — 8-12% mejora, sin riesgo
3. 🟡 Desactivar FKs + validación post-carga — 25-30% mejora, RIESGO MEDIO
4. 🟢 Logging asincrónico auditoría — 5-10% mejora, sin riesgo
5. 🟡 Índices temporalmente deshhabilitados (MSSQL) — 15-20% mejora, RIESGO BAJO

**Conclusión**: Ganancia de ~40-50% combinando todas las mejoras, priorizando las de bajo riesgo.
```

### Paso 5.2: Checklist de validación post-carga

```markdown
## Checklist de Validación Post-Carga

Antes de poner en producción, verificar:

### Integridad de datos
- [ ] No hay FKs inválidas: `SELECT COUNT(*) FROM table WHERE fk IS NOT NULL AND fk NOT IN (SELECT id FROM parent)`
- [ ] No hay UKs duplicadas: `SELECT col, COUNT(*) FROM table GROUP BY col HAVING COUNT(*) > 1`
- [ ] Checks cumplidos: `SELECT * FROM table WHERE check_condition NOT TRUE`
- [ ] Auditoría completa: `SELECT COUNT(*) FROM audit_log WHERE table_name = 'target_table'`

### Performance
- [ ] Tiempo de carga dentro del target (< 3s para 100K)
- [ ] No hay deadlocks: revisar logs de BD
- [ ] CPU/Memory dentro de límites esperados

### Reversión
- [ ] Backup pre-carga disponible
- [ ] Plan de rollback documentado
- [ ] Constraints re-habilitados correctamente
- [ ] Índices reconstruidos (si aplica)

### Operacional
- [ ] Auditoría registrada (qué se desactivó, cuándo)
- [ ] Notificación a ops + DBA
- [ ] Runbook de rollback accesible
```

### Paso 5.3: Recomendaciones por BBDD

```markdown
## Recomendaciones por Database

### PostgreSQL
✅ **Mejor alternativa**: COPY FROM (60% mejora, seguro)
🟡 **Si debe desactivar**: Usar `DISABLE TRIGGER` + `VALIDATE CONSTRAINT`
⚠️ **Riesgo**: Bajo

### MySQL 8.0
🟡 **Mejor alternativa**: LOAD DATA INFILE + pre-validación (50% mejora)
❌ **NO recomendado**: `foreign_key_checks = 0` (sin re-validación automática)
⚠️ **Riesgo**: Alto

### Oracle
🟡 **Mejor alternativa**: PARALLEL DML + hints (40% mejora, requiere licencia)
🟡 **Si debe desactivar**: `DISABLE CONSTRAINT` + batch manual (25% mejora)
⚠️ **Riesgo**: Medio-Alto

### SQL Server
✅ **Mejor alternativa**: BULK INSERT (50-70% mejora)
🟡 **Si debe desactivar**: Índices deshhabilitados + NOCHECK (25% mejora)
⚠️ **Riesgo**: Bajo-Medio

### SQLite
❌ **NO desactivar**: PRAGMA foreign_keys = OFF (sin recuperación)
✅ **Mejor alternativa**: WAL mode + PRAGMA synchronous (20-30% mejora)
⚠️ **Riesgo**: Crítico si desactivas
```

---

## 📊 Outputs finales

Archivos generados durante la auditoría:

1. **`audit_report_constraints_YYYYMMDD.md`** — Informe ejecutivo con hallazgos
2. **`improvement_roadmap_constraints.md`** — Roadmap fases + quick wins
3. **`validation_checklist_constraints.md`** — Checklist post-carga
4. **`benchmark_comparison_constraints.jsonl`** — Resultados de benchmark (opcional)

---

## 🎯 Timelines y recursos

| Fase | Horas | Esfuerzo | Salidas |
|------|-------|----------|---------|
| PLAN | 1-2 | 1 arq | Inventario, matriz impacto, flujo |
| AUDIT_PLAN | 1-2 | 1 arq + 1 DBA | Viabilidad, riesgos, tests |
| AUDIT_CODE | 2-4 | 1 arq + 1 eng | Hallazgos, recomendaciones |
| IMPROVEMENT_PLAN | 1 | 1 arq | Roadmap, quick wins, métricas |
| VERSION | 1 | 1 arq | Veredicto, checklists, handoff |
| **TOTAL** | **6-10h** | **2 personas** | **5 docs + benchmark (opt)** |

---

*Versión*: 1.0.0
*Rol*: Performance Auditor Agent
*Entrada*: `@Performance Auditor` (lenguaje natural)
*Salida*: 5 documentos estructurados + validación
*BBDD soportadas*: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite
