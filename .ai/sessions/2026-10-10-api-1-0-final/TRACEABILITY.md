# TRACEABILITY

## Session metadata
- id: 2026-10-10-api-1-0-final
- fecha: 2026-10-10
- rama: develop (base v0.44.0, `920a5748`)
- skill: refactor (ruptura de API autorizada) + revisión de documentación
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (v1.0.0, local)

## Prompt issued
«Hazlo ahora, no necesito versión de avisos. Luego Revisar documentación y actualizar.»

## Context supplied
- `../2026-10-10-api-1-0/` (PLAN, AUDIT_CODE, TRACEABILITY), `../2026-10-10-exceptions-module-name/`
- `src/util_bbdd/__init__.py`, `managers/sync_mgr.py`, `connection/config.py`, `connection/postgresql/`,
  `factory/sqlalchemy_engine_factory.py`, `migrate/planner.py`, `pyproject.toml`
- README, `docs/` (ver `02_DOC_REVIEW.md`)

## AI output summary
- Probado antes de diseñar: con `from util_bbdd import X`, Python convierte el `AttributeError` de `__getattr__` en un
  `ImportError` genérico; un mensaje con la ruta nueva solo serviría para `util_bbdd.X`. Se retiran los alias sin tabla
  residual.
- `bb76b21a` — `refactor(api)!`: fuera `_DEPRECATED` y `SyncDatabaseManager.close_connection()`; tests de retirada.
- Revisión de documentación (`02_DOC_REVIEW.md`): comprobadores automáticos de imports (198) y métodos; README
  reescrito; instalación desde git (no hay paquete en PyPI: verificado con `pip index versions`); drivers de
  PostgreSQL y parámetros de pool verificados contra `connection/config.py`; extra `doc` inexistente en 6 páginas;
  `SchemaDiffReporter`; métodos inexistentes; ejemplos tocados ejecutados en el scratchpad.
- Errores propios detectados al verificar: `max_overflow` existe también en MySQL (no solo SQL Server); el primer
  extractor de bloques de código desalineaba fences (116 imports en vez de 198) y se rehízo por líneas.
- Cobertura: 91 % (`pytest --cov` sin el banco; `build/logs/api10final_coverage.txt`): cumple el criterio de 1.0.0 de
  `docs/roadmap.md` (≥ 85 %).
- Puerta: ruff, ruff format, mypy (332 ficheros) limpios; pytest sin banco 5678 passed, 523 skipped; con banco +
  `JAVA_HOME` 6194 passed, 7 skipped; `zensical build --strict` sin incidencias; `python -m build` → `util_bbdd-1.0.0`.
- VERSION: 1.0.0 en `pyproject.toml`, CHANGELOG (`Removed`, `Changed`), README, `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-api-1-0-final/01_PLAN.md` | GO |
| Revisión de docs | `.ai/sessions/2026-10-10-api-1-0-final/02_DOC_REVIEW.md` | emitido |
| Logs | `build/logs/api10final_*` | emitido |

## Directrices para Futuras IAs
- **[api]**: desde 1.0.0 la superficie pública es `util_bbdd.__all__` (13) + submódulos `exceptions`, `audit`,
  `metadata`, `connection`, `factory`, `async_utils`, `analysis` y los paquetes de cada punto de entrada. Un cambio
  incompatible ahí es MAJOR.
- **[docs]**: `util_bbdd` no está en PyPI; las instrucciones de instalación usan `git+https://…@vX.Y.Z`. No hay extra
  `doc`: openpyxl, python-docx y jinja2 son dependencias base.
- **[docs]**: los managers usan psycopg 3 (+ psycopg-pool) y asyncpg para PostgreSQL; psycopg2 solo aparece con Engines
  del usuario en `bulk`. Los parámetros de pool válidos por motor están en las `*PoolConfig` de `connection/config.py`.
- **[docs]**: para revisar ejemplos, extraer los bloques recorriendo líneas (una regex ```` ```(.*?)``` ```` desalinea
  fences) y resolver cada import contra el paquete; complementar con `dir()` de los managers para `manager.<m>(`.
- **[tests]**: `test_docs_version` exige que README, `docs/index.md`, `docs/roadmap.md` y el pie de
  `docs/architecture.md` cambien de versión en el mismo commit que `pyproject.toml`.

## Veredicto final
Veredicto: CLOSED (v1.0.0 en local)
Pendientes al cierre:
- Push de `develop` y tag `v1.0.0`: solo con autorización explícita del usuario.
- Fuera de alcance (ver `02_DOC_REVIEW.md`): `audit_csv_path` con `str`; `ResourceWarning` de SQLite con cobertura.
