# Quick Reference: Performance Audit Constraints

**Última actualización**: 2026-09-26  
**Versión**: 1.0.0

---

## 📂 Archivos Creados

| Archivo | Tipo | Para quién | Duración |
|---------|------|-----------|----------|
| `.github/prompts/performance_audit_constraints.prompt.md` (en el repositorio) | Reference (técnico) | Arquitectos, DBAs | 2-4h lectura + análisis |
| `.github/prompts/performance_audit_constraints_agent.prompt.md` (en el repositorio) | Agent (operativo) | Agentes LLM | 6-10h ejecución |
| [`PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md`](PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md) | User Guide | Devs, Architects | 30min lectura |
| `CONSTRAINTS_QUICK_REFERENCE.md` (este) | Quick Ref | Todos | 5min |

---

## 🎯 ¿Cuándo usarlo?

Usa esta auditoría cuando:

- ✅ Cargas masivas (INSERT/UPDATE/DELETE de 10K+ filas) son **lentas**
- ✅ Quieres saber **qué constraints** ralentizan
- ✅ Necesitas **% de mejora estimado** si los desactivas
- ✅ Quieres **alternativas más seguras** (COPY, batch tuning, etc.)
- ✅ Requieres **validación post-carga** robusta

**NO la uses si**:
- ❌ Tus cargas ya son rápidas (< 1s)
- ❌ Cambios de negocio, no de rendimiento
- ❌ No tienes tiempo para auditoría (mínimo 2 horas)

---

## 🚀 Cómo empezar (3 opciones)

### Opción A: Claude Code (Recomendado)
```bash
# En VS Code con Claude Code
/performance-audit-constraints

Tabla: <tu_tabla>
Operación: INSERT|UPDATE|DELETE
Volumen: 100K
Base de datos: PostgreSQL|MySQL|Oracle|SQL Server|SQLite
Baseline (opt): 5.2s
```

**Salida**: 5 documentos automáticos en ~8 horas

---

### Opción B: Chat Manual (Copilot, Gemini, ChatGPT)
1. Copia contenido de `.github/prompts/performance_audit_constraints_agent.prompt.md`
2. Pégalo en tu chat con tus inputs
3. Espera 6-10 horas de análisis

**Salida**: Respuestas de chat estructuradas en 5 fases

---

### Opción C: Análisis Manual (Sin LLM)
1. Lee `.github/prompts/performance_audit_constraints.prompt.md` (técnico)
2. Crea tu tabla de constraints (DDL)
3. Estima impacto usando las referencias de internet
4. Diseña tests tú mismo

**Salida**: Tu análisis custom, ~4-8 horas

---

## 📊 Qué esperar: Salidas típicas

### Hallazgo típico

```markdown
### Hallazgo: Foreign Key ralentiza INSERT 30%

Tabla: orders
Constraint: fk_customer_id REFERENCES customers(id)

Impacto: 30% ralentización en INSERT (validación por fila)

Opciones:
A) Desactivar FK → 30% ganancia, RIESGO ALTO (validar post-carga)
B) Usar COPY → 40-60% ganancia, RIESGO NULO (PostgreSQL)
C) Pre-fetch IDs → 10% ganancia, RIESGO NULO (cualquier BBDD)

Recomendación: Opción B (COPY), luego consideraré Opción C.
```

### Matriz de impacto

| Constraint | BBDD | Tipo | Overhead | Desactivable | Alternativa | Impacto total |
|-----------|------|------|----------|--------------|-------------|---------------|
| fk_customer_id | PostgreSQL | FK | 30% | ⚠️ Sí + validar | COPY | 40-60% ↑ |
| uk_email | PostgreSQL | UK | 15% | ✅ Sí | Índice desactivo | 15% ↑ |
| check_amount | PostgreSQL | CHECK | 2% | ✅ Sí | Validación previa | 2% ↑ |

**Total ganancia estimada**: 50-60% si implementas todo

---

## 💡 Quick Wins (Baja Riesgo, 5-10% Mejora)

Implementa primero sin esperar auditoría completa:

```sql
-- 1. Aumentar batch size
SET batch_size = 5000;  -- de 1000

-- 2. Usar prepared statements
-- (evita compilación SQL repetida)

-- 3. Deshabilitar logging sincrónico
SET audit_mode = 'async';  -- auditoría asincrónica

-- 4. Desactivar CHECK constraints (bajo riesgo)
ALTER TABLE orders DISABLE CONSTRAINT check_amount;
-- ... INSERT ...
ALTER TABLE orders ENABLE CONSTRAINT check_amount;

-- Ganancia total Fase 1: ~8-10%
```

**Tiempo**: < 1 hora  
**Riesgo**: Nulo  
**Mejora**: 8-10%

---

## 🟡 Medium Optimizations (Riesgo Medio, 15-25% Mejora)

Después de validar Fase 1:

```sql
-- PostgreSQL: Usar COPY (mejor impacto)
COPY orders FROM STDIN WITH (FORMAT CSV, DELIMITER ',');
-- Ganancia: 40-60%

-- SQL Server: Deshabilitar índices temporalmente
ALTER INDEX ALL ON orders DISABLE;
BULK INSERT orders FROM 'file.csv';
ALTER INDEX ALL ON orders REBUILD;
-- Ganancia: 25-35%

-- MySQL: LOAD DATA INFILE + pre-validación
LOAD DATA INFILE 'file.csv' INTO TABLE orders;
SELECT COUNT(*) FROM orders WHERE customer_id NOT IN (SELECT id FROM customers);
-- Ganancia: 30-40%
```

**Tiempo**: 1-3 días  
**Riesgo**: Medio (requiere validación post-carga)  
**Mejora**: 15-25% (o 40-60% con COPY)

---

## 🔴 Advanced: Desactivar Constraints (Riesgo Alto, 30-50% Mejora)

Solo si impacto > 20% y validación post-carga robusta:

```sql
-- ANTES: Backup + registrar qué desactivas
BEGIN TRANSACTION;
SAVEPOINT pre_constraint_disable;

-- Desactivar por BBDD
-- PostgreSQL
ALTER TABLE orders DISABLE TRIGGER ALL;

-- MySQL
SET foreign_key_checks = 0;

-- Oracle
ALTER TABLE orders DISABLE CONSTRAINT fk_customer_id;

-- SQL Server
ALTER TABLE orders NOCHECK CONSTRAINT fk_customer_id;

-- DURANTE: Carga masiva
INSERT INTO orders (...) VALUES (...);

-- DESPUÉS: Validar integridad
SELECT COUNT(*) FROM orders WHERE customer_id NOT IN (SELECT id FROM customers);
-- Debe retornar 0

-- Re-habilitar
-- PostgreSQL
ALTER TABLE orders ENABLE TRIGGER ALL;
ALTER TABLE orders VALIDATE CONSTRAINT fk_customer_id;

-- Confirmar
COMMIT;
```

**Checklist**:
- [ ] Backup pre-desactivación
- [ ] Transacción explícita (BEGIN/COMMIT)
- [ ] Validación post-carga (SELECT verificación)
- [ ] Re-habilitación sin errores
- [ ] Rollback plan documentado
- [ ] Ops + DBA notificados

**Tiempo**: 1-2 semanas (testing intensivo)  
**Riesgo**: Alto (corrupción de datos si falla)  
**Mejora**: 30-50%

---

## ⚠️ Riesgos Comunes

| Riesgo | Síntoma | Solución |
|--------|---------|----------|
| FK inválidas después de carga | Re-activación falla | Validar FK pre-carga, ROLLBACK si hay inválidas |
| UK duplicadas no detectadas | Datos corrompidos | Validar UKs post-carga con GROUP BY |
| Índices inconsistentes (MSSQL) | Queries lentas | REBUILD obligatorio después |
| Auditoría se pierde | Datos sin log | NO desactives triggers de auditoría |
| Transacción bloqueada | Table lock infinito | Timeout + rollback automático |

---

## 📚 Referencias por BBDD

### PostgreSQL
```sql
-- Desactivar triggers (safer)
ALTER TABLE table_name DISABLE TRIGGER ALL;
ALTER TABLE table_name ENABLE TRIGGER ALL;
ALTER TABLE table_name VALIDATE CONSTRAINT constraint_name;

-- Mejor: usar COPY
COPY table_name FROM STDIN WITH (FORMAT CSV);
```
**Riesgo**: BAJO  
**Impacto**: 40-60% (COPY), 25-30% (DISABLE TRIGGER)  
**Referencia**: [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)

---

### MySQL / MariaDB
```sql
-- Deshabilitar checks FK
SET foreign_key_checks = 0;
INSERT INTO table_name ...;
SET foreign_key_checks = 1;

-- Re-validar manualmente
CHECK TABLE table_name;
```
**Riesgo**: MEDIO (sin re-validación automática)  
**Impacto**: 20-30%  
**Referencia**: [MySQL foreign_key_checks](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html)

---

### Oracle
```sql
-- Desactivar constraint
ALTER TABLE table_name DISABLE CONSTRAINT constraint_name;
INSERT INTO table_name ...;
-- Re-habilitar (puede fallar si hay violaciones)
ALTER TABLE table_name ENABLE CONSTRAINT constraint_name;
-- O sin validar (menos seguro)
ALTER TABLE table_name ENABLE CONSTRAINT constraint_name NOVALIDATE;
```
**Riesgo**: ALTO (puede fallar re-validación)  
**Impacto**: 20-30%  
**Referencia**: [Oracle DISABLE CONSTRAINT](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/ALTER-TABLE.html)

---

### SQL Server
```sql
-- Desactivar constraint
ALTER TABLE table_name NOCHECK CONSTRAINT constraint_name;
ALTER TABLE table_name NOCHECK CONSTRAINT ALL;

-- Re-habilitar y validar
ALTER TABLE table_name WITH CHECK CHECK CONSTRAINT constraint_name;
-- Opcionalmente, solo habilitar sin validar
-- ALTER TABLE table_name WITH NOCHECK CHECK CONSTRAINT constraint_name;
```
**Riesgo**: MEDIO (validación puede ser lenta)  
**Impacto**: 25-35% (o 40-50% + REBUILD INDEX)  
**Referencia**: [SQL Server NOCHECK CONSTRAINT](https://docs.microsoft.com/en-us/sql/t-sql/statements/alter-table-transact-sql)

---

### SQLite
```sql
-- Desactivar checks (POR SESIÓN SOLAMENTE)
PRAGMA foreign_keys = OFF;
INSERT INTO table_name ...;
PRAGMA foreign_keys = ON;

-- ⚠️ NO hay mecanismo de re-validación automática
-- Alto riesgo de corrupción
```
**Riesgo**: CRÍTICO (sin recuperación)  
**Impacto**: 30-40%  
**Referencia**: [SQLite PRAGMA foreign_keys](https://www.sqlite.org/pragma.html#pragma_foreign_keys)  
**Recomendación**: NO desactives en SQLite; usa WAL mode en su lugar (20-30% mejora)

---

## 🧪 Benchmark: Validar mejoras

```bash
# Si tienes script de benchmark disponible:
python scripts/bench_bulk.py run \
  --table orders \
  --scenarios baseline,no_fk,no_uk,no_constraints,copy,parallel \
  --volume 100k,1m \
  --out results/

python scripts/bench_bulk.py summarize results/results.jsonl
```

**Resultado típico**:
```
Baseline (sin optimizaciones): 5.2s (100%)
Fase 1 (quick wins): 4.8s (92%)
Fase 2 (medium): 3.8s (73%)
Fase 3 (desactiv.): 2.1s (40%)
COPY (recomendado): 2.4s (46%)
```

---

## 📞 Pedir Auditoría Completa

### Claude Code
```
/performance-audit-constraints
Tabla: orders
Operación: INSERT
Volumen: 250K
BBDD: PostgreSQL
Baseline: 5.2s
```

### Chat Manual
Copia `.github/prompts/performance_audit_constraints_agent.prompt.md` + tus inputs.

### Documentación
Lee [`docs/PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md`](./PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md) completa.

---

## 🎓 Aprende Más

| Recurso | Tipo | Tiempo |
|---------|------|--------|
| `docs/PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md` | User Guide | 30min |
| `.github/prompts/performance_audit_constraints.prompt.md` | Reference | 2-4h |
| `.github/prompts/performance_audit_constraints_agent.prompt.md` | Workflow | 6-10h (ejecución) |
| Tus propios tests | Benchmark | var |

---

*Resumen ejecutivo: Desactivar constraints puede mejorar 25-50%, pero requiere validación robusta. Empieza con quick wins (5-10% sin riesgo), luego evalúa medium optimizations (COPY, batch tuning). Desactiva constraints solo si impacto > 20% y puedas validar integridad post-carga.*
