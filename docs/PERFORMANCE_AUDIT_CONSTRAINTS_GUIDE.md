# Guía: Auditoría de Rendimiento — Desactivación de Constraints

**Versión**: 1.0.0  
**Propósito**: Entender y usar los prompts de auditoría de constraints para optimizar cargas masivas  
**Audiencia**: Database Architects, Performance Engineers, Backend Developers  

---

## 🎯 ¿Para qué sirve esta auditoría?

Cuando cargas datos en volumen (INSERT/UPDATE/DELETE masivo en mil o más filas), **los constraints ralentizan** la operación:

- **Foreign Keys (FK)**: Validan referencia en tabla padre (+ búsqueda en BD)
- **Unique Keys (UK)**: Comprueban duplicados en índice único
- **Check Constraints**: Validan predicados (lógica de negocio)
- **Triggers**: Ejecutan auditoría u otras acciones

**Pregunta clave**: ¿Desactivar constraints durante la carga = ganancia de velocidad sin riesgo de corrupción?

**Respuesta**: ✅ Sí, pero **con cuidado**. Esta auditoría te ayuda a:

1. Identificar qué constraints ralentizan tu carga
2. Medir el impacto real (% de mejora)
3. Evaluar el riesgo de integridad si los desactivas
4. Proponer alternativas más seguras (COPY, pre-validación, batch tuning)
5. Generar un plan de implementación priorizando low-risk wins

---

## 🚀 Cómo usar esta auditoría

### Opción A: Usando Claude Code (recomendado)

Si trabajas con Claude Code en VS Code, usa slash command:

```
/performance-audit-constraints

Tabla: customers
Operación: INSERT
Volumen: 100K registros
Base de datos: PostgreSQL
Baseline (opcional): 5.2s
```

El agente ejecutará las 5 fases automáticamente y generará:
- 📄 Informe ejecutivo (hallazgos)
- 🛣️ Roadmap de mejoras
- ✅ Checklist de validación

### Opción B: Prompt manual (CLI/chat)

Si no tienes acceso a Claude Code:

1. Lee `.github/prompts/performance_audit_constraints.prompt.md` (referencia técnica)
2. Lee `.github/prompts/performance_audit_constraints_agent.prompt.md` (workflow en fases)
3. Invoca un LLM con el prompt seleccionado + tus inputs

Ejemplo:
```bash
# Copia el contenido del prompt de agente
cat .github/prompts/performance_audit_constraints_agent.prompt.md

# Abre tu chat preferido (ChatGPT, Copilot, Gemini, Claude) y pega:
# [contenido del prompt] + [tus inputs de tabla, volumen, BBDD]
```

---

## 📋 Preparar inputs antes de la auditoría

Para que la auditoría sea rápida y útil, prepara:

### Input 1: Tabla objetivo
```sql
-- Exporta la DDL de tu tabla
-- PostgreSQL:
\d+ tablename

-- MySQL:
SHOW CREATE TABLE tablename;

-- Oracle:
DBMS_METADATA.GET_DDL('TABLE', 'tablename');

-- SQL Server:
sp_helpconstraint 'tablename';
```

Ejemplo DDL:
```sql
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INT REFERENCES customers(id),  -- FK
  email VARCHAR(255) UNIQUE NOT NULL,        -- UK
  amount DECIMAL(10,2) CHECK (amount > 0),   -- CHECK
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Input 2: Operación y volumen
- **Operación**: `INSERT` / `UPDATE` / `DELETE`
- **Volumen**: Número de filas
  - Pequeño: 1K–10K
  - Medio: 10K–100K
  - Grande: 100K–1M
  - Masivo: > 1M

Ejemplo:
```
Operación: INSERT
Volumen: 250K nuevas órdenes
Frecuencia: Diaria a las 02:00 UTC
```

### Input 3: Base de datos
Especifica:
- Motor: PostgreSQL, MySQL, Oracle, SQL Server, SQLite
- Versión (si la conoces)
- Modo de transacción (autocommit vs. explicit transaction)

Ejemplo:
```
Base de datos: PostgreSQL 15.2
Transacción: Explicit (BEGIN...COMMIT)
```

### Input 4: Baseline (opcional pero útil)
Si ya tienes medición actual:
```
Tiempo actual (con constraints): 5.2 segundos
Límite aceptable: < 3 segundos
Ganancia esperada: >= 40%
```

### Input 5: Restricciones de negocio
```
Restricciones:
- Auditoría DEBE ejecutarse (no desactivable)
- Máximo downtime de tabla: 30 minutos
- No permitido perder datos
- Backup disponible: SÍ
```

---

## 🔍 Qué esperar: Salidas de la auditoría

### Salida 1: Inventario de constraints

Tabla con todos los constraints encontrados:

| Constraint | Tipo | Tabla | Criticidad | Impacto teórico |
|-----------|------|-------|------------|-----------------|
| fk_customer_id | FK | orders | CRÍTICA | 30% |
| uk_email | UK | customers | CRÍTICA | 15% |
| check_amount | CHECK | orders | MEDIA | 2% |
| default_created_at | DEFAULT | orders | BAJA | < 1% |

**Interpretación**:
- **Criticidad CRÍTICA**: Desactivable solo con validación post-carga
- **Criticidad MEDIA/BAJA**: Más seguro desactivar
- **Impacto teórico**: % aproximado de ralentización causado

### Salida 2: Hallazgos de rendimiento

Ejemplo hallazgo:

```markdown
### Hallazgo H1: Foreign Key validation ralentiza INSERT 30%

**Severidad**: ALTA
**Impacto**: 30% ralentización
**Causa**: Cada INSERT valida FK → búsqueda en tabla customers

**Opciones**:

A) Desactivar FK (riesgo ALTO)
   - Ganancia: 30% más rápido
   - Riesgo: Datos FK inválidos si hay error
   - Validación post-carga: OBLIGATORIA
   - Comando: ALTER TABLE orders DISABLE CONSTRAINT fk_customer_id

B) Usar COPY (recomendado, riesgo BAJO)
   - Ganancia: 40-60% más rápido
   - Riesgo: NULO (constraints activos)
   - Validación: Automática
   - Comando: COPY orders FROM stdin

C) Pre-fetch de IDs (alternativa, riesgo NULO)
   - Ganancia: 10-15% más rápido
   - Riesgo: NULO
   - Validación: Local en app
```

### Salida 3: Roadmap priorizado

Fases de implementación ordenadas por riesgo y beneficio:

```
🟢 QUICK WINS (Fase 1, < 1 día, bajo riesgo)
  ✅ Batch size 1000 → 5000: +8% ganancia
  ✅ Logging async: +5% ganancia
  ✅ Desactivar CHECK constraints: +2% ganancia

🟡 MEJORAS MEDIUM (Fase 2, 1-3 días, riesgo medio)
  ⚠️ Usar COPY (PostgreSQL): +40% ganancia, validación requerida
  ⚠️ Índices deshabilitados (MSSQL): +20% ganancia, rebuild obligatorio

🔴 MEJORAS COMPLEJAS (Fase 3, 1-2 semanas, riesgo alto)
  🔴 Desactivar FKs + validación: +30% ganancia, corrupción risk
  🔴 Paralelización: +35% ganancia, testing intensivo
```

**Recomendación**: Implementar Fase 1 (sin riesgo), evaluar antes de pasar a Fase 2-3.

### Salida 4: Checklist de validación post-carga

Pasos a verificar después de cada carga:

```markdown
## Checklist de Validación

**Antes de activar constraints:**
- [ ] No hay FKs inválidas
- [ ] No hay UKs duplicadas
- [ ] Checks cumplidos
- [ ] Auditoría completa

**Después de activar:**
- [ ] Constraints re-habilitados sin error
- [ ] Índices reconstruidos (si aplica)
- [ ] Tiempo de validación aceptable (< 1min)

**Antes de poner en producción:**
- [ ] Backup disponible
- [ ] Rollback plan documentado
- [ ] Ops/DBA notificados
```

---

## 💡 Casos de uso típicos

### Caso 1: Carga diaria de 100K órdenes (PostgreSQL)

**Input**:
```
Tabla: orders (1M filas existentes)
Operación: INSERT 100K nuevas órdenes
Volumen: 100K
BBDD: PostgreSQL
Baseline: 5.2s con constraints
Objetivo: < 3s
```

**Hallazgo típico**:
- FK (customer_id): 30% overhead → Desactivable
- UK (order_number): 15% overhead → Desactivable
- Auditoría: 18% overhead → NO desactivable

**Recomendación**:
```
Fase 1 (Quick win, 8% ganancia):
  ALTER TABLE orders DISABLE TRIGGER audit_trigger;
  INSERT (batch 5000);
  ENABLE TRIGGER;

Fase 2 (Medium, 40% ganancia):
  COPY orders FROM stdin (formarto CSV);
  Validar FK/UK post-carga;
  ENABLE TRIGGER audit;

Mejora esperada: 5.2s → 2.1s (60% ganancia)
```

### Caso 2: Actualización masiva de 1M registros (Oracle)

**Input**:
```
Tabla: customers (50M filas existentes)
Operación: UPDATE 1M registros (cambio de dirección)
Volumen: 1M
BBDD: Oracle
Baseline: 45s con constraints
Objetivo: < 25s
```

**Hallazgo típico**:
- UK (email): 25% overhead → Desactivable (con cuidado)
- FK (country_id): 20% overhead → Validar pre-carga
- Índices: 15% overhead → Desactivables temporalmente

**Recomendación**:
```
Fase 1 (Quick win, 10% ganancia):
  PRAGMA parallel DML (Oracle hint);
  UPDATE batch_size 5000;
  
Fase 2 (Medium, 25% ganancia):
  ALTER TABLE customers DISABLE CONSTRAINT uk_email NOVALIDATE;
  UPDATE 1M registros;
  ALTER TABLE customers ENABLE CONSTRAINT uk_email;
  Validar: SELECT email, COUNT(*) FROM customers GROUP BY email HAVING COUNT(*) > 1;

Mejora esperada: 45s → 25s (44% ganancia)
```

### Caso 3: Dump completo de BD (SQL Server)

**Input**:
```
Tabla: all tables (~50 tablas, 500M filas total)
Operación: BULK INSERT desde archivo
Volumen: 500M
BBDD: SQL Server
Baseline: 180s con constraints
Restricción: Máximo 120s downtime
```

**Recomendación**:
```
Paso 1: Desactivar índices (MSSQL trick)
  ALTER INDEX ALL ON tablename DISABLE;

Paso 2: BULK INSERT sin validación
  BULK INSERT tablename FROM 'file.csv' WITH (CHECK_CONSTRAINTS = OFF);

Paso 3: Reconstruir índices + validar constraints
  ALTER INDEX ALL ON tablename REBUILD;
  ALTER TABLE tablename WITH CHECK CHECK CONSTRAINT ALL;

Mejora esperada: 180s → 80s (55% ganancia, dentro de downtime)
```

---

## ⚠️ Riesgos comunes y cómo evitarlos

### Riesgo 1: Datos FK inválidos quedan en BD

**Problema**: Desactivaste FK, cargaste datos, luego re-activaste y falla.

**Solución**:
```sql
-- ANTES de desactivar FK
SELECT COUNT(*) FROM customer_ids_to_load;  -- Guardar count

-- DESPUÉS de INSERT
SELECT COUNT(*) FROM orders WHERE customer_id NOT IN (
  SELECT id FROM customers
);  -- Debe ser 0

-- Si hay inválidas, hacer ROLLBACK antes de re-activar FK
```

### Riesgo 2: UK duplicadas pasan desapercibidas

**Problema**: Desactivaste UK, cargas duplicados, datos quedan corrupt.

**Solución**:
```sql
-- Validar UKs después de carga
SELECT email, COUNT(*) FROM customers 
GROUP BY email HAVING COUNT(*) > 1;  -- Debe ser empty

-- Si hay duplicados, DELETE antes de re-activar
DELETE FROM customers WHERE id IN (SELECT MAX(id) FROM customers GROUP BY email HAVING COUNT(*) > 1);
```

### Riesgo 3: Índices quedan inconsistentes (MSSQL)

**Problema**: Deshabilitaste índices, recarga falla, índices no se reconstruyen.

**Solución**:
```sql
-- SIEMPRE reconstruir después
ALTER INDEX ALL ON tablename REBUILD;
-- Verificar
DBCC CHECKDB (database_name);  -- Debe pasar sin errores
```

### Riesgo 4: Auditoría se pierde

**Problema**: Desactivaste triggers de auditoría, datos se cargan sin log.

**Solución**:
```python
# NO desactives auditoría para operaciones críticas
# En su lugar:
# 1. Usa logging asincrónico (no ralentiza)
# 2. O usa INSERT con auditoría integrada (validación post)
# 3. O registra carga en tabla audit_metadata
INSERT INTO audit_metadata (table_name, rows_loaded, timestamp)
VALUES ('orders', 100000, NOW());
```

---

## 🧪 Benchmark: Medir impacto real

Después de la auditoría, valida con benchmark:

```bash
# Crear tabla de test con constraints
python -m pytest tests/bulk/test_constraints_performance.py -v

# Correr benchmark (requiere script disponible)
python scripts/bench_bulk.py run \
  --table orders \
  --scenarios baseline,no_fk,no_uk,no_constraints,all \
  --volume 100k,1m \
  --out .ai/sessions/constraint_analysis

# Ver resultados
python scripts/bench_bulk.py summarize \
  .ai/sessions/constraint_analysis/results.jsonl
```

**Resultado esperado**:
```
Baseline (todos activos): 5.2s
Sin FK: 3.6s (30% ganancia)
Sin UK: 4.4s (15% ganancia)
Sin ninguno: 2.5s (52% ganancia)
```

---

## 📞 Contacto y recursos

Si necesitas más ayuda:

1. **Referencia técnica**: Lee `.github/prompts/performance_audit_constraints.prompt.md`
2. **Workflow**: Lee `.github/prompts/performance_audit_constraints_agent.prompt.md`
3. **Ejemplos de código**: Ver `tests/bulk/` y `src/util_bbdd/bulk/`
4. **Documentación de BBDD**:
   - [PostgreSQL: DISABLE TRIGGER](https://www.postgresql.org/docs/current/sql-altertable.html)
   - [MySQL: foreign_key_checks](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_foreign_key_checks)
   - [Oracle: DISABLE CONSTRAINT](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/ALTER-TABLE.html)
   - [SQL Server: CHECK CONSTRAINT](https://docs.microsoft.com/en-us/sql/t-sql/statements/alter-table-transact-sql)

---

*Actualizado: 2026-09-26*  
*Versión*: 1.0.0  
*Para preguntas*: Consulta `.ai/sessions/` de auditorías previas
