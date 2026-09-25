# TRACEABILITY

## Session metadata
- id: 2026-09-25-hotfix-audit-manager-quick-fixes
- fecha: 2026-09-25
- rama: develop (base `5499828`)
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION
- origen: `.ai/sessions/2026-09-25-audit-code-audit-manager/` (hallazgos H3, H4, H12; roadmap QW-1, QW-4, M-3)

## Prompt issued
```
empieza por los arreglos pequeños con /hotfix
```

## AI output summary
- **RCA**:
  - **H4**: `AuditCsvRepository.auditar_lote_csv` decidía si escribir la cabecera con `Path.exists()`. Un fichero de 0 bytes existe, así que no la escribía.
  - **H3**: `DumpOrchestrator._build_audit_summary` filtraba con `timestamp >= desde`, con `desde = datetime.now()` (microsegundos), sobre un CSV que guarda `%Y-%m-%d %H:%M:%S`.
  - **H12**: openpyxl infiere `data_type='f'` en toda cadena que empieza por `=`, y `DataFrame.to_excel` le pasa los valores tal cual.
- **IMPLEMENT** (sin cambiar el formato del CSV ni la API):
  - `bulk/_audit/repository.py`: cabecera si `file_handle.tell() == 0` tras abrir en modo `"a"`, que CPython posiciona al final al abrir. Sustituye a `exists()` y cubre el caso nuevo y el vacío dentro del mismo lock.
  - `dump/orchestrator.py`: `desde.replace(microsecond=0)` en el filtro.
  - `bulk/_audit/exporters.py`: `_desactivar_formulas(worksheet)` pasa a `data_type='s'` las celdas `f` tras cada `to_excel` (hojas por operación y `Resumen_global`). No se antepone `'`, porque en un `.xlsx` quedaría visible en el valor.
- **Tests nuevos** (5):
  - `test_audit_subsystem.py`: `test_fichero_vacio_existente_recibe_cabecera` y `test_fichero_con_datos_no_repite_cabecera` (guarda);
  - `test_audit_excel_export.py`: `test_text_starting_with_equals_is_written_as_text_not_formula`;
  - `dump/test_orchestrator.py::TestBuildAuditSummary`: mismo segundo incluido y segundo anterior excluido (guarda).
- **Validación**:
  - 3 tests en rojo con el código anterior y en verde después;
  - `ruff check` limpio; `ruff format --check` limpio en los ficheros tocados;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio (341 ficheros);
  - `tests/unit` completo: 4352 passed;
  - reproductores de la auditoría: R1 da `summary` con 1 operación y R4 da la cabecera correcta.

## AUDIT_CODE
- **Regresiones potenciales**:
  - H3: se amplía la ventana hasta el inicio del segundo. Una operación de otro volcado que termine en el mismo segundo y antes de `dump_inicio`, sobre el mismo CSV, se contaría. Es aceptable y está documentado en el CHANGELOG.
  - H4: `tell()` en modo append de texto devuelve el offset en bytes del final; verificado en Windows por el test.
  - H12: solo afecta a celdas que openpyxl había tomado por fórmula. El exportador nunca escribía fórmulas propias (grep).
- **Edge cases**: CSV con solo la cabecera (no la repite: `tell() > 0`); CSV ya dañado por H4 (no se repara, documentado); tabla con `+`, `-` o `@` al inicio (en `.xlsx` ya se guardaban como texto).
- **Compatibilidad**: sin cambios de firma, de esquema del CSV ni de columnas del Excel. No depende del dialecto.
- **Fuera de alcance**:
  - el propio CSV de auditoría, si se abre con Excel, sigue expuesto a CSV injection (neutralizarlo cambia el formato);
  - H1, H2 y el resto del roadmap siguen pendientes.
- **Nota**: `ruff format src tests` reformateaba además `bulk/_execution/range_partitioner.py` (deriva previa, ajena a este hotfix). Se ha revertido y sigue pendiente.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Fix H4 | `src/util_bbdd/bulk/_audit/repository.py` | modificado |
| Fix H12 | `src/util_bbdd/bulk/_audit/exporters.py` | modificado |
| Fix H3 | `src/util_bbdd/dump/orchestrator.py` | modificado |
| Tests | `tests/unit/test_audit_subsystem.py`, `tests/unit/test_audit_excel_export.py`, `tests/unit/dump/test_orchestrator.py` | modificados |
| Docs | `CHANGELOG.md` (`[Unreleased]` → Fixed) | modificado |

## Rollback
`git revert <commit>`. No hay migración de datos. Los CSV escritos después del fix son idénticos en formato.

## Directrices para Futuras IAs
- **[auditoría / cabecera]**: decidir la cabecera con `tell() == 0` tras abrir en `"a"`, dentro del lock por ruta; no volver a `exists()`.
- **[auditoría / Excel]**: todo export con openpyxl de texto no controlado debe pasar por `_desactivar_formulas` o equivalente. openpyxl convierte en fórmula cualquier cadena que empiece por `=`.
- **[dump / auditoría]**: el `timestamp` del CSV tiene resolución de segundo. Toda comparación con un `datetime` de Python debe truncar los microsegundos.
