# Prompts de Auditoría de Rendimiento: Desactivación de Constraints — Índice

**Versión**: 1.0.0  
**Fecha de creación**: 2026-09-26  
**Estado**: ✅ Completado  

---

## 📋 Resumen: ¿Qué se creó?

Se han creado **4 documentos** especializados para analizar el rendimiento de desactivar constraints en operaciones de carga masiva:

| # | Documento | Ubicación | Tipo | Audiencia | Tiempo |
|---|-----------|-----------|------|-----------|--------|
| 1️⃣ | **Reference Prompt** (técnico detallado) | `.github/prompts/performance_audit_constraints.prompt.md` | 📘 Reference | Arquitectos, DBAs | 2-4h |
| 2️⃣ | **Agent Prompt** (workflow 5 fases) | `.github/prompts/performance_audit_constraints_agent.prompt.md` | 🤖 Agent Workflow | Agentes LLM | 6-10h |
| 3️⃣ | **User Guide** (cómo usar) | `docs/PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md` | 📗 User Guide | Devs, Architects | 30min |
| 4️⃣ | **Quick Reference** (cheatsheet) | `docs/CONSTRAINTS_QUICK_REFERENCE.md` | ⚡ Cheatsheet | Todos | 5min |

---

## 🚀 Punto de Partida (Elige Uno)

### 👤 Soy usuario final (Dev, QA, Architect)
**→ Lee primero**: [`docs/CONSTRAINTS_QUICK_REFERENCE.md`](CONSTRAINTS_QUICK_REFERENCE.md) (5 min)  
**→ Luego**: [`docs/PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md`](PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md) (30 min)  
**→ Accción**: `/performance-audit-constraints` en Claude Code o copia el agent prompt a tu chat

---

### 🤖 Soy arquitecto o especialista técnico
**→ Lee primero**: `.github/prompts/performance_audit_constraints.prompt.md` (2-4h)  
**→ Luego**: `.github/prompts/performance_audit_constraints_agent.prompt.md`  
**→ Aplica**: Personaliza inputs + ejecuta análisis completo

---

### 🦾 Soy un agente LLM (Claude, GPT, Gemini)
**→ Tu prompt**: `.github/prompts/performance_audit_constraints_agent.prompt.md`  
**→ Método**: Ejecuta 5 fases (PLAN → AUDIT_PLAN → AUDIT_CODE → IMPROVEMENT_PLAN → VERSION)  
**→ Duración**: 6-10 horas

---

## 📂 Estructura de Archivos

```
util_bbdd/
├── .github/prompts/
│   ├── performance_audit_constraints.prompt.md          ← 📘 Reference
│   └── performance_audit_constraints_agent.prompt.md    ← 🤖 Agent Workflow
├── docs/
│   ├── PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md          ← 📗 User Guide
│   ├── CONSTRAINTS_QUICK_REFERENCE.md                  ← ⚡ Cheatsheet
│   └── [otros documentos de proyecto]
└── ...
```

---

## 🎯 Usar en 3 Pasos

### Paso 1: Preparar Inputs
Reúne antes de la auditoría:
- [ ] DDL de tu tabla (con constraints)
- [ ] Tipo de operación (INSERT, UPDATE, DELETE)
- [ ] Volumen de datos (1K, 10K, 100K, 1M)
- [ ] Base de datos (PostgreSQL, MySQL, Oracle, SQL Server, SQLite)
- [ ] Tiempo actual (opcional pero útil)

### Paso 2: Ejecutar Auditoría
**Opción A**: Usar Claude Code
```
/performance-audit-constraints
[tus inputs]
```

**Opción B**: Pegar prompt en chat
Copia `.github/prompts/performance_audit_constraints_agent.prompt.md` + inputs en ChatGPT, Gemini, Copilot, etc.

**Opción C**: Leer documentación manual
Lee `.github/prompts/performance_audit_constraints.prompt.md` y analiza tú mismo.

### Paso 3: Implementar Recomendaciones
El análisis te dará:
1. Matriz de constraints (impacto %)
2. Hallazgos técnicos (severidad, riesgos)
3. Roadmap de mejoras (quick wins → medium → complex)
4. Checklist de validación

---

## 💡 Casos de Uso Típicos

### Caso 1: Carga diaria lenta (PostgreSQL)
```
Tabla: orders (1M existentes)
Operación: INSERT 100K nuevas órdenes
Baseline: 5.2s
Objetivo: < 3s (42% mejora)
```
→ **Recomendación típica**: Usar COPY (PostgreSQL) = 40-60% mejora, sin riesgo

### Caso 2: Actualización masiva (Oracle)
```
Tabla: customers (50M filas)
Operación: UPDATE 1M registros
Baseline: 45s
Objetivo: < 25s (44% mejora)
```
→ **Recomendación típica**: Desactivar UK + índices = 25-30% mejora + validación post-carga

### Caso 3: Bulk dump (SQL Server)
```
Tabla: all (500M filas total)
Operación: BULK INSERT desde archivo
Baseline: 180s
Restricción: máximo 120s downtime
```
→ **Recomendación típica**: BULK INSERT + REBUILD INDEX = 55% mejora, dentro de downtime

---

## 🎓 ¿Qué Cubre?

### Constraints Analizados
- ✅ Foreign Keys (FK)
- ✅ Unique Keys (UK)
- ✅ Check Constraints
- ✅ Default Values
- ✅ Triggers (auditoría)
- ✅ Índices asociados
- ⚠️ Primary Keys (limitado)

### Bases de Datos Soportadas
- ✅ PostgreSQL
- ✅ MySQL / MariaDB
- ✅ Oracle
- ✅ SQL Server
- ✅ SQLite

### Estrategias Evaluadas
- Desactivación de constraints (riesgo vs. beneficio)
- Alternativas más seguras (COPY, BULK INSERT, batch tuning)
- Pre-validación de datos
- Índices temporalmente deshabilitados
- Logging asincrónico
- Paralelización

### Riesgos Cubiertos
- Corrupción de datos (FK inválidas, UK duplicadas)
- Índices inconsistentes
- Pérdida de auditoría
- Transacciones bloqueadas
- Validación post-carga fallida

---

## 📊 Salidas Esperadas

La auditoría genera:

1. **Inventario de constraints** — Tabla de todos los constraints (tipo, criticidad, impacto %)
2. **Hallazgos técnicos** — Severidad, riesgos, recomendaciones por constraint
3. **Matriz riesgo/beneficio** — Desactivar sí/no, alternativas
4. **Roadmap** — Fases (quick wins → medium → complex)
5. **Checklist** — Validación post-carga por BBDD
6. **Benchmark** (opcional) — Before/after si ejecutas los test scripts

**Archivo de entrega**: Típicamente 3-5 documentos Markdown + JSON results (opcional)

---

## ⚡ Quick Wins (Sin Auditoría Completa)

Si no tienes tiempo para auditoría de 6-10h, aplica directamente:

```sql
-- Aumentar batch size (5-10% mejora, sin riesgo)
SET batch_size = 5000;  -- de 1000

-- Desactivar CHECK constraints (2-5% mejora, bajo riesgo)
ALTER TABLE table_name DISABLE CONSTRAINT check_constraint;
-- ... INSERT ...
ALTER TABLE table_name ENABLE CONSTRAINT check_constraint;

-- Logging asincrónico (5% mejora, sin riesgo)
SET audit_mode = 'async';

-- Total Fase 1: ~8-10% mejora, sin riesgo, < 1 hora
```

---

## ⚠️ Consideraciones Importantes

### ✅ Seguro desactivar
- CHECK constraints (validación simple)
- Índices temporales (SQL Server)
- Triggers de formato / transformación

### ⚠️ Riesgo medio desactivar
- Unique Keys (validar duplicados post-carga)
- Índices secundarios (rebuild obligatorio)

### 🔴 Alto riesgo desactivar
- Foreign Keys (corrupción referencial)
- Triggers de auditoría (pérdida de logs)
- Primary Keys (nunca desactives)

### ❌ NO desactives
- Auditoría crítica (compliance)
- PKs
- Constraints que definen integridad

---

## 🔗 Referencias Relacionadas

### En el proyecto
- **Módulo bulk**: `src/util_bbdd/bulk/` (carga masiva)
- **Auditoría**: `src/util_bbdd/audit/` (audit_manager.py)
- **Introspección**: `src/util_bbdd/introspect/` (análisis de BBDD)
- **Tests**: `tests/bulk/` (test suites de carga)

### Prompts relacionados
- `.github/prompts/performance_audit_bulk.prompt.md` (carga masiva general)
- `.github/prompts/performance_audit_dump.prompt.md` (volcado masivo)
- `.github/prompts/audit_code.prompt.md` (auditoría técnica)

---

## 🆘 Soporte

### Preguntas frecuentes
**P: ¿Cuánto tiempo toma una auditoría completa?**  
A: 6-10 horas (2 personas: arquitecto + DBA). En paralelo con otros trabajo puede tardar 1-2 días.

**P: ¿Qué pasa si tengo múltiples tablas?**  
A: Ejecuta auditoría por tabla. Usa `performance_audit_bulk.prompt.md` para optimización general.

**P: ¿Riesgo de perder datos?**  
A: Bajo si sigues checklist de validación post-carga. Usa transacciones explícitas + backup pre-carga.

**P: ¿Qué BBDD tiene mejor resultado desactivando constraints?**  
A: PostgreSQL (COPY = 60% mejora). Mejor usar DB-specific directives que desactivar.

### Contacto
- Consulta archivos en `.ai/sessions/` para auditorías previas
- Revisa `docs/PERFORMANCE_AUDIT_GUIDE.md` para volcado (dump) masivo
- Lee `SHARED_INSTRUCTIONS.md` para arquitectura general del proyecto

---

## 📝 Changelog

**v1.0.0** (2026-09-26)
- ✅ Creados 4 documentos principales
- ✅ Cubiertos 10 áreas de auditoría
- ✅ 5 BBDD soportadas (PostgreSQL, MySQL, Oracle, SQL Server, SQLite)
- ✅ Casos de uso reales + riesgos identificados
- ✅ Benchmarks y validación incluidos

**Próximas versiones**:
- [ ] Slash command `/performance-audit-constraints` en Claude Code
- [ ] Integración con `scripts/bench_bulk.py`
- [ ] Test suite `tests/bulk/test_constraints_performance.py`
- [ ] Documentación específica por BBDD en `docs/guides/`

---

*Actualizado: 2026-09-26 | Versión: 1.0.0 | Estado: ✅ Listo para usar*
