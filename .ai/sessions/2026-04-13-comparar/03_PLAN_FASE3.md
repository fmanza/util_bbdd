# PLAN: Fase 3 (M1 + M2) — Remediación de hallazgos MEDIUM

## Objetivo

Remediar 2 hallazgos MEDIUM identificados en AUDIT_CODE_FASE2:
- **M1**: SQL injection potencial en PostgreSQL `_get_routines_postgresql()` — usar parametrización segura
- **M2**: Documentación incompleta sobre limitación HSQLDB — mejorar docstrings de API pública

## Rutas afectadas

| Fichero | Cambios |
|---|---|
| `src/util_bbdd/comparar/comparator.py` | M1: parametrización en línea 873-876; M2: docstring en línea 82-103 |
| `tests/comparar/test_comparator.py` | Tests para M1 parametrización |

## M1: PostgreSQL SQL Injection — MEDIUM

### Contexto

Ubicación actual (comparator.py: 873-876):
```python
ddl_result = conn.execute(
    text(
        "SELECT pg_get_functiondef(('{schema}.{name}'::regprocedure)::oid) AS definition"
        % (schema_name, func_name)  # ← SQL injection risk aquí
    )
)
```

**Riesgo**: Aunque `func_name` y `schema_name` vienen de metadatos de confianza (`pg_proc.proname`, validación), la construcción de string literal en cast `::regprocedure` es teóricamente inyectable.

### Solución propuesta

Usar parametrización PostgreSQL completa. **Opción A** (recomendada): Delegar a PostgreSQL la construcción del regprocedure:

```python
# ✅ Opción A: PostgreSQL interpola el regprocedure
ddl_result = conn.execute(
    text("SELECT pg_get_functiondef((:schema_name || '.' || :func_name)::regprocedure) AS definition"),
    {"schema_name": schema_name, "func_name": func_name}
)
```

**Ventaja**: Parametrización completa sin interpolación en Python.

**Alternativa B** (más segura pero menos elegante):
```python
# Escapar schema_name y func_name como identificadores PostgreSQL
# Usar quote_ident() si disponible, o validación whitelisto
```

**Recomendación**: Usar Opción A + agregar validación de esquemas conocidos como precaución adicional.

### Tipos necesarios

Sin cambios de tipos.

## M2: HSQLDB Documentation — MEDIUM

### Contexto

`_get_routines_hsqldb()` devuelve `[]` silenciosamente sin error. Pero docstring de `compare()` no documenta:
- HSQLDB no soporta introspección de routines
- `include_routines=True` ignora HSQLDB de facto

### Solución propuesta

1. **Docstring de `compare()`** (línea 82-103):
   - Agregar nota: "Nota: No todos los motores soportan introspección de routines. `include_routines=True` será ignorado para HSQLDB con warning."

2. **Docstring de `_get_routines_hsqldb()`** (línea 900-907):
   - Expandir warning: documentar explícitamente que HSQLDB no expone DDL portable

3. **Docstring de `_strip_dialect_artifacts()`** (linea 636):
   - Documentar cuáles motores tienen reglas definidas

## Impactos en auth/roles

Ninguno. Los cambios son puramente técnicos (SQL) y documentación.

## Riesgos

| Risk | Mitigación |
|---|---|
| **Regresión en PostgreSQL fetch** | Tests unitarios verifican resultado equivalente |
| **Performance hit por concatenación** | PostgreSQL || es eficiente natively; no hay overhead |
| **Documentación incompleta** | Auditar todos los docstrings de `_get_routines_*` |

## Plan de implementación

```
1. IMPLEMENT M1 + M2
   1a. Parametrización PostgreSQL: cambiar línea 873-876
   1b. Validación adicional: lista de esquemas permitidos (get_schema_names)
   1c. Docstrings mejorados: compare(), _get_routines_hsqldb(), _strip_dialect_artifacts()

2. TESTS
   2a. Test M1 parametrization behavior con mocks
   2b. Test M2 docstring completeness (verificar warning HSQLDB documentado)

3. VALIDATE
   3a. ruff check, mypy, pytest

4. AUDIT_CODE

5. VERSION + closure
```

## Veredicto esperado

GO — Cambios menores, bajo riesgo, cobertura defensiva.
