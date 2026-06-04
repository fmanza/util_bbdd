# TRACEABILITY

## Session metadata
- id: 2026-06-04-mariadb-default-collation-uca1400
- fecha: 2026-06-04
- rama: develop
- skill: hotfix (cambio de valor por defecto)
- fase: PROMPT + IMPLEMENT + DOCS + TRACEABILITY

## Prompt issued
> Cambiar en src\util_bbdd\migrate los valores por defecto para MariaDB de:
> Charset: utf8mb4
> Collation: utf8mb4_uca1400_ai_ci
>
> (seguimiento) Actualizar .ai\sessions y preparar mensaje para subir código a GitHub.

## Context supplied
- CLAUDE.md + `.github/SHARED_INSTRUCTIONS.md` (instrucciones de proyecto).
- `src/util_bbdd/migrate/charset.py` (constantes y validación de charset/collation).
- `src/util_bbdd/migrate/__init__.py` (docstrings con ejemplos de uso).
- Documentación: README.md, docs/DDL_MIGRATION_GUIDE.md, docs/examples/*.

## AI output summary
- Localizadas las definiciones de charset/collation por defecto en `migrate/charset.py`.
- `DEFAULT_COLLATION`: `utf8mb4_unicode_ci` → `utf8mb4_uca1400_ai_ci`. `DEFAULT_CHARSET`
  permanece `utf8mb4`.
- Añadida `utf8mb4_uca1400_ai_ci` a `VALID_COLLATIONS` y a
  `CHARSET_COLLATION_MAP["utf8mb4"]` para que el nuevo default supere la validación.
- Actualizados los ejemplos de docstring en `migrate/__init__.py` (3 ocurrencias
  `collation=`) al nuevo default.
- Documentación actualizada (nuevo default + nota "requiere MariaDB ≥ 10.10"):
  README.md, docs/DDL_MIGRATION_GUIDE.md, docs/examples/migrate-postgresql-source.py,
  docs/examples/migrate-sqlserver-source.md.
- Tests: `pytest tests -k "charset or migrate"` → 1346 passed, 2481 deselected.
- Creada trazabilidad de sesión + entrada en INDEX.md + GITHUB_COMMIT_MESSAGE.md.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT (código) | `src/util_bbdd/migrate/charset.py` | completado |
| IMPLEMENT (docstrings) | `src/util_bbdd/migrate/__init__.py` | completado |
| DOCS | `README.md`, `docs/DDL_MIGRATION_GUIDE.md`, `docs/examples/migrate-postgresql-source.py`, `docs/examples/migrate-sqlserver-source.md` | completado |
| REQUEST | `.ai/sessions/2026-06-04-mariadb-default-collation-uca1400/00_REQUEST.md` | emitido |
| CONTEXT | `.ai/sessions/2026-06-04-mariadb-default-collation-uca1400/00_CONTEXT_SNAPSHOT.md` | emitido |
| TRACEABILITY | `.ai/sessions/2026-06-04-mariadb-default-collation-uca1400/TRACEABILITY.md` | emitido |
| COMMIT MSG | `.ai/sessions/2026-06-04-mariadb-default-collation-uca1400/GITHUB_COMMIT_MESSAGE.md` | emitido |

## Directrices para Futuras IAs
- **migrate/charset**: el default por defecto es `utf8mb4` + `utf8mb4_uca1400_ai_ci`.
  Cualquier nuevo default DEBE estar presente en `VALID_COLLATIONS` y en
  `CHARSET_COLLATION_MAP[charset]`, o `MigrationPlanner()` lanzará `ValueError` al
  construirse con valores por defecto.
- **Compatibilidad**: `utf8mb4_uca1400_ai_ci` requiere MariaDB ≥ 10.10. Para destinos
  MariaDB < 10.10 o MySQL hay que pasar `collation=` explícito (p.ej. `utf8mb4_unicode_ci`,
  que sigue siendo válido).
- **Tests**: varios tests en `tests/unit/migrate/` siguen usando `utf8mb4_unicode_ci`
  como entrada explícita — es intencionado (sigue siendo collation válida); no es necesario
  migrarlos al nuevo default.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- CHANGELOG.md: ✅ entrada añadida en [Unreleased] › Changed con aviso de cambio de
  comportamiento (potencialmente breaking para MariaDB < 10.10).
- (Decisión usuario) `.claude/settings.json` aparece modificado en el working tree (config
  local de hooks/permissions, ajena a este cambio): decidir si se incluye o se excluye del commit.
