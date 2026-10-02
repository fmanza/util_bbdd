# Prompt: Auditoría de Rendimiento — Desactivación de Constraints en Carga Masiva

**Rol**: Arquitecto de software senior experto en optimización de bases de datos y carga masiva
**Objetivo**: Analizar el impacto de rendimiento de desactivar constraints durante operaciones bulk INSERT/UPDATE/DELETE
**Scope**: Constraints (FK, UK, CHECK, DEFAULT), estrategia de desactivación, re-habilitación segura, integridad de datos

---

## 📋 Inputs requeridos

Antes de ejecutar, confirma que dispones de:

- ✅ **Contexto de operación**: Tabla objetivo, número de filas (1K, 10K, 100K, 1M), tipo de operación (INSERT, UPDATE, DELETE)
- ✅ **Constraints definidas**: Listar constraints por tipo (FK, UNIQUE, CHECK, DEFAULT, IDENTITY)
- ✅ **Base de datos objetivo**: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite (comportamiento varía)
- ✅ **Métricas de partida**: Tiempo base con constraints activos (si disponible)
- ✅ **Datos de test**: Conjunto representativo que pueda validarse post-carga
- ✅ **Restricciones de negocio**: ¿Se permite desactivar constraints? ¿Cuánto tiempo puede quedar la integridad en riesgo?

Si falta alguno, decláralos como supuesto explícito antes de continuar.

---

## 🔍 Áreas de auditoría

### 1. **Identificación y tipología de constraints**
   - **Foreign Key (FK)**: Validación referencial en cada INSERT/UPDATE/DELETE
   - **Unique Key (UK)**: Búsqueda de duplicados antes de INSERT/UPDATE
   - **Check constraints**: Validación de rango/patrón por fila
   - **Default values**: Evaluación en el motor vs. aplicación
   - **Primary Key (PK)**: Índice único por defecto, difícil de desactivar
   - **Not Null**: Validación mínima, costo bajo
   - **Triggers**: Pueden ser más costosos que constraints
   - **Índices asociados**: Índices creados automáticamente por constraints (FK → índice)
   - **Referencia de internet**: Buscar "[DB] constraint performance impact analysis", "disabling constraints for bulk load"

### 2. **Análisis de costo por constraint**
   - **FK (Foreign Key)**:
     - Costo: Búsqueda en tabla padre por cada fila
     - Impacto típico: 10-40% overhead en INSERT con múltiples FKs
     - Agravante: JOIN implícito en ON DELETE CASCADE
     - **Medición**: Comparar tiempo INSERT con FK activa vs. desactivada

   - **Unique Key (UK)**:
     - Costo: Escaneo de índice único por INSERT/UPDATE
     - Impacto típico: 5-15% overhead
     - Agravante: Múltiples UKs por tabla
     - **Medición**: Comparar con constraint desactivado

   - **Check constraints**:
     - Costo: Bajo (evaluación de predicado simple)
     - Impacto típico: 1-5% overhead
     - **Medición**: Comparar con constraint desactivado

   - **Índices en cascada**:
     - Costo: Inserción en índice B-tree por cada constraint
     - Impacto típico: 10-30% overhead (índices múltiples)
     - **Medición**: Comparar INSERT con índices vs. sin índices

### 3. **Estrategias de desactivación por BBDD**

   #### PostgreSQL
   ```sql
   -- Desactivar constraints específicas
   ALTER TABLE tablename DISABLE TRIGGER ALL;
   ALTER TABLE tablename DISABLE RULE all;

   -- Desactivar FK específica
   ALTER TABLE tablename DISABLE TRIGGER constraint_name;

   -- Re-validar después
   ALTER TABLE tablename ENABLE TRIGGER ALL;
   ALTER TABLE tablename VALIDATE CONSTRAINT constraint_name;
   ```
   - **Costo de re-validación**: O(n) donde n = filas no sincronizadas
   - **Referencia**: PostgreSQL docs "Disable Triggers"

   #### MySQL / MariaDB
   ```sql
   -- Deshabilitar checks de FK
   SET foreign_key_checks = 0;
   -- ... INSERT/UPDATE/DELETE ...
   SET foreign_key_checks = 1;

   -- Re-validar manualmente
   CHECK TABLE tablename;
   ANALYZE TABLE tablename;
   ```
   - **Riesgo**: No hay re-validación automática; requiere validación manual
   - **Referencia**: MySQL docs "Disabling Foreign Key Checks"

   #### Oracle
   ```sql
   -- Desactivar constraint específica
   ALTER TABLE tablename DISABLE CONSTRAINT constraint_name;

   -- Re-habilitar
   ALTER TABLE tablename ENABLE CONSTRAINT constraint_name;

   -- Validar sin activar
   ALTER TABLE tablename ENABLE CONSTRAINT constraint_name NOVALIDATE;
   ```
   - **Costo de re-habilitación**: Puede ser muy alto si hay violaciones
   - **Referencia**: Oracle docs "Disabling and Enabling Constraints"

   #### SQL Server
   ```sql
   -- Deshabilitar constraint
   ALTER TABLE tablename NOCHECK CONSTRAINT constraint_name;

   -- Deshabilitar todos
   ALTER TABLE tablename NOCHECK CONSTRAINT ALL;

   -- Re-habilitar y validar
   ALTER TABLE tablename WITH CHECK CHECK CONSTRAINT constraint_name;
   ALTER TABLE tablename WITH CHECK CHECK CONSTRAINT ALL;
   ```
   - **Costo de validación**: Alto si hay violaciones
   - **Índices**: Pueden estar deshabilitados también
   - **Referencia**: SQL Server docs "Disabling Constraints"

   #### SQLite
   ```sql
   -- Desactivar checks por sesión
   PRAGMA foreign_keys = OFF;
   -- ... INSERT/UPDATE/DELETE ...
   PRAGMA foreign_keys = ON;

   -- NO hay re-validación automática; requiere validación manual
   ```
   - **Riesgo**: No hay mecanismo de re-validación; alto riesgo de corrupción
   - **Referencia**: SQLite docs "PRAGMA foreign_keys"

### 4. **Estrategia de re-habilitación segura**
   - **Fase 1**: Desactivar constraints antes de bulk load
   - **Fase 2**: Realizar INSERT/UPDATE/DELETE
   - **Fase 3**: Validar integridad de datos (ver sección 6)
   - **Fase 4**: Re-habilitar constraints
   - **Fase 5**: Hacer rollback en caso de violaciones detectadas

   **Riesgo de integridad**:
   - ¿Pueden haber valores FK inválidos después de carga?
   - ¿Pueden violar UKs durante actualización?
   - ¿Pueden Check constraints ser violated?
   - **Mitigación**: Validación previa de datos, cuarentena, rollback

### 5. **Medición de impacto**

   **Benchmark recomendado**:
   ```
   Escenario 1: Todos los constraints activos (baseline)
   Escenario 2: Solo FKs desactivadas
   Escenario 3: Solo UKs desactivadas
   Escenario 4: Todos los constraints desactivados
   Escenario 5: Además, índices deshabilitados (SQL Server)
   ```

   **Métricas por escenario**:
   - Tiempo total de INSERT/UPDATE/DELETE (ms)
   - Throughput (filas/segundo)
   - CPU usage (%)
   - Memory footprint (MB)
   - Costo de re-validación (ms) si aplica
   - **Total time = bulk operation + constraint re-enable time**

### 6. **Validación de integridad post-carga**

   #### PostgreSQL
   ```sql
   -- Listar filas con FK inválidas
   SELECT * FROM tablename t
   WHERE NOT EXISTS (SELECT 1 FROM parent_table p WHERE t.fk_col = p.id);

   -- Validar constraint
   ALTER TABLE tablename VALIDATE CONSTRAINT fk_constraint;
   ```

   #### MySQL / MariaDB
   ```sql
   -- Validar FK manualmente
   SELECT COUNT(*) FROM tablename t
   LEFT JOIN parent_table p ON t.fk_col = p.id
   WHERE p.id IS NULL AND t.fk_col IS NOT NULL;

   -- Validar UK
   SELECT col, COUNT(*) FROM tablename GROUP BY col HAVING COUNT(*) > 1;
   ```

   #### Oracle
   ```sql
   -- Validar constraint
   ALTER TABLE tablename ENABLE CONSTRAINT fk_constraint VALIDATE;

   -- Buscar violaciones antes de validar
   SELECT * FROM tablename t
   WHERE NOT EXISTS (SELECT 1 FROM parent_table p WHERE t.fk_col = p.id);
   ```

   #### SQL Server
   ```sql
   -- Validar constraint
   ALTER TABLE tablename WITH CHECK CHECK CONSTRAINT constraint_name;

   -- Si hay error, listar violaciones
   SELECT * FROM tablename t
   LEFT JOIN parent_table p ON t.fk_col = p.id
   WHERE p.id IS NULL AND t.fk_col IS NOT NULL;
   ```

### 7. **Identificación de constraints críticos vs. opcionales**
   - **Críticos**: FK referenciando tabla productiva, UNIQUE en identificadores
   - **Opcionales**: CHECK constraints de negocio, DEFAULT values normalizables
   - **Materia de riesgo**: Desactivar críticos = riesgo de corrupción; desactivar opcionales = ganancia mínima
   - **Matriz riesgo/beneficio**: Por constraint

### 8. **Overhead de auditoría y triggers**
   - ¿Hay triggers asociados a FKs (ON DELETE CASCADE)?
   - ¿Hay triggers de auditoría (audit_manager)?
   - Desactivar triggers puede aumentar riesgo de inconsistencia
   - **Medición**: Comparar tiempo con triggers activos vs. desactivados

### 9. **Opciones alternativas a desactivar constraints**
   - **Batch size tuning**: ¿Lotes más grandes reducen overhead?
   - **Índices deshhabilitados**: Desactivar índices durante carga, reconstruir después (SQL Server)
   - **Directivas específicas por BBDD**: Oracle hints, MySQL LOAD DATA INFILE, PostgreSQL COPY
   - **Paralelización**: ¿Cargas paralelas en diferentes particiones?
   - **Validación diferida**: Constraints con deferred checking (PostgreSQL)
   - **Referencia de internet**: Buscar "[DB] bulk load performance tuning without disabling constraints"

### 10. **Riesgos residuales**
   - **Corrupción de datos**: Si hay violaciones y no se detectan
   - **Bloqueos**: Re-validación puede bloquear la tabla
   - **Tiempo de downtime**: Tabla indisponible durante re-habilitación
   - **Reversión fallida**: Si hay violaciones, no se puede re-habilitar el constraint
   - **Auditoría**: Registrar qué constraints fueron desactivados y cuándo
   - **Recuperación**: Plan de rollback si la carga falla post-desactivación

---

## 📊 Deliverables esperados

### PLAN
- Inventario de constraints por tabla (FK, UK, CHECK, DEFAULT, etc.)
- Matriz de impacto teórico por constraint (costo % en INSERT/UPDATE/DELETE)
- Estrategia de desactivación recomendada (quién desactivar, en qué orden)
- Plan de validación post-carga (qué verificar, cómo)
- Timeline estimado (desactivación + carga + re-validación)

### AUDIT_PLAN
- Validación de viabilidad por BBDD (PostgreSQL, MySQL, Oracle, SQL Server, SQLite)
- Riesgos de integridad identificados
- Alternativas consideradas (batch tuning, índices, directives específicas)
- Tests de regresión propuestos
- Orden de ejecución (dependencias)

### AUDIT_CODE (Hallazgos)

Para cada hallazgo, reportar:

```markdown
### Hallazgo: [Nombre del constraint o estrategia]
**Severidad**: CRÍTICA | ALTA | MEDIA | BAJA | INFO
**Tipo de Constraint**: FK | UK | CHECK | DEFAULT | TRIGGER | ÍNDICE
**Tabla/Constraint**: [nombre exacto]
**Descripción**: [qué constraint, por qué ralentiza, en qué BBDD]
**Impacto estimado**: [% mejora si se desactiva]
**BBDD especificidad**: [PostgreSQL | MySQL | Oracle | SQL Server | SQLite | multi]
**Confirmación**: [CONFIRMADA | HIPÓTESIS | DEPENDE_DE_DATOS]

#### Evidencia
- Constraint definition: [DDL]
- Costo observado: [benchmark si disponible]
- Referencia/documentación: [link BBDD oficial si aplica]

#### Estrategia de desactivación
- Comando SQL: [DDL específica del BBDD]
- Costo de desactivación: [tiempo estimado]
- Costo de re-habilitación: [tiempo estimado + posibles violaciones]

#### Validación post-carga
- Query de verificación: [SQL para buscar violaciones]
- Acción en caso de violación: [rollback | fix | ignore]
- Impacto en tiempo total: [desactivación + carga + re-validación]

#### Mitigación de riesgos
- Riesgo de corrupción: [alto | medio | bajo]
- Alternativa sin desactivar: [batch tuning | índices | directives]
- Recomendación final: [desactivar | NO desactivar | evaluar caso por caso]
```

### VERSION
- Veredicto final: **CRÍTICO | SIGNIFICATIVO | MODERADO | LIMPIO**
- Resumen: top 5 constraints con mayor impacto
- Estrategia recomendada de desactivación
- Quick wins (desactivaciones sin riesgo, > 5% mejora)
- Fases de implementación (seguridad, validación, rollback)
- Checklist de validación post-carga
- Métricas esperadas (antes/después en benchmark)
- Recomendaciones de configuración por BBDD

---

## 🎯 Criterios de prioridad

| Prioridad     | Criterio de entrada                                      | Impacto esperado | Riesgo de corrupción | Quick-win? |
|---------------|----------------------------------------------------------|------------------|----------------------|-----------|
| **CRÍTICA**   | FK/UK en tabla > 100K filas, > 20% overhead              | 20-50%↑          | ALTO                 | ❌        |
| **ALTA**      | FK/UK en tabla 10K-100K filas, 10-20% overhead          | 10-20%↑          | MEDIO                | ⚠️        |
| **MEDIA**     | CHECK/DEFAULT en tabla cualquier tamaño, 5-10% overhead | 5-10%↑           | BAJO                 | ✅        |
| **BAJA**      | Constraint con impacto < 5% o casos edge                | < 5%↑            | MUY BAJO             | ✅        |
| **INFO**      | Alternativa viable (batch tuning, índices)              | N/A              | NONE                 | ✅        |

---

## 🛠️ Comandos de benchmark recomendados

Para reproducir y validar análisis:

```bash
# Setup: crear tabla con constraints
python -m pytest tests/bulk/test_constraints_performance.py -v -s

# Benchmark: comparar escenarios
python scripts/bench_bulk.py run \
  --engines postgresql,mysql,mssql,oracle \
  --scenarios baseline,no_fk,no_uk,no_constraints,all \
  --volume 100k,1m \
  --out .ai/sessions/<sesión>/constraint_analysis

# Resumen de resultados
python scripts/bench_bulk.py summarize \
  .ai/sessions/<sesión>/constraint_analysis/results.jsonl
```

---

## 📚 Referencias de internet (buscar si aplica)

- "[Database] disable constraints bulk insert performance"
- "[Database] constraint validation cost analysis"
- "[Database] foreign key performance tuning"
- "[Database] unique key index overhead"
- "[Database] re-enable constraints after bulk load"
- "bulk insert best practices without disabling constraints"
- "data integrity validation post-bulk-load patterns"

---

*Versión*: 1.0.0
*Actualizado*: 2026-09-26
*Aplicable a*: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite
*Módulos relacionados*: `src/util_bbdd/bulk/`, `src/util_bbdd/metadata/`, `src/util_bbdd/audit/`
