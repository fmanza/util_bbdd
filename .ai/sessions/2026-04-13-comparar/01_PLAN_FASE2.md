# PLAN: Fase 2 (D1 + D4)

## Objetivo

Extender `SchemaComparator` con soporte para **3 motores adicionales** (mssql, postgresql, hsqldb):
- **D1**: Implementar `_get_routines_*` para los 3 motores
- **D4**: Agregar reglas de limpieza DDL dialect-específicas

## Rutas afectadas

| Fichero | Cambios |
|---|---|
| `src/util_bbdd/comparar/comparator.py` | +3 métodos fetcher, +3 reglas DDL, actualización registro |
| `tests/comparar/test_comparator.py` | +12 tests (4 por motor) |

## Componentes implicados

### D1 · Routines

**Contexto**: `Inspector` de SQLAlchemy no tiene API estándar para routines. Cada motor expone metadatos de forma diferente.

#### Motores a implementar

| Motor | Tabla sistema | Query | Fetch definición | Notas |
|---|---|---|---|---|
| **mssql** (SQL Server) | `sys.procedures` / `sys.objects` | `sysobjects` + tipo 'P'/'C'/'RF' | `OBJECT_DEFINITION()` o `sp_helptext` | Procedures, triggers como routines |
| **postgresql** | `pg_proc` / `pg_namespace` | `JOIN` con schema | `pg_get_functiondef()` | Functions; procedures en PG11+ |
| **hsqldb** | `INFORMATION_SCHEMA.ROUTINES` | Standard SQL schema | N/A (solo lectura) | Muy limitado; devolver lista vacía o error controllado |

**Especificaciones por motor**:

##### SQL Server (mssql)

```sql
SELECT name, type
FROM sys.procedures
WHERE schema_id = SCHEMA_ID('dbo')

SELECT definition
FROM sys.sql_modules
WHERE object_id = OBJECT_ID('name')
```

Tipos a capturar: `P` (stored procedures), `C` (check constraints — opcional), `RF` (replication-filter-procedure — opcional). **Recomendación**: solo `P`.

##### PostgreSQL

```sql
SELECT pg_get_functiondef('schema_name.function_name'::regprocedure) AS definition
SELECT * FROM pg_proc
JOIN pg_namespace ON pg_proc.pronamespace = pg_namespace.oid
WHERE nspname = 'schema_name'
```

Tipos: `p` (procedure), `f` (function). **Recomendación**: ambos.

##### HSQLDB

HSQLDB tiene `INFORMATION_SCHEMA.ROUTINES` pero no expone DDL portable. **Recomendación**: retornar lista vacía con warning.

### D4 · DDL Stripping Rules

**Contexto**: Cada motor emite DDL con artefactos propios (encoding, timestamps, owner info).

#### Reglas a agregar

| Motor | Patrón | Razón |
|---|---|---|
| **mssql** | `\[\w+\]` | Escaped identifiers `[name]` → `name` |
| **mssql** | `WITH \(.*?\)` | Storage hints (`FILLFACTOR`, etc.) — opcional |
| **postgresql** | `LANGUAGE \w+` | Lenguaje PL/pgSQL / PL/Python |
| **postgresql** | `SECURITY DEFINER\|SECURITY INVOKER` | Contexto de seguridad |
| **postgresql** | `STRICT\|RETURNS NULL ON NULL INPUT` | Comportamiento de nulls |
| **hsqldb** | ninguna (no emite routines) | N/A |

**Nota**: Las reglas se aplican **antes** de la normalización universal, permitiendo que motores con artefactos sean comparables.

## Tipos necesarios

Todos los métodos siguen la firma:

```python
@staticmethod
def _get_routines_X(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
    """Obtiene routines de X."""
    return [
        {"name": "...", "type": "PROCEDURE|FUNCTION", "definition": "..."},
        ...
    ]
```

## Impactos en auth/roles

Ninguno. Los fetch utilizan credenciales heredadas del engine.

## Riesgos

| Risk | Mitigación |
|---|---|
| **SQL injection en identifiers** | Usar `text()` + params, no f-strings |
| **Conexión con permisos insuficientes** | Uso de try-except; logging de warnings |
| **DDL stripping sobre-agresivo** | Tests compartidos para verificar no-regresiones |
| **Performance**: queries lentas en sys.procedures | Lazy evaluation; documentar sobre grandes schemas |
| **HSQLDB sin soporte DDL**: falso negativo | Documentar limitación; retornar [] con warning |

## Plan de implementación

```
1. IMPLEMENT D1 + D4
   1a. Agregar _get_routines_mssql, _get_routines_postgresql, _get_routines_hsqldb
   1b. Agregar reglas a _DDL_STRIP_RULES
   1c. Actualizar registro _ROUTINE_FETCHERS

2. TESTS
   2a. Tests unitarios para cada fetcher (mocks + real SQLite)
   2b. Tests de reglas DDL (verificar patterns no rompen queries válidas)

3. VALIDATE
   3a. ruff check, mypy, pytest

4. AUDIT_CODE

5. VERSION + closure
```

## Veredicto esperado

GO — Cambios ajustados, bajo riesgo de regresión, cobertura completa de 6 motores.
