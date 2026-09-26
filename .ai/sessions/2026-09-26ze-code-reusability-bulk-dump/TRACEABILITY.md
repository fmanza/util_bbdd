# TRACEABILITY

## Session metadata
- id: 2026-09-26ze-code-reusability-bulk-dump
- fecha: 2026-09-26
- rama: develop
- skills: prompt `code_reusability_architecture.prompt.md` → refactor (PLAN, AUDIT_PLAN, IMPLEMENT) → hotfix
- nota: la carpeta se creó como `2026-09-26zd-…` y se renombró a `ze` al cerrar v0.17.1 (colisionaba con
  `2026-09-26zd-version-closure-v0.17.0`, de otra sesión en paralelo). Los mensajes de `34aee9f` y `825f025` citan
  el nombre antiguo.

## Artefactos
- [REPORT.md](REPORT.md): análisis de 9 secciones de `bulk/` y `dump/`.
- [PLAN.md](PLAN.md): PLAN y AUDIT_PLAN (GO_CONDICIONAL, decisiones D-1 a D-5).
- [IMPLEMENT.md](IMPLEMENT.md): incrementos R1–R10, verificación y pendientes.

## Commits
- `62908b1` refactor(bulk,dump): helpers extraídos y división de `orchestrator.py` y `batch.py` (R1–R4, R6–R10).
- `e513db1` docs: `.ai/architecture.md`, `CURRENT_STATE` § Calidad actual, `DumpResult`, guía.
- `34aee9f`, `825f025` docs(ai): artefactos de la sesión e integración (338/0).
- `9ef505e` fix(dump): `DumpConfig` valida `chunk_size` y `commit_every_n_chunks` antes de vaciar el destino.
- `f5ca1b6` refactor(dump): R5, rangos de PK con `RangePartitioner` (equivalencia en 39 063 casos).
- `acbb342` docs: CHANGELOG (corregido con `--amend` antes de publicar: la primera versión no incluía el fichero).
- Publicado en v0.17.1 (sesión `2026-09-26zf-version-closure-v0.17.1`).

## Pendientes
- R11–R14 del PLAN (SQL de catálogo a `metadata/`, SQL de mantenimiento por motor, `TableReflector`,
  `SessionScope`); R15–R16 opcionales. Orden recomendado: R11 → R12 + R13 → R14 en sesión propia.
- Puntos reclasificados fuera del refactor (capacidad del pool, `rows_committed` con DELETE, jerarquía de
  `AuditError`): `/new-feature` si hay necesidad.

## Directrices para Futuras IAs
- **[refactor/tests]**: al mover código, un `patch("mod.nombre")` solo intercepta si `mod` es donde se **usa** el
  nombre. Comprobar cada destino (script en IMPLEMENT.md § Verificación) y sabotear en el punto de uso: parchear el
  módulo de origen no alcanza a quien hizo `from x import nombre` ni a un `staticmethod(...)` capturado en la clase.
- **[dump]**: los tests parchean `util_bbdd.dump.orchestrator._read_chunks` (24 veces) y `._prefetch`; sus llamadores
  deben seguir en `orchestrator.py`. `event` se parchea en `util_bbdd.dump._source_reader`.
- **[logging]**: los módulos separados de `orchestrator.py` y `batch.py` usan explícitamente el logger del módulo
  original (`util_bbdd.dump.orchestrator`, `util_bbdd.bulk._execution.batch`); 7 tests filtran por ese nombre.
- **[bulk]**: la cadencia de commit del DELETE reinicia su contador en cada llamada y no suma a `rows_committed`; la del
  INSERT se arrastra en la sesión. Un `SessionScope` (R14) debe conservar ambas.
- **[dump]**: fases. Documentación pública y docstrings de `DumpConfig`/`DumpResult`: 7 fases (PK sync = «Fase 6a»).
  Comentarios y log de `orchestrator.py`: 5 fases («Fase 5a»). No renumerar el log sin decisión.
- **[cobertura]**: con Python 3.14 + numpy, `pytest --cov=util_bbdd.x` falla; usar
  `COVERAGE_CORE=sysmon python -m coverage run --branch --source=src/util_bbdd/<pkg> -m pytest …`.
- **[banco]**: sin `UTIL_BBDD_BENCH_PASSWORD` en el entorno, el usuario autorizó usar la de los contenedores del banco
  (la misma en todos): leerla de `docker inspect` sin mostrarla y codificarla para URL.

## Veredicto final
Veredicto: CLOSED
