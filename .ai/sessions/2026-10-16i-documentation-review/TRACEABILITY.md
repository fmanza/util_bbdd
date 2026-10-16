# TRACEABILITY

## Session metadata
- id: 2026-10-16i-documentation-review
- fecha: 2026-10-16
- rama: develop
- skill: documentation + config_review + version_closure
- fase: revisión (Documentation Reviewer: PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION) → IMPLEMENT por niveles →
  config_review (ANÁLISIS + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE) → VERSION

## Prompt issued
«Usa Documentation Reviewer (.github/agents/documentation-reviewer.agent.md) con
.github/prompts/documentation_review.prompt.md sobre src/util_bbdd. Solo lectura: no edites ficheros.» Después, por
turnos: aplicar el nivel 1, unificar ADR-004, nivel 2 (con la decisión «intermedia» para la documentación funcional),
`/config-review`, nivel 3, revisar lo no tocado y proponer, bloques A, D, B y C («Completo») y cierre.

## Context supplied
- `.github/agents/documentation-reviewer.agent.md`, `.github/prompts/documentation_review.prompt.md`
- `.github/DOCUMENTATION_STANDARD.md`, `.github/prompts/functional_doc.prompt.md`, `technical_doc.prompt.md`
- `.github/agents/config-reviewer.agent.md`, `.github/prompts/config_review.prompt.md`
- `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`,
  `.github/instructions/sync.instructions.md`
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`; memoria del proyecto (banco, JAVA_HOME, puerta sin URLs)

## AI output summary
- Revisión de solo lectura: `mkdocs.yml` sin páginas rotas ni huérfanas; 24 directivas autodoc resueltas; 11 ejemplos
  SQLite ejecutados en una copia; `mkdocs build --strict` fallaba (11 enlaces fuera de `docs_dir`). Veredicto `BLOCKED`.
- `384c1106` nivel 1: instalación `@v3.0.2`, enlaces del build, ADR-004 unificado (escapes decodificados), docstrings de
  la API de consultas de los managers.
- `f089d0e3` nivel 2: sintaxis 2.x retirada, docstrings (`SchemaSnapshot`, contratos, executors…), 5 páginas autodoc,
  test de humo de ejemplos, Documentation Reviewer remite a su prompt, estructura funcional de 5 secciones (bloque de
  dominio) y criterios en 4 páginas, 12 `@v1.1.0` restantes.
- Revertido a petición del usuario (sin commit): quitar los bloques `options:` de las páginas autodoc.
- `be6dfbc8`: criterios de aceptación en las 17 páginas funcionales restantes.
- `977c1400` `/config-review` (`APROBADO`): P1–P5 (precedencia del bloque de dominio, revisor coherente con sus `tools`,
  duplicación 0 %).
- `79dbd0af` nivel 3: `Examples:` en 60 secciones con doctest, migración a 3.0 en `index.md` y `troubleshooting.md`,
  §5 de `async_utils.md`.
- `f117c9ba` (A) y `493f9fc9` (D): `chunk_size` en troubleshooting, README «API pública», §2 técnica según la práctica.
- `cbd48cdd` (B): autodoc de `query`/`validators`/`results`, `analysis` y `factory`; `Args` en puntos de entrada;
  `validate_db_type_static` documenta `InvalidDatabaseType`; ejemplos de `QueryResolver` corregidos y ejecutados.
- `311dfe5b` (C): 6 ejemplos leen `UTIL_BBDD_EXAMPLE_*`; `tests/integration/test_docs_examples_engines.py` (8 passed
  contra el banco) y los 8 sin conexión en el test unitario.
- Validaciones finales: ruff y mypy (339 ficheros) limpios; `pytest` 6238 passed / 540 skipped sin banco y 6770 passed
  / 8 skipped con banco (HSQLDB con `JAVA_HOME`); `mkdocs build --strict` y `zensical build --strict` limpios.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Informe de revisión | conversación (PLAN, AUDIT_PLAN, AUDIT_CODE, VERSION) | emitido |
| Config review | conversación (ANÁLISIS, PLAN, AUDIT_PLAN, AUDIT_CODE) | aplicado (`977c1400`) |
| Autodoc nuevo | `docs/api/{migrate,doc,metadata,audit,connection,query,analysis}_autodoc.md` | completado |
| Test de ejemplos | `tests/unit/test_docs_examples.py`, `tests/integration/test_docs_examples_engines.py` | completado |
| Cierre | `CHANGELOG.md` [3.0.3], campos de versión, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`, `INDEX.md` | completado |

## Directrices para Futuras IAs
- **[docs/griffe]**: una sección `Example:` (singular) de un docstring Google es para griffe un aviso Markdown: el
  código `>>>` se publica como texto y unos corchetes en la salida (`[10]`) rompen `mkdocs build --strict` como
  referencia cruzada. Con `Examples:` se publica como bloque de código; sin doctest, usar ` ```python `.
- **[docs/griffe]**: al publicar un módulo en autodoc por primera vez, griffe exige `**kwargs` anotado si se documenta y
  una sección `Raises:` con excepción; esos avisos rompen el build estricto (`mkdocs build --strict`).
- **[docs/funcional]**: la estructura de 5 secciones de `docs/functional/` vive en la «Especialización de dominio» de
  `functional_doc.prompt.md`, no en su núcleo (compartido por bootstrap con otros proyectos; solo ese bloque es
  editable). El bloque traduce las §N del núcleo (§3, §5, §7, §8) y prevalece sobre «Restricciones» y «Output esperado».
- **[docs/técnica]**: las páginas de `docs/api/` titulan la §2 «Modelo de Datos / Contratos» y no llevan directivas
  `:::`; el autodoc va en `docs/api/*_autodoc.md` (sección «Autodoc (mkdocstrings)» de `mkdocs.yml`).
- **[docs/autodoc]**: las páginas autodoc usan bloques `options:` por directiva; el usuario rechazó moverlos a la
  configuración global de `mkdocs.yml` (aunque la vista previa del editor los muestre seguidos).
- **[docs/ejemplos]**: los ejemplos con servidor leen `UTIL_BBDD_EXAMPLE_URL` (o `…_SOURCE_URL`/`…_TARGET_URL` y
  `…_SCHEMA`) y sin ella explican cómo configurarla; convierten la URL a `conn_params` con `make_url` (la query añade
  parámetros: `service_name` en Oracle, `schema` en PostgreSQL). La librería no tiene esa conversión.
- **[tests/banco]**: en MariaDB y MySQL el usuario `bench` solo puede crear bases `zz_util_bbdd_%`
  (`docker-compose.bench.yml`); en Oracle, un usuario propio se crea con `UTIL_BBDD_TEST_ORACLE_ADMIN_URL` (SYSTEM).
- **[query]**: `sql_queries.json` empaquetado está vacío para todos los motores: los ejemplos de queries con nombre deben
  registrar la suya en un JSON (`QueryRegistry(Path(...))`); un nombre inventado da `QueryNotFoundError`.
- **[managers]**: `validate_db_type_static` lanza `InvalidDatabaseType` (`ValidationError`), no `ValueError`.
- **[herramientas]**: `grep -r` sobre `src` cuenta también los `.pyc` de `__pycache__` («Binary file … matches»):
  usar `--include=*.py` (un recuento de 127 secciones `Example:` eran 69).
- **[herramientas]**: `zensical build` no admite `-d`; para no escribir `site/` en el repo, copiar `docs/` y un
  `mkdocs.yml` con `paths` absolutos al scratchpad (exige `docs_dir` y `site_dir` dentro del proyecto).
- **[proceso]**: una observación del usuario no es una petición de cambio: explicar y proponer antes de editar.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- R4: tag `v3.0.3` y fast-forward de `main` (decisión del usuario); al etiquetar, valorar mover los `@v3.0.2` de las
  instrucciones de instalación.
- D4: fechas de ADR-004, verificar `onboarding_dev.md` para 3.0, páginas funcionales de `connection` y `factory`,
  docstrings de una línea sin `Args:`.
