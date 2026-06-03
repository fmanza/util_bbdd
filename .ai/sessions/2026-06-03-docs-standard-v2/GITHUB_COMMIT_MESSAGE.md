# Mensaje para Commit y Push a GitHub

## Commit Message (Conventional Commits)

```
docs: estándar documental v2 (5 arquetipos × 5 secciones) + fix cobertura autodoc bulk/dump

Homogeniza toda la documentación pública al estándar v2 y corrige dos gaps
de cobertura de autodoc (mkdocstrings). Sin cambios de código de funcionalidad.

### Estándar v2: 5 arquetipos × 5 secciones

- Arquetipo 1 (Funcional): +§4 Criterios de Aceptación (POSPUESTO — pendiente
  validación QA, solo placeholder) y +§5 Glosario; 19 archivos en docs/functional/.
- Arquetipo 2 (Técnica): +§5 Ejemplos Relacionados (enlace bidireccional);
  24 archivos en docs/api/.
- Arquetipo 3 (Guías): +§1 Objetivo, renumeración §1→§5 y §5 Variantes y
  Solución de Problemas; 13 guías en docs/.
- Arquetipo 4 (Ejemplos): +§5 Referencias Relacionadas (enlace bidireccional
  a functional/ y api/); 18 archivos en docs/examples/.
- Arquetipo 5 (Arquitectura): nuevo arquetipo ADR; docs/adr/ADR-001 restructurado
  + nueva plantilla docs/adr/ADR-TEMPLATE.md.

### Navegación: 7 secciones top-level exactas

- mkdocs.yml consolidado de 9 a 7 secciones: Inicio, Instalación, Documentación
  Funcional, Referencia Técnica, Guías, Ejemplos, Arquitectura.
- "Roadmap & Planificación" y "Versiones Históricas" reubicadas bajo Arquitectura.
- API_REFERENCE.md reemplazado por api/intro.md (índice de Referencia Técnica);
  API_REFERENCE.md añadido a exclude_docs.

### Reubicación de guías de herramientas IA

- 4 guías movidas de docs/examples/ a docs/ raíz (eran guías Arquetipo 3, no ejemplos):
  - claude_code_usage_complete_example.md → claude_code_guide.md
  - codex_usage_complete_example.md → codex_guide.md
  - doc_generation_vscode_guide.md → doc_generation_vscode_guide.md (raíz)
  - github_usage_complete_example.md → github_copilot_guide.md
- Resuelve 99 warnings de links rotos a .github/ que abortaban el build estricto.

### Fix cobertura autodoc (mkdocstrings)

- bulk.md: la directiva apuntaba al alias de variable `bulk_crud` (= BulkCrud).
  mkdocstrings trata los aliases de variable como escalares y no expande los
  métodos de la clase. Corregido a la clase real BulkCrud; añadidas directivas
  para ParallelBulkLoader, AuditManager y AuditTransaction.
- dump: el módulo NO tenía ningún archivo autodoc en la sección Autodoc; sus
  docstrings nunca se renderizaban. Creado api/dump-autodoc.md con 11 clases
  públicas (DumpOrchestrator, DumpConfig, DumpResult, DumpReporter,
  ConstraintManager, ConstraintResult, IndexManager, IndexActionResult,
  DumpAuditSummary, TableDumpResult, BulkInserter). PKSyncResult excluido por
  ser re-export de bulk._models, ya cubierto en bulk.md.

### Instrucciones IA (gobernanza)

- .github/instructions/docs.instructions.md: 5 arquetipos × 5 secciones,
  detección de lenguaje multi-lenguaje (Python/Java/TypeScript), regla crítica
  de aliases de autodoc y regla de cobertura "cada módulo público necesita un
  archivo autodoc".
- .github/DOCUMENTATION_STANDARD.md: §3.1–§3.5 (5 arquetipos) + §3.6 multi-lenguaje.
- Prompts actualizados: functional_doc, technical_doc, guide_doc, example_doc.
- Nuevo prompt: .github/prompts/architecture_doc.prompt.md (Arquetipo 5 ADR).

### Ejemplos ejecutables

- 7 nuevos .py de ejemplo verificados con python -m py_compile:
  example-connect-introspect, query_execution_example, dump_data_export,
  migrate-{oracle-mariadb,mariadb-source,postgresql-source,sqlserver-source}.

### Trazabilidad

- .ai/sessions/2026-06-03-docs-standard-v2/ (REQUEST, CONTEXT_SNAPSHOT,
  TRACEABILITY) + entrada en .ai/sessions/INDEX.md.

### Validación

- mkdocs build --strict: 0 errores, 0 warnings.
- Nav verificado: 7 secciones top-level.
- Cobertura verificada: 24 api con §5, 18 examples con §5, 13 guías con §1.
- Decisiones del AUDIT_PLAN: C1 (criterios QA) POSPUESTO; C6 (anchors) verificado
  sin referencias rotas antes de renumerar.
```

---

## Comandos sugeridos (NO ejecutados — requieren confirmación del usuario)

> Estás en la rama `develop` (no es la rama por defecto `main`), por lo que se
> puede commitear directamente. Revisa los puntos de decisión antes de ejecutar.

```bash
# 1. Revisar qué se va a incluir
git status

# 2. Añadir documentación e instrucciones IA (NO incluye .cursorrules — ver nota)
git add docs/ mkdocs.yml \
        .github/DOCUMENTATION_STANDARD.md \
        .github/instructions/docs.instructions.md \
        .github/prompts/ \
        .ai/sessions/

# 3. Commit (el mensaje completo está arriba)
git commit -F .ai/sessions/2026-06-03-docs-standard-v2/GITHUB_COMMIT_MESSAGE.md
# (o pegar el bloque de Conventional Commits manualmente)

# 4. Push
git push origin develop
```

---

## Puntos de decisión antes de subir

1. **`.cursorrules` (untracked)**: NO fue creado en esta sesión — es un archivo
   tuyo de configuración de Cursor. NO está incluido en el `git add` sugerido.
   Decide si quieres versionarlo aparte.

2. **Trabajo de sesiones previas sin commitear**: el árbol de trabajo arrastra
   documentación creada en sesiones anteriores que nunca se commiteó:
   `docs/api/normalize.md`, `docs/api/dump-reporter.md`,
   `docs/examples/parallel_bulk_insert.{md,py}`, `docs/examples/database/`,
   `docs/functional/bulk-parallel-loading.md`. Quedan bundleados en este commit
   porque forman parte del estado documental coherente actual.

3. **Tamaño del commit (~107 archivos)**: si prefieres un historial más granular,
   se puede dividir en 3 commits:
   - `docs: estándar v2 + nav 7 secciones` (arquetipos + mkdocs.yml + instrucciones IA)
   - `docs(api): fix cobertura autodoc bulk y dump`
   - `chore(sessions): trazabilidad 2026-06-03-docs-standard-v2`

4. **Sin tag de versión**: este commit es solo documentación; no requiere bump
   de versión en `pyproject.toml` (sigue en 0.10.0).
