# PLAN: Análisis RCA MariaDB + Eliminación de Fallback
**Versión**: 1.0 | **Estado**: PLAN + AUDIT_PLAN | **Fecha**: 2026-10-06

---

## Executive Summary

### El Problema
```
SystemError: fetchrows() returned a result with an exception set
↳ Ocurre al leer information_schema de MariaDB
↳ Ya hay 3 capas de fallback (retry 3×, latin1, pymysql) → aún falla
↳ Usuario quiere: eliminar fallback + propuestas sin fallback
```

### Root Cause: 3 Hipótesis

| Hipótesis | Síntoma | Riesgo | Solución |
|---|---|---|---|
| **A1**: mariadb driver 1.1 tiene bug de C extension | SystemError en fetchrows() | Alto | Upgrade driver o cambiar a PyMySQL |
| **B1**: MariaDB server no tiene UTF-8 configurado | charset deficiente | Medio | Validar @@character_set_server |
| **C1**: information_schema datos corruptos | Bytes inválidos incluso en latin1 | Bajo | Limpiar BD o usar CONVERT/CAST en queries |

---

## 5 Alternativas Evaluadas

```
┌─────────────────────────────────────────────────────────────┐
│ Opción A: PyMySQL como driver principal (pure Python)        │
│ ✅ Pro: Sin SystemError, simple                             │
│ ❌ Contra: Overhead 20–30% en bulk operations               │
│ ⭐ Recomendación: Medio (considerar si performance OK)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Opción B: Charset Validation explícita en sesión [RECOMENDADO]
│ ✅ Pro: Detecta problemas temprano, overhead bajo           │
│ ✅ Pro: Independiente de driver (mariadb + pymysql)        │
│ ⭐ Recomendación: Alto (IMPLEMENTAR)                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Opción C: CONVERT/CAST en queries [COMPLEMENTARIO]          │
│ ✅ Pro: Resilencia a datos corruptos                        │
│ ✅ Pro: SQL-level cleanup, sin cambiar driver               │
│ ⭐ Recomendación: Bajo–Medio (usar selectivo en campos)    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Opción D: Binary read (sin fallback)                        │
│ ❌ No recomendado: Duplica lógica actual sin mejora        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Opción E: Error explícito + guía clara [RECOMENDADO]       │
│ ✅ Pro: Falla rápido, transparencia total                  │
│ ✅ Pro: Obliga a usuario a configurar servidor             │
│ ⭐ Recomendación: Alto (IMPLEMENTAR)                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Estrategia Ganadora: B + C + E (Combinada)

### Fase 1: Validación de Servidor (Opción E)
Falla **explícitamente** si servidor no tiene UTF-8:
```python
def _validate_mariadb_charset(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT @@character_set_server")
    server_cs = cursor.fetchone()[0]
    if server_cs.lower() not in ("utf8mb4", "utf8"):
        raise MetadataError(f"❌ MariaDB: character_set_server='{server_cs}'"
                           f" Ejecute: ALTER DATABASE CHARACTER SET utf8mb4;")
```

### Fase 2: Garantizar UTF-8 en Sesión (Opción B)
```python
def _ensure_session_charset(connection):
    cursor = connection.cursor()
    cursor.execute("SET NAMES 'utf8mb4'")  # Garantía por sesión
```

### Fase 3: Retry Simple (2×, NO fallback)
```python
def fetch_all(self, sql, params):
    for attempt in range(2):
        try:
            return self._executor.fetch_all(sql, params)
        except SystemError as exc:
            if attempt == 0:
                time.sleep(0.1)  # Retry una vez
                continue
            raise MetadataError(f"MariaDB charset error (RCA requerido)")
```

### Fase 4: Cleanup Selectivo en Queries (Opción C)
Aplicar solo a comentarios/definiciones:
```sql
SELECT TABLE_NAME,
       CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4) AS TABLE_COMMENT,
       TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = :schema
```

---

## Cambios Arquitectónicos

### Antes (Fallback Actual)
```
┌──────────────────────────────────────┐
│ fetch_all()                          │
├──────────────────────────────────────┤
│ → Reintento 3×: 100ms, 200ms, 400ms  │
│ → Si falla:                          │
│    └─ Fallback latin1                │
│       └─ Si falla:                   │
│          └─ Fallback pymysql         │
│             └─ Si falla: ERROR       │
│ Total fallbacks: 2 (~600 líneas)     │
└──────────────────────────────────────┘
```

### Después (Propuesto)
```
┌──────────────────────────────────────┐
│ fetch_all()                          │
├──────────────────────────────────────┤
│ → Validar charset_server (una vez)   │
│ → SET NAMES 'utf8mb4' (por sesión)   │
│ → Reintento 2×: 100ms (simple)       │
│ → Si falla: ERROR explícito + guía   │
│ Total fallbacks: 0 (~50 líneas)      │
│ Ventajas: Claro, mantenible, rápido │
└──────────────────────────────────────┘
```

### Archivo a Eliminar
- `_fetch_all_latin1_fallback()` (307 líneas)
- `_fetch_all_pymysql_fallback()` (391 líneas)
- `_extract_mariadb_connection_params()` (~30 líneas)

**Total eliminado**: ~600 líneas de código fallback

---

## Investigación Necesaria (Pre-Implementación)

### RCA Profundo (Sección 7 del plan completo)
- [ ] Verificar versión MariaDB server destino
- [ ] Probar cada hipótesis (A1, B1, C1)
- [ ] Benchmark: PyMySQL vs mariadb driver
- [ ] Testing: Reproducir error con charset deficiente

### Testing
- [ ] Crear BD MariaDB con charset heredado (utf8mb3)
- [ ] Validar cada alternativa (A, B, C, E)
- [ ] Coverage de casos edge

### Documentación
- [ ] Guía de troubleshooting para usuarios
- [ ] Performance impact (Opción A vs B)

---

## Roadmap

| Fase | Tarea | Sessions | Status |
|---|---|---|---|
| **1** | Investigación RCA (hipótesis A1/B1/C1) | 1–2 | ⬜ Pendiente |
| **2** | Selección de estrategia final | 1 | ⬜ Pendiente |
| **3** | IMPLEMENT (eliminar fallback, aplicar B+C+E) | 2–3 | ⬜ Pendiente |
| **4** | Release + docs + monitoring | 1 | ⬜ Pendiente |

---

## Decisión Final Recomendada

### ✅ IMPLEMENTAR: Opción B (Validation) + C (CONVERT Selectivo) + E (Error Explícito)

**Por qué esta combinación:**
1. **Falla explícita** → error claro, sin fallback oculto
2. **Independiente de driver** → mariadb o pymysql
3. **Bajo overhead** → validación 1× por pool, no por query
4. **Escalable** → solución por motor, aplicable a MySQL también
5. **Resilencia** → CONVERT para datos heredados
6. **Mantenible** → ~600 líneas menos de código

**Beneficio principal**: De "tolerancia con fallback" → "fallo explícito + guía clara"

---

## Documento Completo

Para análisis profundo, ver: [`.ai/MARIADB_CHARSET_RCA_PLAN_v1.md`](./MARIADB_CHARSET_RCA_PLAN_v1.md)

Contiene:
- RCA detallado de 3 hipótesis (A, B, C)
- 5 alternativas con matriz de decisión
- Implementación concreta de cada opción
- Checklist de verificación (AUDIT_PLAN)
- Testing y documentación necesarios
