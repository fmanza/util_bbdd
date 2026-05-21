# TRACEABILITY

## Session metadata
- id: 2026-05-22-hotfix-mypy-medir-tiempo
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

```
Run python -m mypy src
src/util_bbdd/bulk/crud.py:67: error: All conditional function variants must have identical signatures  [misc]
src/util_bbdd/bulk/crud.py:67: note: Original:
src/util_bbdd/bulk/crud.py:67: note:     def medir_tiempo(proceso: str = ...) -> Any
src/util_bbdd/bulk/crud.py:67: note: Redefinition:
src/util_bbdd/bulk/crud.py:67: note:     def medir_tiempo(proceso: str = ...) -> Callable[[Any], Any]
pyproject.toml: note: unused section(s): module = ['util.medir_tiempo']
Found 1 error in 1 file (checked 325 source files)
```

## Context supplied
- Salida completa de `python -m mypy src`
- Código del bloque `try/except ImportError` en `bulk/crud.py:63-81`
- Sección `[[tool.mypy.overrides]]` de `pyproject.toml`

## AI output summary

- Diagnóstico causa raíz: bloque `try/except ImportError` define dos variantes de
  `medir_tiempo`; la rama `try` importa con tipo inferido `-> Any` (stub ausente),
  mientras la rama `except` declara explícitamente `-> Callable[[Any], Any]`.
  mypy error `[misc]`: variantes condicionales deben tener firma idéntica.
- Override stale: `pyproject.toml` apuntaba a `util.medir_tiempo` pero la importación
  real es `util.timing.medir_tiempo` (path diferente → override nunca aplicaba).
- Fix 1: `crud.py:67` — `-> Callable[[Any], Any]` cambiado a `-> Any`.
- Fix 2: `pyproject.toml` — `"util.medir_tiempo"` actualizado a `"util.timing.medir_tiempo"`.
- Verificación: `python -m mypy src` → `Success: no issues found in 325 source files`.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| bulk/crud.py | `src/util_bbdd/bulk/crud.py` | modificado (return type fallback: Any) |
| pyproject.toml | `pyproject.toml` | modificado (override path corregido) |

## Veredicto final

Veredicto: **CLOSED**

Pendientes al cierre:
- Ninguno. mypy limpio (325 ficheros, 0 errores).
