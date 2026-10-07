# Resumen Ejecutivo: v0.31.1 Hotfix MariaDB SystemError

**Estado**: 🟡 APROBADO CON CONDICIONES (AUDIT_PLAN completado)  
**Fecha**: 2026-10-04  
**Alcance**: Hotfix CRÍTICO para MariaDB  
**Versión**: v0.31.1  

---

## El Problema en 30 Segundos

```
✗ Generación de documentación en MariaDB 0.31.0 falla con:
  SystemError: <method 'fetchrows' of 'mariadb.cursor'> returned result with exception set

✓ Causa: Driver mariadb (C binding) retorna SystemError cuando cursor se corrompe
✓ Inicio: v0.31.0 (ADR-003 — Centralización de Metadatos)
✓ Scope: Solo MariaDB; PostgreSQL/Oracle/SQL Server/SQLite NO afectados
```

---

## La Solución en 60 Segundos

**Componente**: `ManagerCatalogExecutor` en `managers/_catalog_executor.py`

**Fix**: 
1. Capturar `SystemError` específico de mariadb driver
2. Reintentar automáticamente con backoff exponencial (3 intentos max)
3. Agregar logging para debugging
4. Implementar lo mismo para async

**Resultado**:
- ✅ Documentación en MariaDB funciona (1er intento éxito = sin delay)
- ✅ Si falla 1x, se reintentan automáticamente (transparente)
- ✅ Backward compatible (sin cambios en API)
- ✅ Otros drivers no se impactan

---

## Roadmap de Implementación

| # | Fase | Duración | Qué | Quién | Estado |
|---|---|---|---|---|---|
| 1 | **PLAN** | 2h | Analizar error y diseñar fix | ✅ Completado | READY |
| 2 | **AUDIT_PLAN** | 1.5h | Auditar plan por riesgos y gaps | ✅ Completado | READY |
| 3 | **IMPLEMENT** | 3–4h | Codificar fix (sync + async) | ⏳ Por hacer | PENDIENTE |
| 4 | **AUDIT_CODE** | 1–2h | Revisar código por bugs y calidad | ⏳ Por hacer | PENDIENTE |
| 5 | **VERSION** | 0.5h | Commit + CHANGELOG + tag | ⏳ Por hacer | PENDIENTE |

**Total**: 8–10 horas (hotfix 1 día)

---

## Condiciones de Aprobación (AUDIT_PLAN)

🟡 Se aprobó el PLAN CON 4 CONDICIONES:

| # | Condición | Prioridad | Estado |
|---|---|---|---|
| 1 | Agregar reintento en `AsyncManagerCatalogExecutor` (no solo sync) | ALTA | ⏳ PENDIENTE |
| 2 | Agregar test async de reintento | MEDIA | ⏳ PENDIENTE |
| 3 | Actualizar docstrings y agregar logging detallado | MEDIA | ⏳ PENDIENTE |
| 4 | Validar `import time` en `_catalog_executor.py` | BAJA | ⏳ PENDIENTE |

✅ **Todas se abordarán en IMPLEMENT** (fases 1.1B + 2 + 3)

---

## Archivos de Referencia

| Tipo | Archivo | Propósito |
|---|---|---|
| 📋 **RCA** | [mariadb_fetchrows_error_analysis.md](mariadb_fetchrows_error_analysis.md) | Análisis técnico completo del error |
| 📐 **PLAN** | [hotfix_mariadb_plan.md](hotfix_mariadb_plan.md) | Diseño del fix con timeline |
| 🔍 **AUDIT** | [hotfix_mariadb_audit_plan.md](hotfix_mariadb_audit_plan.md) | Auditoría de riesgos y completitud |
| 📝 **SESIÓN** | [/memories/session/mariadb_error_investigation.md](/memories/session/mariadb_error_investigation.md) | Notas de sesión |

---

## Preguntas Frecuentes

### ¿Por qué solo MariaDB?
El driver `mariadb` (MariaDB Connector/Python) tiene un binding de C que retorna `SystemError` en lugar de `DatabaseError` cuando el cursor se corrompe. PyMySQL, asyncpg, etc. no tienen este problema.

### ¿El reintento enmascara otro bug?
Potencialmente. Por eso agregamos logging (PLAN Fase 2) para capturar el SQL exacto que falló.

### ¿Cuánto tiempo agrega a la documentación?
- **Si es éxito al 1er intento** (caso normal): 0ms extra
- **Si hay error que se reinténta**: máx 700ms (100ms + 200ms + 400ms)

### ¿Impacta a otros drivers?
NO. El error y fix son específicos a mariadb driver. PostgreSQL, Oracle, SQL Server, SQLite usan otros drivers/protocolos.

### ¿Qué pasa en v0.32.0?
Plan futuro: Validar que el SQL de catálogo se genera correctamente ANTES de ejecutar (para evitar reintentos).

---

## Siguiente Paso

➜ **Autorización para pasar a IMPLEMENT**

Si el equipo está de acuerdo:
1. Las 4 condiciones del AUDIT_PLAN se implementarán en IMPLEMENT
2. Tests se escriben en Fase 3
3. Código se audita en AUDIT_CODE
4. Se lanza v0.31.1 en VERSION

**Estimado**: 8–10 horas, completable hoy (2026-10-04)

---

*Documento ejecutivo completado*  
*Fecha*: 2026-10-04  
*Estado*: ✅ PLAN y AUDIT_PLAN terminados → Listo para IMPLEMENT
