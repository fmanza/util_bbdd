# TRACEABILITY

## Session metadata
- id: 2026-10-16h-static-analysis-fixes
- fecha: 2026-10-16
- rama: develop (base `4020e39c`, tras v3.0.1)
- skill: correcciones aviso a aviso (Pylance + SonarLint) + version_closure v3.0.2
- fase: IMPLEMENT por aviso + VERSION

## Prompt issued
Avisos de Pylance y SonarLint pegados uno a uno desde el IDE (sin texto propio salvo la selección del editor), y al
final «/version-closure de los cambios de esta sesion».

## Context supplied
- Los diagnósticos del IDE (regla, fichero, línea) y la línea seleccionada en el editor.
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md` y la memoria del proyecto (español, no `git add -A`, puerta sin URLs
  del banco).

## AI output summary
- **bulk** (`bulk/options.py`): `BulkOptions.audit`/`rejects` con `field(default_factory=lambda: AuditOptions())` y
  `lambda: RejectOptions()` (Pylance `reportCallIssue`); `BulkOptions.for_worker` marcado `# NOSONAR` (S5886 falso
  positivo sobre `dataclasses.replace`). Primer intento con el motivo en un comentario que empezaba por «NOSONAR:» →
  S7632; se reformuló.
- **_core** (`_core/export_safety.py`): `SafeWorksheet.append` pasa `cast(Any, iterable)` en la rama que delega el
  `TypeError` en openpyxl (Pylance `reportArgumentType`).
- **analysis** (`analysis/graphviz_ext.py`): el motivo del `# noqa: BLE001` de `_render_batch` sin coma (S7632).
- **connection** (`connection/hsqldb/connection_hsqldb.py`): la regex que enmascara `;password=` de la URL JDBC marcada
  `# NOSONAR` (S2068 falso positivo); `factory/_url.py::sanitize_conn_str` no cubre ese formato.
- **_core** (`_core/exceptions.py`): el bucle que asigna `__module__ = "util_bbdd.exceptions"` pasa a
  `_set_public_module()` (Pylance `reportPossiblyUnboundVariable` por el `del` de la variable de bucle).
- Cada cambio verificado al hacerlo con `npx pyright` (1.1.414), `ruff check`, `ruff format --check`, `mypy` del fichero
  y los tests relacionados (`-k options`: 72; `-k export_safety…`: 19; `-k exception`: 216 + 12 skipped).
- `/version-closure` v3.0.2: CHANGELOG, `pyproject.toml`, `README.md` (2), `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md`, `CURRENT_STATE`, `SESSIONS_DIGEST`, `INDEX`.

## Tests and evidence
- Puerta (`build/logs/v3.0.2_gate.txt`), shell sin URLs del banco: `ruff check` y `ruff format --check` sobre
  `src tests` (716 ficheros), `mypy src tests/unit/test_protocol_conformance.py` sin errores (339), `pytest`
  **6219 passed, 532 skipped** (igual que v3.0.1).
- `scripts/gen_arquitectura_capas.py`: el dibujo coincide con el código (339 ficheros; SVG/CSS sin diferencias).
- Cierre (`build/logs/v3.0.2_final.txt`): `tests/unit/test_docs_version.py` 6 passed, `zensical build --strict` sin
  avisos, `python -m build` (sdist y wheel 3.0.2).
- Banco de motores no ejecutado: los cambios no alteran el comportamiento.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Código | `src/util_bbdd/bulk/options.py`, `_core/export_safety.py`, `_core/exceptions.py`, `analysis/graphviz_ext.py`, `connection/hsqldb/connection_hsqldb.py` | sin commit |
| Versión | `CHANGELOG.md`, `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `.ai/sessions/SESSIONS_DIGEST.md`, `.ai/sessions/INDEX.md` | sin commit |
| Logs | `build/logs/v3.0.2_gate.txt`, `build/logs/v3.0.2_final.txt` | generados |

## Known limitations
- Solo se corrigieron los avisos que se pegaron; no se pasó SonarLint ni pyright sobre todo `src/`.
- Ningún test nuevo: los cambios no alteran el comportamiento (el de `_set_public_module` lo cubren los tests de pickle
  y `__module__` de las excepciones).

## Rollback
- `git revert` del commit de la sesión (o `git checkout -- <ruta>` antes de confirmar). Riesgo nulo: sin cambios de API
  ni de comportamiento.

## Directrices para Futuras IAs
- **[pyright]**: un dataclass con un campo descriptor (`OptionalPathField`/`PathField` de `_core/validation/paths.py`)
  no es asignable a `Callable[[], T]`: pyright toma la instancia del descriptor como default del `__init__` y no encaja
  con el tipo de su `__set__`. `field(default_factory=Clase)` falla; `default_factory=lambda: Clase()` pasa. Afecta a
  `AuditOptions`, `RejectOptions` y `DumpConfig`.
- **[pyright]**: `npx --yes pyright <ficheros>` reproduce los avisos de Pylance desde la terminal (el venv no tiene
  `pyright`); mypy no da ninguno de estos.
- **[sonarlint]**: S7632 lee lo que sigue a `# noqa:` como lista de códigos separada por comas: un motivo
  `# noqa: BLE001 - a, b` es «sintaxis inválida». También salta si un comentario propio empieza por `NOSONAR:`. El
  motivo de un `NOSONAR` va en la línea anterior y no empieza por esa palabra.
- **[sonarlint]**: S5886 sobre `return dataclasses.replace(self, ...)` es falso positivo (typeshed:
  `replace(obj: _DataclassT, ...) -> _DataclassT`); se marca `# NOSONAR` y no se reescribe con el constructor, que
  perdería en silencio los campos que se añadan.
- **[sonarlint]**: S2068 salta con cualquier literal que contenga `password=`, también la regex que lo enmascara
  (`connection_hsqldb.py`).
- **[_core]**: la ruta pública de las excepciones (`util_bbdd.exceptions`) se fija en `_set_public_module()` al final
  de `_core/exceptions.py`; recorre `globals()` sin copiarlo (asignar `__module__` no cambia el diccionario).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit, tag `v3.0.2` y push: propuestos, no ejecutados.
