# Índice: Plan RCA MariaDB Charset + Eliminación de Fallback
**Generado**: 2026-10-06 | **Estado**: PLAN + AUDIT_PLAN (sin IMPLEMENT)

---

## 📑 Documentos Generados

### 1. **Executive Summary** (Start Here! 📍)
📄 [`.ai/MARIADB_CHARSET_RCA_PLAN_EXEC_SUMMARY.md`](./MARIADB_CHARSET_RCA_PLAN_EXEC_SUMMARY.md)
- **Duración**: 5–10 minutos
- **Contenido**:
  - Problema en 1 página
  - 5 alternativas con tabla de evaluación
  - Estrategia ganadora (B + C + E)
  - Antes/después (fallback elimination)
  - Decisión recomendada
- **Para quién**: Stakeholders, revisores, quienes necesitan overview rápido

---

### 2. **Plan Completo** (Deep Dive)
📄 [`.ai/MARIADB_CHARSET_RCA_PLAN_v1.md`](./MARIADB_CHARSET_RCA_PLAN_v1.md)
- **Duración**: 20–30 minutos
- **Contenido** (10 secciones):
  1. Problema actual + contexto técnico
  2. Root Cause Analysis (3 hipótesis con evidencia)
  3. 5 alternativas con pro/contra
  4. Matriz de decisión
  5. Estrategia recomendada (B+C+E detallado)
  6. Eliminación de fallback (archivos, cambios)
  7. Investigación necesaria (6 puntos)
  8. Roadmap (4 fases)
  9. Decisión final
  10. AUDIT_PLAN checklist
- **Para quién**: Arquitectos, tech leads, implementadores, auditores

---

### 3. **Checklist de Investigación** (Hands-On)
📄 [`.ai/MARIADB_CHARSET_INVESTIGATION_CHECKLIST.md`](./MARIADB_CHARSET_INVESTIGATION_CHECKLIST.md)
- **Duración**: 1–2 sesiones (ejecución práctica)
- **Contenido** (6 secciones):
  - A: Verificaciones técnicas (driver, server, charset, datos)
  - B: Reproducción del error (scripts SQL + Python)
  - C: Benchmark PyMySQL vs mariadb
  - D: Testing integrado
  - E: Documentación de resultados
  - F: Notas de ejecución
- **Para quién**: QA, developers ejecutando RCA, investigadores

---

## 🎯 Flujo de Lectura Recomendado

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Leer: Executive Summary (5 min)                          │
│    ↓ Entender: Problema, 5 alternativas, estrategia ganadora│
│                                                             │
│ 2. Revisar: Matriz de Decisión en Executive (2 min)        │
│    ↓ Confirmar: ¿Por qué B+C+E?                           │
│                                                             │
│ 3. Leer: Plan Completo - Secciones 2-5 (10 min)           │
│    ↓ Profundizar: RCA detallado, hipótesis, alternativas  │
│                                                             │
│ 4. Revisar: AUDIT_PLAN (Sección 10, 5 min)                │
│    ↓ Validar: Checklist de verificación                   │
│                                                             │
│ 5. Ejecutar: Checklist de Investigación (1–2 sesiones)    │
│    ↓ Confirmar hipótesis, benchmark, reproduce error      │
│                                                             │
│ 6. Decisión: Siguiente sesión → IMPLEMENT                 │
│    ↓ Basada en resultados de investigación                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Búsqueda Rápida por Tema

### Alternativas
| Alternativa | Ubicación | Status |
|---|---|---|
| **A: PyMySQL** | Plan (§3.1), Summary (tabla) | Alternativa evaluada |
| **B: Charset Validation** | Plan (§3.2), Summary (fase 2) | ⭐ RECOMENDADO |
| **C: CONVERT/CAST** | Plan (§3.3), Summary (fase 4) | ⭐ COMPLEMENTARIO |
| **D: Binary Read** | Plan (§3.4) | ❌ No recomendado |
| **E: Error Explícito** | Plan (§3.5), Summary (fase 1) | ⭐ RECOMENDADO |

### Hipótesis de RCA
| Hipótesis | Ubicación | Evidencia |
|---|---|---|
| **A1: mariadb driver bug** | Plan §2.1 | SystemError en fetchrows() |
| **B1: charset_server deficiente** | Plan §2.2 | Datos heredados utf8mb3 |
| **C1: datos corruptos** | Plan §2.3 | H-41 menciona bytes inválidos |

### Checklist de Investigación
| Sección | Tema | Duración |
|---|---|---|
| A | Verificaciones técnicas (driver, server) | 30 min |
| B | Reproducción del error | 30–60 min |
| C | Benchmark PyMySQL vs mariadb | 30 min |
| D | Testing integrado | 60 min |
| E | Documentación de resultados | 20 min |

---

## 📋 Decisiones Clave

### 1. ¿Por qué eliminar fallback?
- ❌ **Antes**: Tolerancia silenciosa + 3 capas fallback (~600 líneas)
- ✅ **Después**: Error explícito + guía clara + solución directa
- **Beneficio**: Falla rápido, transparencia, mantenibilidad

### 2. ¿Por qué Opción B (Charset Validation)?
- ✅ Detecta problemas en servidor temprano
- ✅ Bajo overhead (validación 1× por pool)
- ✅ Independiente de driver (mariadb + pymysql)
- ✅ Standard SQL (portable a MySQL)

### 3. ¿Por qué no PyMySQL puro (Opción A)?
- ⚠️ Overhead 20–30% en bulk operations
- ⚠️ Cambio de driver es más invasivo
- ✅ Válido como fallback si Opción B insuficiente

### 4. ¿Cuándo usar CONVERT/CAST (Opción C)?
- ✅ Selectivo en campos problemáticos (comentarios, definiciones)
- ❌ No en todas las queries (overhead)
- ✅ Complemento a Opción B, no reemplazo

---

## 🚀 Próximos Pasos

### Fase 1: Investigación (esta sesión)
1. [ ] Leer: Executive Summary
2. [ ] Leer: Plan Completo
3. [ ] Revisar: AUDIT_PLAN

### Fase 2: RCA Técnico (próxima sesión)
1. [ ] Ejecutar: Checklist de Investigación (A–D)
2. [ ] Confirmar hipótesis
3. [ ] Benchmark PyMySQL vs mariadb
4. [ ] Documentar hallazgos (Sección E del checklist)

### Fase 3: Selección & IMPLEMENT (2 sesiones después)
1. [ ] Decidir entre:
   - ✅ Opción B (Charset Validation)
   - ✅ Opción B + A (Validation + PyMySQL fallback)
   - ✅ Opción B + C (Validation + CONVERT selectivo)
2. [ ] Implementar eliminación de fallback
3. [ ] Actualizar tests + docs

### Fase 4: Release & Monitoring
1. [ ] Version bump (0.32.3 o 0.33.0)
2. [ ] CHANGELOG + guía de troubleshooting
3. [ ] Monitoreo de issues GitHub

---

## 📌 Archivos Relacionados

**En este proyecto:**
- `src/util_bbdd/managers/_catalog_executor.py` → Código de fallback actual
- `src/util_bbdd/connection/config.py` → MariaDBConnectionConfig
- `src/util_bbdd/metadata/mariadb/catalog.py` → Queries de catálogo
- `CHANGELOG.md` → H-32 hotfix documentado

**Memoria de sesión:**
- `/memories/session/mariadb_rca_plan_session.md` → Resumen ejecutivo de sesión

**Hotfixes previos:**
- `/memories/repo/mariadb_unicode_decode_error_fix_h32.md` → H-32 (2026-10-05)
- `/memories/repo/mariadb_unicode_corrupt_metadata_fix_h41.md` → H-41 (análisis, no impl.)
- `/memories/repo/mariadb_charset_pool_fix_h39.md` → H-39 (pool config)
- `/memories/repo/mariadb_case_sensitivity_fix.md` → Fixes anteriores

---

## 💡 Preguntas Frecuentes (Pre-IMPLEMENT)

**P: ¿Por qué no simplemente actualizar mariadb driver a 1.2+?**  
R: Buena pregunta. Es parte de la investigación (Sección A1). Si un upgrade de driver resuelve, sería la solución más simple.

**P: ¿Qué pasa si elijo Opción A (PyMySQL puro)?**  
R: Válida si overhead es aceptable. Pero requiere cambio de driver por defecto y update de MariaDBConnectionConfig.

**P: ¿CONVERT/CAST aplica a MySQL también?**  
R: Sí, es SQL estándar. Ambos drivers (mariadb + pymysql) lo soportan.

**P: ¿Se rompe la API pública?**  
R: No. Cambios son internos (_catalog_executor.py). API pública (managers, config) se mantiene igual.

**P: ¿Cuántas líneas de código se eliminan?**  
R: ~600 líneas de fallback (_fetch_all_latin1_fallback, _fetch_all_pymysql_fallback, _extract_mariadb_connection_params).

---

## 🔗 Referencias Externas

- **MariaDB Connector/Python**: https://github.com/mariadb-corporation/mariadb-connector-python
- **PyMySQL**: https://github.com/PyMySQL/PyMySQL
- **SQLAlchemy Pooling**: https://docs.sqlalchemy.org/en/20/core/pooling.html
- **MariaDB Charset**: https://mariadb.com/kb/en/library/character-sets-and-collations/

---

## ✅ Checklist de Lectura

- [ ] Leer: Executive Summary
- [ ] Leer: Plan Completo (§1–5)
- [ ] Leer: AUDIT_PLAN (Plan §10)
- [ ] Revisar: Checklist de Investigación
- [ ] Confirmar: Estrategia B+C+E
- [ ] Preguntar: Dudas sobre alternativas
- [ ] Proceder: Fase 2 (Investigación técnica)

---

**Generado por**: GitHub Copilot  
**Referencia**: MARIADB_CHARSET_RCA_PLAN_v1.md  
**Estado**: ✅ PLAN + AUDIT_PLAN | ⬜ Sin IMPLEMENT
