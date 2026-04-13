# AUDIT_PLAN: Fase 3 (M1 + M2)

## Riesgos funcionales

### M1: PostgreSQL parametrización

**¿Qué cambia?**
- SQL: De `.format(schema=..., name=...)` a `text("... || '.' || ...", {...})`
- Semántica: PostgreSQL interpola `:param` en lugar de Python

**Riegos identificados**:
1. **Regresión en fetch**: ¿La concatenación en PostgreSQL produce el mismo `regprocedure` que antes?
   - Mitigation: Unit test con mock que verifica resultado equivalente

2. **Unicode en schema_name o func_name**: ¿PostgreSQL maneja correctamente?
   - Mitigation: Que viene de `pg_proc.proname` (already vetted by PG)

3. **Performance**: ¿PostgreSQL || es más lento que Python .format()?
   - Mitigation: PostgreSQL `||` es nativa y rápida; overhead negligible

**Veredicto**: LOW RISK — Cambio defensivo sin impacto funcional observable.

### M2: Documentación HSQLDB

**¿Qué cambia?**
- Docstrings: Se agrega nota explícita sobre limitación HSQLDB
- Comportamiento: Ninguno (warnings ya existen)

**Riesgos identificados**:
1. **Rotura de contrato?**: ¿Hay callers que dependen del silence actual?
   - Mitigation: No — los warnings ya están en logs; documentación es additive-only

2. **API pública breaking change?**: ¿Se documenta que `include_routines=True` no funciona para HSQLDB?
   - Consideración: Es documentación defensiva, no cambio de behav
   - Mitigation: Actualizar también notas de release

**Veredicto**: NEGLIGIBLE RISK — Cambio de documentación solamente.

---

## Riesgos técnicos

### M1: SQL Injection — ¿De verdad se remedia?

**Análisis**:
- ✅ Antes: `.format()` interpolaba sin escapar
- ✅ Después: `text(:param)` con parámetros vinculados
- ✅ PostgreSQL maneja el cast `::regprocedure` de forma segura con params

**Edge case**: ¿Qué si `schema_name` es NULL o malformado?
- Mitigation: `get_schema_names()` valida esquemas; si `schema_name is None`, fallback a "public"

**Veredicto**: FIXED ✓

### M2: Documentación — ¿Cambios de línea números?

**Análisis**:
- Docstring en comparator.py línea ~82-103 es pequeño cambio (agregar ~5 líneas)
- No afecta numeración de métodos posteriores materialmente

**Veredicto**: SAFE ✓

---

## Riesgos de seguridad

### Ninguno

- No hay credenciales nuevas
- No hay permisos elevados
- SQL parametrizado es más seguro

---

## Simplificaciones posibles

### ¿Validar schema_name contra get_schema_names()?

**Pro**:
- Defense in depth
- Documenta que solo esquemas conocidos son aceptados

**Con**:
- Requiere llamada extra a Inspector (get_schema_names)
- Puede ser lento en BDs con 1000+ esquemas

**Decisión**: INCLUDE validación opcional con fallback — Si `schema_name not in get_schema_names()` y `schema_name != "public"`, loguear warning pero continuar.

---

## Gate: ¿GO o WAIT?

| Aspecto | Veredicto |
|---|---|
| Funcional | ✅ GO — Sin regriones esperadas |
| Técnico | ✅ GO — SQL injection remediada |
| Seguridad | ✅ GO — Mejora defensiva |
| Documentación | ✅ GO — Additive-only |
| Tests | ✅ Cobertura planificada |

**VEREDICTO FINAL**: **GO** — Fase 3 aprobada para IMPLEMENT
