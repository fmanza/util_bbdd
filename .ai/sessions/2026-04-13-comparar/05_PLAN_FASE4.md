# PLAN: Fase 4 (L1 + L2 + L3) — Optimizaciones y robustez

## Objetivo

Abordar 3 hallazgos LOW identificados en AUDIT_CODE_FASE2 para mejorar robustez, performance y coverage:
- **L1**: Mejorar regex MSSQL para soportar caracteres especiales en brackets
- **L2**: Documentar limitaciones de performance (N+1 queries en schemas grandes)
- **L3**: Parametrizar tests de exception handling (TimeoutError, PermissionError, Deadlock)

## Rutas afectadas

| Fichero | Cambios | Prioridad |
|---|---|---|
| `src/util_bbdd/comparar/comparator.py` | L1: línea 54 (regex); L2: docstrings | L1 = ⭐⭐, L2 = ⭐ |
| `tests/comparar/test_comparator.py` | L3: +3 parametrized tests | ⭐⭐ |

---

## L1: MSSQL Bracket Regex — LOW

### Contexto

**Línea actual** (comparator.py:54):
```python
(r"\[(\w+)\]", r"\1"),  # SQL Server: Escaped brackets [name] → name
```

**Problema**:
- `\w+` solo matchea `[a-zA-Z0-9_]`, pero SQL Server permite:
  - Espacios: `[My Table Name]`
  - Guiones: `[Column-X]`
  - Punto: `[dbo.table]` (aunque rare)

**Ejemplo fallido**:
```python
sql = "SELECT [My Column] FROM [My Table Name]"
result = SchemaComparator._strip_dialect_artifacts(sql)
# ❌ Resultado: "SELECT My FROM My" (solo captura primer word)
# ✅ Esperado: "SELECT My Column FROM My Table Name"
```

### Solución propuesta

```python
# ❌ Antes (limited):
(r"\[(\w+)\]", r"\1"),

# ✅ Después (flexible):
(r"\[([^\]]+)\]", r"\1"),  # Captura todo excepto ]
```

**Explicación**: `[^\]]+` captura cualquier carácter menos `]`, permitiendo espacios, guiones, etc.

### Tests nuevos para L1

```python
class TestStripDialectArtifactsMSSQLSpecialChars:
    def test_handles_spaces_in_brackets(self):
        sql = "CREATE PROCEDURE [My Procedure] AS BEGIN END"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "[" not in result
        assert "My Procedure" in result

    def test_handles_dashes_in_brackets(self):
        sql = "CREATE TABLE [My-Table] ([Column-X] INT)"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "[" not in result
        assert "My-Table" in result
```

---

## L2: Performance Documentation — LOW

### Contexto

**Riesgo identificado**:
- MSSQL: Query `SELECT name FROM sys.procedures WHERE schema_id = SCHEMA_ID(...)` sin LIMIT
- PostgreSQL: Query `SELECT * FROM pg_proc JOIN pg_namespace ...` sin LIMIT

En schemas con 10k+ routines, esto puede ser lento o causar memory issues.

### Solución propuesta

**Agregar docstrings alerta**:

1. En `_get_routines_mssql()`:
   ```python
   """...
   **Performance note**: On large schemas (10k+ procedures), this may be slow.
   Consider limiting results or caching.
   """
   ```

2. En `_get_routines_postgresql()`:
   ```python
   """...
   **Performance note**: Uses pg_get_functiondef() which materializes full DDL.
   On schemas with 10k+ functions, this may consume significant memory.
   """
   ```

3. En `_get_routines_mariadb()`:
   ```python
   """...
   **Performance note**: SHOW PROCEDURE STATUS is relatively fast, but large databases
   benefit from pagination. Consider calling SchemaComparator.compare(..., include_routines=False)
   for performance-critical scenarios.
   """
   ```

### Tests para L2

No hay tests automáticos (es documentación), pero verificar manualmente:
```python
# El docstring debe estar presente
assert "Performance" in SchemaComparator._get_routines_mssql.__doc__
```

---

## L3: Exception Tests — LOW

### Contexto

**Cobertura actual**:
- ✓ OperationalError (connection refused)
- ✓ Engine is None
- ✗ TimeoutError (conexión tarda mucho)
- ✗ PermissionError (insuficientes permisos)
- ✗ Deadlock (deadlock en BD)

### Solución propuesta

Parametrizar tests con excepciones adicionales:

```python
@pytest.mark.parametrize("exc_type,exc_msg", [
    (TimeoutError, "connection timeout"),
    (PermissionError, "insufficient privileges"),
    (Exception, "unexpected error"),  # Catch-all para otros fallos
])
def test_mssql_handles_various_exceptions(exc_type, exc_msg):
    inspector = MagicMock()
    engine = _make_engine_mock("mssql")
    inspector.engine = engine
    engine.connect.side_effect = exc_type(exc_msg)

    routines = SchemaComparator._get_routines_mssql(inspector, "dbo")
    assert routines == []  # Fallback seguro
```

**Aplicar a**:
- `_get_routines_mssql()`
- `_get_routines_postgresql()`
- `_get_routines_mariadb()`
- `_get_routines_oracle()`

---

## Impactos

### Funcional

| L1 | L2 | L3 |
|---|---|---|
| Corrección de regex | Documentación defensive | Cobertura de robustez |
| **Sin cambio de comportamiento** | **Sin cambio funcional** | **Sin cambio funcional** |

### Tests

- **L1**: +2 tests (espacios, guiones)
- **L2**: +0 tests (docstring assertion)
- **L3**: +4 tests parametrizados (1 per motor × 3 excepciones + catch-all)

**Total L1+L2+L3**: ~+6 nuevos tests

### Performance

- **L1**: No hay impacto (es método de regex puro)
- **L2**: Documentación solamente
- **L3**: Tests con mocks (sin impacto en suite)

## Plan de implementación

```
1. IMPLEMENT L1 + L2 + L3
   1a. Actualizar regex MSSQL (línea 54)
   1b. Agregar performance docstrings (3 métodos fetchers)
   1c. Parametrizar exception tests (4 motores)

2. TESTS
   2a. Run L1 tests nuevos (regex)
   2b. Run L3 tests nuevos (exceptions)
   2c. Verify L2 docstrings presentes

3. VALIDATE
   3a. ruff check, mypy, pytest

4. AUDIT_CODE

5. VERSION + closure
```

## Veredicto esperado

**GO** — Cambios de bajo riesgo, estrictamente mejoras de robustez y documentación.
