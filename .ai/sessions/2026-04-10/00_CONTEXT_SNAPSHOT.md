# CONTEXT SNAPSHOT

## Contexto del repositorio revisado

- `CLAUDE.md` — instrucciones del proyecto, reglas SOLID, arquitectura, slash commands
- `.ai/architecture.md` — arquitectura de 3 niveles (v0.6.2 al inicio)
- `.ai/v0.6.7-release-tracking.md` — tracking de bloqueantes y checklist de cierre
- `src/util_bbdd/_core/exceptions.py` — jerarquía canónica (`DatabaseException` + derivadas)
- `src/util_bbdd/_foundation/` — módulo legacy con `exceptions.py`, `queries.py`, `validators_core.py`, `driver_validator.py`
- `src/util_bbdd/database_exceptions.py` — facade raíz con aliases históricos
- `src/util_bbdd/database_queries.py`, `database_type_validator.py`, `driver_validator.py` — facades raíz
- `src/util_bbdd/__init__.py` — exports públicos del paquete
- `src/util_bbdd/metadata/adapters/_adapter_protocol.py` — deprecated `SourceAdapter`/`RoutineAdapter`
- `pyproject.toml` — versión `0.6.7.dev0` al inicio
- `CHANGELOG.md` — sin entrada v0.6.7 al inicio

## Estado actual observado al inicio

- Tests: 1688 passed, 1 skipped (baseline)
- Ruff: limpio (excepto ficheros tocados en sesión)
- Mypy: 10 errores por stubs faltantes (pandas, networkx) — sin overrides configurados
- Versión activa: `0.6.7.dev0`
- `_foundation/` presente con 4 ficheros
- 4 facades raíz (`database_exceptions`, `database_queries`, `database_type_validator`, `driver_validator`)
- `SourceAdapter`/`RoutineAdapter` deprecated aliases aún presentes en `metadata/adapters/`

## Estado Git relevante

- Rama activa: develop
- Cambios locales pre-existentes: varios ficheros de la sesión anterior (alias cleanup refactor en curso)
- Último tag / versión publicada: v0.6.6

## Clasificación metodológica

- Tipo principal: tech_debt + refactor + version_closure
- Estado real de alcance: mezclado (assessment + deuda técnica + refactor breaking + cierre de versión)
- Consecuencia: ejecutar fases secuencialmente con decisiones explícitas del usuario antes de cada IMPLEMENT

## Gate G0 · Context Ready

Veredicto: GO_CONDICIONAL
Condiciones pendientes (si aplica):
- Decisión usuario sobre Option A vs Option B para `database_exceptions.py` (resuelta: Option A)
- Decisión usuario sobre eliminación de `_foundation/` (resuelta: eliminar íntegramente)
