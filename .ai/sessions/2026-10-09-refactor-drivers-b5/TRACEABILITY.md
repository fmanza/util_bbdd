# TRACEABILITY

## Session metadata
- id: 2026-10-09-refactor-drivers-b5
- fecha: 2026-10-09
- rama: develop
- skill: refactor
- fase: FASE 4 de `drivers-connections-audit`, bloque B5 (factories de Engine): PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/refactor

Objeto: drivers-connections-audit FASE 4 — bloque B5 (factories de Engine)
Alcance: extraer a un módulo compartido los helpers casi idénticos de factory/sqlalchemy_engine_factory.py y factory/async_sqlalchemy_engine_factory.py (_render_url 89 %, _get_test_query 92 %, _sanitize_conn_str 79 %, y lo común de _build_*_connection_string)
Evidencia: .ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md (duplicidad medida)
Versión: 0.35.10 (sin cambio de comportamiento). Commit + versión al cerrar.
```
Aprobación de IMPLEMENT: «si».

## Context supplied
- `.github/prompts/refactor.prompt.md`
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md`

## AI output summary
- AUDIT_PLAN: los `_build_*_connection_string` no se fusionan; sync y async divergen en casos límite (`host=None`, `database=None` → `conn_params["database"]` solo en async, SQL Server sin `database` solo rechazado en async, Oracle `service_name=""`). Unificarlos sería cambio funcional → deuda para B1.
- Nuevo `factory/_url.py` (`render_url`, `sanitize_conn_str`, `get_test_query`, `sqlite_url`); en ambas factories los privados quedan como alias `staticmethod(...)`; builders MySQL con `render_url`; rama `os.path.isabs` del SQLite async eliminada.
- Equivalencia: 9.744 combinaciones (5 builders × 2 factories × credenciales/host/puerto/`database`/`service_name`/`sid`, SQLite, sanitizado, test query) comparadas con los módulos de HEAD cargados en paralelo: 0 diferencias en salida, tipo de excepción ni mensaje.
- −153/+24 líneas en las factories; +65 en `_url.py` (neto −64).
- `ruff`/`mypy` OK (330 ficheros); `gen_arquitectura_capas.py` OK; `pytest` 5279 passed, 497 skipped (`build/logs/refactor_drivers_b5_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/refactor_drivers_b5_integration.txt`).
- Versión 0.35.10 en `pyproject.toml`, `CHANGELOG.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (330 ficheros).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/factory/_url.py` | creado |
| IMPLEMENT | `src/util_bbdd/factory/sqlalchemy_engine_factory.py`, `async_sqlalchemy_engine_factory.py` | modificados |
| VERSION | `pyproject.toml`, `CHANGELOG.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md` | 0.35.10 |

## Directrices para Futuras IAs
- **[factory/URL]**: punto canónico de URL, redacción y test query de los Engine: `factory/_url.py`. Los `_render_url`/`_sanitize_conn_str`/`_get_test_query` de las clases son alias que los tests llaman directamente.
- **[factory/builders]**: los `_build_*_connection_string` sync y async difieren a propósito en casos límite (ver AI output summary); en los 5 motores con `creator` la URL solo elige dialecto y sus credenciales no se usan para conectar. B1 puede reducirlos a elegir dialecto si la validación pasa a `*Config`.
- **[técnica/equivalencia]**: para probar un refactor sin cambio funcional, cargar la versión de HEAD en paralelo (`git show HEAD:<ruta> > <paquete>/_old.py`, borrar después) y comparar salidas y excepciones sobre un producto cartesiano de entradas.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Siguiente bloque: B4 (mapeo aiomysql único), `/refactor`, 0.35.x.
- Push y tags `v0.35.9` y `v0.35.10` pendientes.
