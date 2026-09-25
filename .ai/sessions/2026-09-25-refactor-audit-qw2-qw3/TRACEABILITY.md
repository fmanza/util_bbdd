# TRACEABILITY

## Session metadata
- id: 2026-09-25-refactor-audit-qw2-qw3
- fecha: 2026-09-25
- rama: develop (base `7775c17`)
- skill: refactor
- origen: roadmap `.ai/sessions/2026-09-25-audit-code-audit-manager/` (QW-2 → H9, QW-3 → H10/P-11)

## Prompt issued
```
Sigue con el roadmap
```

## AI output summary
- **QW-2** (`bulk/_audit/repository.py`):
  - `_file_lock(path)` cachea el lock de `_get_file_lock` por instancia y lo recalcula si `audit_csv_path` cambia, así que el setter funciona sin tocarlo.
  - `_open_for_append(path)` sustituye al `mkdir` de cada escritura: ante `FileNotFoundError`, crea el directorio y reintenta una vez, dentro del lock.
- **QW-3** (`bulk/audit.py`, `bulk/_audit/repository.py`):
  - WARNING "Auditoría deshabilitada" una vez por instancia;
  - "🟢 … registrado/registradas en auditoría" y "🧹 Caché limpiado" a DEBUG.
- **API pública**: sin cambios. **Formato del CSV**: sin cambios.

## Validación
- **Tests nuevos** (5, `tests/unit/test_audit_subsystem.py`): directorio borrado a mitad; lock resuelto 1 vez en 5 escrituras; cambio de ruta vía setter; aviso único; sin INFO por operación.
- **Mutación**: quitar la caché del lock hace fallar 1 test; quitar el reintento con `mkdir` hace fallar 2.
- **Micro** (`bench_audit.py micro`, Windows):

  | Escenario | Antes | Después |
  |---|---|---|
  | Raíz en WARNING | 287 µs | 136 µs |
  | INFO + FileHandler | 370 µs | 122 µs |
  | Desactivada | 8,5 µs | 0,1 µs |

- **Calidad**: `ruff check` y `ruff format --check` limpios; `mypy` limpio (342 ficheros); `tests/unit` 4372 passed.

## AUDIT_CODE
- **Regresiones**:
  - Con ruta relativa y un cambio del directorio de trabajo entre escrituras, el lock cacheado corresponde al fichero original. Antes se recalculaba en cada escritura. Es muy improbable y el lock es intra-proceso.
  - Un error en el directorio padre (permisos, padre que es un fichero) sigue saliendo como `OSError` y lo trata la política de `audit_strict`.
- **Logs**: quien filtrara por los INFO de auditoría por operación deja de verlos salvo en DEBUG (anotado en el CHANGELOG).

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[auditoría / escritura]**: no volver a llamar a `Path.resolve()` ni a `mkdir` en el camino de escritura. Usar `_file_lock` y `_open_for_append`.
