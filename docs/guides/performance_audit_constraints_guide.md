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

!!! note "Cifras de los ejemplos"
    Los porcentajes y tiempos de esta guía (30 % por FK, 5,2 s → 2,1 s…) ilustran el formato de la salida; no son
    mediciones de `util_bbdd`. Las mediciones reales están en [Benchmarks](benchmarks.md) y en las sesiones de
    auditoría de `.ai/sessions/`.

## 🧰 Qué hace ya util_bbdd

Antes de auditar, conviene saber qué desactiva la librería por su cuenta:

| Punto de entrada | Qué desactiva y cómo lo restaura | Referencia |
|---|---|---|
| `BulkCrud.maintenance_scope(tabla, disable_constraints=True, disable_indexes=False, require_optimization=False)` | MariaDB/MySQL: `FOREIGN_KEY_CHECKS=0` (tampoco se ejecutan los `ON DELETE/UPDATE CASCADE`). PostgreSQL: `DISABLE TRIGGER ALL` si el usuario es propietario o superusuario, con comprobación de filas huérfanas de cada FK al restaurar. SQL Server: `NOCHECK CONSTRAINT ALL`. Oracle: `DISABLE`/`ENABLE VALIDATE CONSTRAINT` de cada FK, CHECK con nombre y UNIQUE. Con `disable_indexes` (v3.2.0, estrategia común con `dump`): índices secundarios no únicos, SQL Server `DISABLE`→`REBUILD`, Oracle `UNUSABLE`→`REBUILD`, PostgreSQL `DROP`→recreación, MyISAM/Aria `DISABLE KEYS`, InnoDB `DROP`→`ADD` solo con `commit_every_n_chunks`; nunca PK/UNIQUE ni el clustered. Requiere `bulk_session()` | [BulkCrud](../api/bulk_crud.md) |
| `ParallelBulkLoader(parallel=ParallelOptions(disable_constraints=True))` | Solo en el INSERT. En SQL Server, PostgreSQL y Oracle desactiva una vez antes de lanzar los hilos; en el resto, cada worker usa `maintenance_scope`. Los índices, con `disable_indexes` (v3.2.0): una vez antes de lanzar los hilos; compensa en SQL Server y Oracle (y poco en MySQL), no en PostgreSQL ni MariaDB | [Carga paralela](../api/bulk_parallel.md) |
| `DumpOrchestrator` | Desactiva las constraints del destino durante la carga y las rehabilita al final (`DumpResult.constraint_results`); `DumpConfig.manage_indexes=True` gestiona además los índices | [Volcado](../api/dump.md) |

La auditoría sirve para decidir si esas palancas compensan en tu caso y qué validar después.

## ⚡ Referencia rápida por motor

Qué se puede desactivar, cómo se reactiva y si la reactivación comprueba los datos cargados. La columna «util_bbdd»
es lo que hace `maintenance_scope` (código en `src/util_bbdd/bulk/_execution/maintenance.py`).

| Motor | Desactivar | Reactivar | ¿Revalida al reactivar? | util_bbdd |
|---|---|---|---|---|
| PostgreSQL | `ALTER TABLE t DISABLE TRIGGER ALL` (propietario o superusuario; apaga las FK **y todos los triggers**, también los de usuario) | `ALTER TABLE t ENABLE TRIGGER ALL` | **No**: la FK sigue marcada como válida aunque haya filas huérfanas, y `VALIDATE CONSTRAINT` no hace nada sobre una FK válida | Lo usa si hay permisos (si no, avisa y sigue sin desactivar; con `require_optimization=True` falla) y, al reactivar, busca filas huérfanas de cada FK: las que tienen quedan con `status="failed"` |
| MySQL / MariaDB | `SET SESSION FOREIGN_KEY_CHECKS=0` | `SET SESSION FOREIGN_KEY_CHECKS=1` | **No** | Lo usa; el resultado es `status="unverified"` |
| SQL Server | `ALTER TABLE t NOCHECK CONSTRAINT ALL` (FK y CHECK) | `ALTER TABLE t WITH CHECK CHECK CONSTRAINT ALL` | **Sí** (sin `WITH CHECK` quedarían «no confiables») | Lo usa con `WITH CHECK` |
| Oracle | `ALTER TABLE t DISABLE CONSTRAINT c` (por constraint) | `ALTER TABLE t ENABLE VALIDATE CONSTRAINT c` | **Sí** (falla si hay violaciones) | Lo usa con cada FK, CHECK con nombre y UNIQUE; el DDL confirma la transacción |
| SQLite | `PRAGMA foreign_keys = OFF` (no tiene efecto dentro de una transacción) | `PRAGMA foreign_keys = ON` | **No**; se comprueba con `PRAGMA foreign_key_check` | No desactiva nada |

Las UNIQUE y las CHECK de PostgreSQL no se desactivan: solo se pueden borrar y volver a crear. En SQL Server una UNIQUE
se desactiva desactivando su índice (`ALTER INDEX … DISABLE`, y `REBUILD` para reactivarla). No desactives las PK.

Comprobar a mano filas huérfanas de una FK (cualquier motor):

```sql
SELECT COUNT(*)
FROM orders c
WHERE c.customer_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM customers p WHERE p.id = c.customer_id);  -- debe ser 0
```

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

-- Oracle (nombre en mayúsculas si no se creó entre comillas):
SELECT DBMS_METADATA.GET_DDL('TABLE', 'TABLENAME') FROM dual;

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
- UK (order_number): 15% overhead → No desactivable en PostgreSQL (es un índice único, no un trigger)
- Auditoría (trigger): 18% overhead → NO desactivable (restricción de negocio)

**Recomendación**:
```
Fase 1 (Quick win, sin desactivar nada):
  Lotes de 20 000 filas (el default de BulkCrud para el INSERT de PostgreSQL)
  y la vía COPY de BulkCrud (requiere el driver psycopg 3 en el Engine).

Fase 2 (Medium, solo si la Fase 1 no basta):
  En PostgreSQL las FK se comprueban con triggers internos: DISABLE TRIGGER ALL
  (lo que hace maintenance_scope) apaga también el trigger de auditoría, que aquí
  no se puede desactivar. Alternativa sin tocar la auditoría:
    ALTER TABLE orders DROP CONSTRAINT fk_customer_id;
    -- carga
    ALTER TABLE orders ADD CONSTRAINT fk_customer_id
      FOREIGN KEY (customer_id) REFERENCES customers (id) NOT VALID;
    ALTER TABLE orders VALIDATE CONSTRAINT fk_customer_id;  -- falla si hay huérfanas

Mejora esperada: la de la Fase 1, medida con el banco (ver «Benchmark»).
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
  ALTER SESSION ENABLE PARALLEL DML;
  UPDATE en lotes de 5000;

Fase 2 (Medium, 25% ganancia):
  ALTER TABLE customers DISABLE CONSTRAINT uk_email;
  -- Oracle elimina el índice de la UNIQUE al desactivarla (salvo KEEP INDEX) y lo
  -- reconstruye al reactivarla: el coste se traslada al ENABLE.
  UPDATE 1M registros;
  Validar antes de reactivar:
    SELECT email, COUNT(*) FROM customers GROUP BY email HAVING COUNT(*) > 1;
  ALTER TABLE customers ENABLE VALIDATE CONSTRAINT uk_email;  -- lo que hace maintenance_scope

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
Paso 1: Desactivar solo los índices NO CLUSTERED, uno a uno
  ALTER INDEX ix_tabla_columna ON tablename DISABLE;
  -- ALTER INDEX ALL ... DISABLE desactiva también el CLUSTERED (la tabla deja de ser
  -- accesible) y los de PK/UNIQUE (sin control de duplicados; las FK que apuntan a la
  -- tabla quedan deshabilitadas y REBUILD no las reactiva). maintenance_scope solo
  -- desactiva los NONCLUSTERED no únicos, y solo en tablas sin índice CLUSTERED.

Paso 2: BULK INSERT sin la opción CHECK_CONSTRAINTS
  BULK INSERT tablename FROM 'file.csv' WITH (TABLOCK);
  -- Sin CHECK_CONSTRAINTS, BULK INSERT no comprueba CHECK ni FK y las marca como
  -- no confiables (is_not_trusted = 1).

Paso 3: Reconstruir índices + revalidar constraints
  ALTER INDEX ALL ON tablename REBUILD;
  ALTER TABLE tablename WITH CHECK CHECK CONSTRAINT ALL;  -- vuelven a ser confiables

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
```

Si hay duplicados, decide qué fila conservar de cada grupo **antes** de reactivar la UK; no hay un borrado automático
seguro (un `DELETE ... WHERE id IN (SELECT MAX(id) ...)` solo quita una fila por grupo y en MySQL/MariaDB ni siquiera se
puede referenciar la misma tabla en la subconsulta). Si la carga no debía traer duplicados, lo correcto es deshacerla.

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

**Solución**: no desactives los triggers de auditoría en operaciones críticas. En su lugar, registra la carga en una
tabla propia, o usa la auditoría de `util_bbdd` (`BulkCrud(audit=AuditOptions(csv_path=...))` o `AuditOptions(sink=...)`, que registran cada
operación al confirmarse, ver [Auditoría](../api/audit.md)):

```sql
INSERT INTO audit_metadata (table_name, rows_loaded, loaded_at)
VALUES ('orders', 100000, CURRENT_TIMESTAMP);
```

---

## 🧪 Benchmark: Medir impacto real

Después de la auditoría, valida con el banco contra motores reales. No hay un banco con escenarios por constraint: se
mide con los que existen.

```bash
# Volcado completo (dump): "indexes" = manage_indexes=True; "nocheck" = rehabilitar sin revalidar los datos
# (mide cuánto cuesta la validación al reactivar). Ver la guía de auditoría de rendimiento de dump, § «Uso del banco de rendimiento».
python scripts/bench_dump.py setup --engines postgresql,mssql --volume medium
python scripts/bench_dump.py run --engines postgresql,mssql --variants baseline,indexes,nocheck --volume medium --repeat 3 --out bench_results/constraints
python scripts/bench_dump.py summarize bench_results/constraints/results.jsonl

# Operaciones de BulkCrud por motor y tamaño (sin desactivar constraints): línea base de la carga
python scripts/bench_bulk.py --engines postgresql --sizes 100000,1000000 --ops insert --repeat 3 --out bench_results/bulk
```

`bench_bulk.py` escribe `results.csv`, `summary.md` y `environment.json` en `--out`. Para comparar con constraints
desactivadas, mide tu propia carga dentro de `bulk_session()` + `maintenance_scope(...)` frente a la misma carga sin él.
Los tests de comportamiento (no de rendimiento) de `maintenance_scope` están en `tests/unit/bulk/test_maintenance_scope.py`.

### Índices secundarios durante la carga (v3.2.0)

`maintenance_scope(disable_indexes=True)`, `ParallelOptions(disable_indexes=True)` y `DumpConfig(manage_indexes=True)`
comparten estrategia: desactivan los índices secundarios **no únicos** y los reconstruyen al final; nunca PK, UNIQUE ni
el índice clustered. Medido en el banco con `scripts/bench_index_modes.py` (tiempo total: desactivar + cargar +
reconstruir; PK + 2 secundarios + 1 UNIQUE):

| Motor | En serie, 3,5M filas | 4 hilos, 1M filas |
|---|---|---|
| PostgreSQL 17 | −25 % | +3 % a +4 % (más lento) |
| MySQL 8.4 | −16 % | −4 % a −6 % |
| MariaDB 11.4 | −9 % | +11 % (más lento) |
| SQL Server 2022 | −22 % | −32 % a −34 % |
| Oracle Free 23 | −88 % | −81 % a −82 % |

Compensa más cuantos más índices tenga la tabla y con filas desordenadas. En paralelo, PostgreSQL y MariaDB
ya reparten el coste de los índices entre hilos y la reconstrucción va en serie: se aplica igualmente, con un aviso.
En MariaDB/MySQL, `FOREIGN_KEY_CHECKS=0` (`disable_constraints=True`) ganó además un 9 % en una tabla con 2 FK. La
cifra de Oracle está inflada por el banco (2 CPU, columnas indexadas de baja cardinalidad); la dirección es robusta.
Detalle: `.ai/sessions/2026-10-18b-index-modes-bulk-dump/03_G0_MEDICION.md`.

```bash
python scripts/bench_index_modes.py --engines postgresql,mssql --rows 1000000 --profiles sec2u --repeat 3 \
    --out build/logs/bench_index_modes.md
python scripts/bench_index_modes.py --engines mysql,mariadb --profiles fk2 --constraints on,off --unique-checks on,off
python scripts/bench_index_modes.py --engines mssql,mysql,mariadb --probes-only   # comprobaciones de corrección
python scripts/bench_index_modes.py --fk-validation --rows 1000000 --repeat 3     # coste de validar FK tras cargar
```

### Todos los índices: `disable_indexes="all"` (v3.3.0)

`"all"` desactiva además los índices únicos y las PK/UNIQUE, salvo lo que el motor no permite quitar sin rehacer la
tabla (índice clustered de SQL Server, PK de InnoDB, PK de una IOT de Oracle), y gestiona las FK que los referencian:

| Motor | Únicos y PK/UNIQUE | FK de otras tablas que los referencian |
|---|---|---|
| SQL Server | NONCLUSTERED: `DISABLE` → `REBUILD` | El motor las deshabilita; se reactivan con `WITH CHECK CHECK CONSTRAINT` |
| Oracle | `DISABLE CONSTRAINT … CASCADE` → `ENABLE VALIDATE` (índices únicos sin constraint: no se tocan) | `ENABLE VALIDATE` después de la PK/UNIQUE |
| PostgreSQL | `DROP CONSTRAINT`/`DROP INDEX` → recreación con su DDL | Se borran antes y se recrean con `NOT VALID` + `VALIDATE CONSTRAINT` |
| MariaDB/MySQL | Únicos secundarios: `DROP INDEX` → `ADD UNIQUE INDEX` (en el mismo `ALTER` que los secundarios) | Los índices referenciados por una FK no se tocan |

En serie gana entre un 3 % y un 13 % más que `"secondary"` (3,5M filas, 2 secundarios + 1 UNIQUE: PostgreSQL −43 %,
MySQL −24 %, MariaDB −15 %, SQL Server −31 %, Oracle −89 %). **La unicidad no se comprueba durante la carga**, así que:

- exige `disable_constraints=True` (`ParallelOptions` y `maintenance_scope`) y no admite `on_error="isolate"`;
- en `dump` exige `truncate_target=True`; en `bulk` avisa si la tabla ya tiene filas;
- si un único no se puede reconstruir (duplicados), se restaura todo lo demás y se lanza `IndexRebuildError` con
  hasta 5 claves repetidas (`dump` no lanza: el índice queda `"failed"` con las claves en `error_msg`). En PostgreSQL
  y SQL Server, dentro de `bulk_session`, la sesión deshace también la carga (en SQL Server el propio servidor la
  deshace al fallar el `REBUILD`, y las claves no se pueden listar); en Oracle y MariaDB/MySQL las filas quedan.

Patrón recomendado para procesos de carga con iteraciones de calidad:

| Iteración | `disable_indexes` | Motivo |
|---|---|---|
| De validación (1…n−1) | `False` o `"secondary"` | PK y UNIQUE activas: un duplicado falla en el momento |
| Carga final, datos ya validados | `"all"` | Máximo rendimiento; la reconstrucción de los únicos es la última comprobación |

### Validar FK tras cargar sin FK checks: `validate_fks_after` (v3.3.0, por defecto desde v3.4.0)

En MariaDB/MySQL, `FOREIGN_KEY_CHECKS=1` no revisa lo ya cargado (resultado `"unverified"`).
Desde v3.4.0, `maintenance_scope` y `DumpConfig` lanzan por defecto al reactivar un `NOT EXISTS` por FK y devuelven
`"enabled"` o `"failed"` por FK (`validate_fks_after=False` vuelve a la fila única `"unverified"`). Coste medido con 1M filas y 2 FK: 0,2–0,23 s (≈1 % de la carga); la
revalidación nativa de los otros motores cuesta lo mismo (`WITH CHECK CHECK CONSTRAINT` 0,06 s en SQL Server,
`VALIDATE CONSTRAINT` 0,15 s en PostgreSQL, `ENABLE VALIDATE` 0,15 s en Oracle). `unique_checks=0` en MariaDB/MySQL
**no compensa** (sin índices desactivados fue un 3–7 % más lento; con `"secondary"`, como mucho un 1,5 % más rápido) y
no se ofrece.

---

## 📞 Contacto y recursos

Si necesitas más ayuda:

1. **Referencia técnica**: Lee `.github/prompts/performance_audit_constraints.prompt.md`
2. **Workflow**: Lee `.github/prompts/performance_audit_constraints_agent.prompt.md`
3. **Código**: `src/util_bbdd/bulk/_execution/maintenance.py` (lo que hace `maintenance_scope` por motor) y sus tests en
   `tests/unit/bulk/test_maintenance_scope.py`
4. **Documentación de BBDD**:
   - [PostgreSQL: DISABLE TRIGGER](https://www.postgresql.org/docs/current/sql-altertable.html)
   - [MySQL: foreign_key_checks](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_foreign_key_checks)
   - [Oracle: DISABLE CONSTRAINT](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/ALTER-TABLE.html)
   - [SQL Server: CHECK CONSTRAINT](https://docs.microsoft.com/en-us/sql/t-sql/statements/alter-table-transact-sql)

---

*Actualizado: 2026-10-10 (revisión de 1.1.0: SQL por motor corregido, banco real, qué hace ya la librería)*  
*Versión*: 1.0.0  
*Para preguntas*: Consulta `.ai/sessions/` de auditorías previas
