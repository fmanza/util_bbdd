# TRACEABILITY

## Session metadata
- id: 2026-05-22-hotfix-ruff-migrate
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

```
Run python -m ruff check src/ tests/
F821 Undefined name `MigrationWarning`
   --> src/util_bbdd/migrate/extractors/sqlserver.py:168:33
   ...
Found 8 errors.
[*] 5 fixable with the `--fix` option.
Error: Process completed with exit code 1.
```

## Context supplied
- Salida completa de `ruff check src/ tests/` con 8 errores en 4 archivos
- Sesión previa: 2026-05-21-migrate-sqlserver-source (creó `sqlserver.py` + tests)

## AI output summary

- Diagnóstico causa raíz F821: `MigrationWarning` usada en líneas 168/173 de
  `extractors/sqlserver.py` pero ausente del import `from ..ir.models import (...)`.
- Verificado: `MigrationWarning` definida en `ir/models.py`, incluida en `__all__`,
  firma compatible (`table`, `column`, `oracle_type`, `target_type`, `message`, `severity`).
- Fix aplicado: `MigrationWarning` añadida al import existente de `ir.models`.
- `ruff --fix` aplicado en 3 archivos de test (I001, F401 — 7 errores corregidos automáticamente).
- F841 (`call_count = [0]` no usada) eliminada manualmente en `test_sqlserver_extractor.py`.
- Verificación final: `ruff check src/ tests/` → `All checks passed!`

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Extractor SQL Server | `src/util_bbdd/migrate/extractors/sqlserver.py` | modificado (+MigrationWarning import) |
| Test extractor | `tests/unit/migrate/test_sqlserver_extractor.py` | modificado (rm pytest, rm call_count, sort imports) |
| Test type map MariaDB | `tests/unit/migrate/test_type_map_mariadb.py` | modificado (rm pytest, sort imports) |
| Test type map SQL Server source | `tests/unit/migrate/test_type_map_sqlserver_source.py` | modificado (sort imports) |

## Veredicto final

Veredicto: **CLOSED**

Pendientes al cierre:
- Ninguno. `ruff check` limpio. Sin cambios de lógica funcional.
