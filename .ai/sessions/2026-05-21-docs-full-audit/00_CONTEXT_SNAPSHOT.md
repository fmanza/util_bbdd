# CONTEXT SNAPSHOT

## Contexto del repositorio revisado

- `.github/SHARED_INSTRUCTIONS.md` — arquitectura, capacidades, motores soportados
- `.github/DOCUMENTATION_STANDARD.md` — estándar de documentación, nav de referencia
- `.github/prompts/functional_doc.prompt.md` — criterios para doc funcional
- `.github/prompts/technical_doc.prompt.md` — criterios para doc técnica
- `CLAUDE.md` — instrucciones Claude Code, slash commands
- `mkdocs.yml` — navegación activa y configuración del sitio
- `src/util_bbdd/__init__.py` — API pública exportada
- `src/util_bbdd/migrate/__init__.py` — API pública + docstring con todos los flujos soportados
- `src/util_bbdd/migrate/planner.py` — `MigrationPlanner.__init__` (parámetros completos)
- `src/util_bbdd/migrate/transformers/oracle_to_*.py` (×3) — transformers Oracle
- `src/util_bbdd/migrate/transformers/mariadb_to_*.py` (×3) — transformers MariaDB
- `src/util_bbdd/migrate/emitters/*.py` (×4) — emitters MariaDB/Oracle/SS/PG
- `docs/functional/migrate-oracle-mariadb.md` — doc funcional pre-sesión (desactualizada)
- `docs/api/migrate-oracle-mariadb.md` — doc técnica pre-sesión (desactualizada)
- `docs/examples/migrate-oracle-mariadb.md` — ejemplo pre-sesión (solo Oracle→MariaDB)
- Sesiones de referencia: `2026-05-20-migrate-mariadb-source/`, `2026-05-21-migrate-postgresql-source/`

## Estado actual observado

- Tests: 3058 passed (últimas sesiones — sin cambios de código en esta sesión)
- Lint / mypy: clean (no se tocan ficheros fuente)
- Documentación del módulo `migrate/`: **parcialmente desactualizada** — Oracle→MariaDB documentado, pero Oracle→SS/PG y MariaDB como fuente sin documentación pública
- `DOCUMENTATION_STANDARD.md §4.2`: referenciaba módulos de otro proyecto (file-system, generators)

## Estado Git relevante

- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último commit: `refactor(metadata): tech-debt B-01...B-05 + D-01...D-05`

## Clasificación metodológica

- Tipo principal: documentation (maturity_assessment)
- Estado real de alcance: acotado — solo docs, sin tocar código fuente
- Consecuencia: proceder directamente con las 6 fases

## Gate G0 · Context Ready

Veredicto: GO
Condiciones pendientes:
- Ninguna
