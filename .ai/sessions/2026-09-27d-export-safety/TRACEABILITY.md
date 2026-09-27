# TRACEABILITY

## Session metadata
- id: 2026-09-27d-export-safety
- fecha: 2026-09-27 / 2026-09-28
- rama: develop
- skill: audit_code + hotfix + version_closure
- fase: RCA + FIX + AUDIT_CODE + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Revisa en src\dump, no se crear el fichero Excel, solo el CSV → logs de `pruebas_util` → `/audit-code` «todo lo
relacionado con exportación y una solución definitiva» → variante (a) → PLAN/AUDIT_PLAN de lo pendiente → IMPLEMENT
(opción (a) en el diagrama de capas) → `/version-closure`. Detalle en `00_REQUEST.md`.

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/instructions/sync.instructions.md`
- Logs del usuario: `C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\dump.log` y `util_bbdd_dump.log`
- CSV del usuario: `C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\dump\bulk_audit.csv` y sus tres copias de junio
- `src/util_bbdd/dump/`, `src/util_bbdd/bulk/_audit/`, `src/util_bbdd/comparar/reporters/`, `src/util_bbdd/doc/infrastructure/renderers/`

## AI output summary
- RCA 1 (hipótesis, luego descartada como causa del caso real): `IllegalCharacterError` de openpyxl no es `OSError` y
  escapaba de `DumpReporter.generate`. Fix en `_cell` + test.
- RCA 2 (causa real, `dump.log` 21:13:42): `KeyError: 'timestamp'` en `_audit_summary.build_audit_summary` tras la
  carga. `bulk_audit.csv` tenía las líneas 1–9 614 (hasta 2026-06-02 10:10:59) entrecomilladas enteras: re-guardado
  fuera de la librería (la librería escribe con `csv.writer(delimiter="\t")` desde 805889c; las copias de junio están
  limpias). Fix: comprobación de columnas → WARNING.
- `/audit-code` de exportación: 4 exportadores Excel + CSV de auditoría. Confirmado en `comparar/`: caracteres de
  control abortan el informe y `=HYPERLINK(...)` queda como fórmula. Veredicto APROBADO CON CONDICIONES.
- Commits `d56c991` (SafeWorkbook en los 4 informes Excel) y `94e25ca` (resumen tolerante, `DumpReportError.result`,
  CSV con cabecera no válida apartado, identidad del CSV en el resumen).
- `/audit-code` de `d56c991..94e25ca`: APROBADO; L1–L7 menores. Comprobado en vivo: cabecera sin cambios desde v0.1,
  8 hilos, `audit_strict` (fila confirmada + excepción = comportamiento previo), `pickle`.
- IMPLEMENT: P1 Word (`safe_text`, 39 textos vía transformación `ast`), P2 (a) diagrama, P3 `AuditExportError`,
  P4 nombre del informe, P5 tests `doc/`, P6/L3 docs, L1, L2, L4, L6.
- Durante IMPLEMENT el test de 8 hilos destapó un fallo latente: `_get_file_lock` usaba `str(path.resolve())`; en
  Windows devuelve `\\?\C:\...` mientras el fichero se renombra → dos locks para el mismo CSV → 3 de 320 filas
  perdidas. Fix: `os.path.normcase(os.path.abspath(path))`. 0 pérdidas en 5×320 tras el fix.
- Commits `9cc634c`, `1f18f06`, `133a445`, `fdfb037`, verificados uno a uno en `git worktree` aparte con
  `PYTHONPATH=<worktree>/src` (5270 → 5277 → 5285 → 5288).
- Incidente: `git stash --keep-index` con un `git mv` previo en el índice produjo un conflicto al hacer pop en
  `tests/unit/test_export_safety.py`; recuperado desde `stash@{0}` tras verificar `git diff stash@{0}` vacío.
- VERSION: `v0.18.3` (pyproject, CHANGELOG `[0.18.3] - 2026-09-28`, `.ai/CURRENT_STATE.md`, `INDEX.md`,
  `SESSIONS_DIGEST.md`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Módulo de escritura segura | `src/util_bbdd/_core/export_safety.py` | completado |
| Resumen tolerante + identidad del CSV | `src/util_bbdd/dump/_audit_summary.py`, `dump/orchestrator.py` | completado |
| `DumpReportError.output_path/.result` | `src/util_bbdd/_core/exceptions.py` | completado |
| CSV apartado + lock sin `resolve()` | `src/util_bbdd/bulk/_audit/repository.py` | completado |
| `AuditExportError` | `_core/exceptions.py`, `bulk/_audit/exporters.py` | completado |
| Informes Word | `comparar/reporters/word_reporter.py`, `doc/.../word_generator.py` | completado |
| Diagrama de capas | `scripts/gen_arquitectura_capas.py`, `docs/assets/diagrams/arquitectura-capas.svg` | completado |
| Tests | `tests/unit/test_export_safety.py` y 7 ficheros más (39 tests nuevos: 5249 → 5288) | 5288/199 |
| Docs | `docs/api/dump.md`, `bulk-audit.md`, `exceptions.md`, `architecture.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs

- **[export]**: Todo informe Excel se crea con `SafeWorkbook` (`_core/export_safety.py`); los de pandas pasan por
  `safe_frame` + `neutralize_formulas`. Todo texto no literal hacia python-docx pasa por `safe_text`. Un generador
  nuevo que use `openpyxl.Workbook()` o `add_paragraph(variable)` sin envolver reintroduce los dos fallos.
- **[export]**: `IllegalCharacterError` de openpyxl hereda solo de `Exception` (ni `ValueError` ni `OSError`); python-docx
  lanza `ValueError`. Un `except OSError` no los captura.
- **[dump]**: Tras la carga, nada auxiliar puede abortar `run()`: el resumen de auditoría degrada a WARNING y un fallo del
  informe se relanza como `DumpReportError` con `exc.result` (el `DumpResult`). `result` es `Any` porque `_core` no puede
  importar de `dump` (el script de capas cuenta también los imports bajo `TYPE_CHECKING`).
- **[bulk/audit]**: La cabecera del CSV es la misma desde v0.1 (`timestamp, tabla, motor, operacion, total_filas,
  tiempo_seg, sql`). Un CSV con otra cabecera se aparta como `<nombre>.invalid-<fecha>[_N].csv` en la primera escritura de
  cada instancia; un fallo de E/S al leerlo NO lo aparta (la ruta puede ser un directorio o estar bloqueada).
- **[bulk/audit]**: No usar `Path.resolve()` como clave de locks o cachés en Windows: devuelve `\\?\C:\...` o `C:\...`
  según el estado del fichero (p.ej. mientras se renombra). Usar `os.path.normcase(os.path.abspath(p))`.
- **[bulk/audit]**: Con `audit_strict=True` y fuera de `bulk_session`, un fallo al escribir el CSV lanza la excepción con
  las filas YA confirmadas en BD (comportamiento previo, no regresión).
- **[dump]**: `DumpConfig.output_dir` por defecto es `Path()`: el informe va al directorio de trabajo del proceso, no junto
  al CSV. Primera hipótesis a descartar cuando «no aparece el Excel».
- **[architecture]**: `gen_arquitectura_capas.py` deduce de la medición si `bulk → connection` es perezoso; desde
  `ad4b08e` es de módulo (`bulk/crud.py:46`). Si falla, no escribe nada.
- **[tooling]**: En Git Bash, los heredocs que generan código Python con `"\x00"`/`"\n"` dentro de strings pueden acabar
  como bytes reales en el fichero. Escribir tests con Write/Edit, o reparar con un script a nivel de bytes.
- **[tooling]**: No verificar commits parciales con `git stash --keep-index` si el índice tiene renombrados (`git mv`): el
  pop entra en conflicto. Usar `git worktree add --detach` + `PYTHONPATH=<worktree>/src` (el paquete está instalado en
  modo editable apuntando al `src` del repo principal).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- (Resuelto 2026-09-28) Tags `v0.18.2` (`ad4b08e`) y `v0.18.3` (`02d0a0c`) creados y publicados; `develop` subido a `origin`.
- CSV del usuario (`pruebas_util/.../bulk_audit.csv`): se apartará solo en el próximo volcado; no se ha tocado.
- L5 (valor provisional `report=cfg.output_dir` en `run()`) aceptado como está, con comentario.
- `detail.html.j2:416` usa `|safe` con el SVG de Graphviz: fuera del alcance de exportación, sin revisar.
