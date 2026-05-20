# SESSION INDEX

Inventario de sesiones de trabajo controlado en `.ai/sessions/`.
Cada sesión sigue la estructura de artefactos definida en `TEMPLATE/`.

## Convención de nomenclatura
```
.ai/sessions/YYYY-MM-DD/
  00_REQUEST.md           ← solicitud saneada y restricciones
  00_CONTEXT_SNAPSHOT.md  ← estado del repo y Gate G0
  NN_<FASE>.md            ← artefactos por fase (PLAN, IMPLEMENT, etc.)
  TRACEABILITY.md         ← resumen de lo ejecutado y veredicto final
```

## Sesiones

| Fecha       | Objetivo breve                                      | Rama                  | Skill          | Estado   | Trazabilidad                          |
|-------------|-----------------------------------------------------|-----------------------|----------------|----------|---------------------------------------|
| 2026-03-22  | Refactorización v0.6.0: relaciones N niveles        | develop → main (v0.6.0) | refactor     | CLOSED   | `2026-03-22/REFACTOR_v0.6.0_SESSION.md` |
| 2026-03-24  | Aplicar metodología IA + primera slice v0.6.1 HTML  | develop               | new_feature    | CLOSED   | `2026-03-24/TRACEABILITY.md`          |
| 2026-03-25  | Aplicar metodología IA + features v0.6.2            | develop               | new_feature    | CLOSED   | `2026-03-25/TRACEABILITY.md`          |
| 2026-04-10  | v0.6.7: maturity assessment + tech-debt _foundation/ + refactor facades legacy + version closure | develop | tech-debt / refactor / version-closure | CLOSED | `2026-04-10/TRACEABILITY.md` |
| 2026-04-13  | audit-code: identificar duplicación `_core/capabilities.py` vs `core/capabilities.py`             | develop | audit-code                             | CLOSED      | `2026-04-13/TRACEABILITY.md` |
| 2026-04-13b | tech-debt: gaps multimotor en `comparar/` (Fases 0-3: D6+D3, D2+D5, D1+D4, M1+M2) — **Completada exitosamente** | develop | tech-debt                              | CLOSED      | `2026-04-13-comparar/` → PLAN+AUDIT_PLAN+IMPLEMENT+AUDIT_CODE+VERSION (0-3) |
| 2026-04-13c | version-closure: v0.6.7 final release — actualizar README.md arquitectura, preparar subida a GitHub | develop → main (v0.6.7) | version-closure | CLOSED | `2026-04-13/v0.6.7-version-closure-2026-04-13.md` |
| 2026-04-13d | **IN_PROGRESS**: v0.6.8-dev initialization — Phase 4 L1/L2/L3 optimizations planned | develop | new_feature / tech-debt | IN_PROGRESS | `2026-04-13-v0.6.8/` (TBD) |
| 2026-04-14  | new_feature: reporters de SchemaDiff — HTML (Jinja2+Mermaid), Excel (openpyxl), Word (docx), Markdown (Mermaid) en `comparar/reporters/` | develop | new_feature | CLOSED | `2026-04-14/TRACEABILITY.md` |
| 2026-04-15  | refactor: OOP exclusivo en reporters (funciones→@staticmethod/ClassVar); docs política OOP en CLAUDE.md + copilot-instructions + python.instructions | develop | refactor | CLOSED | en sesión |
| 2026-04-15b | new_feature: HTML filtrado interactivo 5 categorías sin Jinja2 (html.escape stdlib); Word compactado sin párrafos vacíos (paragraph_format spacing) | develop | new_feature | CLOSED | en sesión |
| 2026-04-15c | refactor: HTML restaura Jinja2 + búsqueda de texto (controls-bar); Word aplica Heading 1 a las 5 categorías (Tablas añadidas/eliminadas/modificadas, Vistas, Rutinas) | develop | refactor | CLOSED | en sesión |
| 2026-04-15d | new_feature: SqlDiffReporter — script SQL de nivelación dialect-específico (7 dialectos) integrado en SchemaDiffReporter como formato "sql"; 56 tests verdes | develop | new_feature | CLOSED | en sesión |
| 2026-04-15e | new_feature: SqlDiffReporter con source_inspector — CREATE TABLE completo + ADD COLUMN tipo_real; corrección gap semántico "exists"/"missing"; SchemaDiffReporter +sql_source_inspector; 72 tests verdes | develop | new_feature | CLOSED | en sesión |
| 2026-04-16  | new_feature: SqlDiffReporter gaps — CommentDiff (COMMENT ON/ALTER TABLE COMMENT/placeholder); CREATE TABLE completo con FK inline + CREATE INDEX post-tabla; nullable/DEFAULT dialect-aware (MODIFY COLUMN para mariadb/mysql/oracle); 102 tests verdes | develop | new_feature | CLOSED | en sesión |
| 2026-04-16b | new_feature: HTML diff reporter — diagrama de diferencias tabbed (Añadidas/Modificadas/Eliminadas) con paginación Mermaid lazy (máx. 9 tablas/bloque); ARIA completo; CDN mermaid@10; 1878 tests verdes | develop | new_feature | CLOSED | `2026-04-16/TRACEABILITY.md` |
| 2026-04-16c | refactor: layout 3 columnas en diagramas Mermaid — invisible links ~~~; fix bug loop.index con None padding (reject("none")); 1878 tests verdes | develop | refactor | CLOSED | en sesión |
| 2026-04-16d | **refactor: excepciones en comparar/** — reemplazar ValueError/Exception genéricas por ComparerError + 3 subclases (SchemaDiffValidationError, MetadataIntrospectionError, DiffReportGenerationError); 4 nuevas excepciones, 6 tests actualizados; 1878 tests verdes ✅ COMPLETADA | develop | refactor | CLOSED | `2026-04-16-comparar-exceptions/TRACEABILITY.md` |
| 2026-04-18-tech-debt-logging | **tech-debt: logging typed annotations Phases 1-4B** — añadir `self.logger: logging.Logger` a 36 clases; release v0.6.8 | develop | tech-debt | CLOSED | `2026-04-18-tech-debt-logging/TRACEABILITY.md` |
| 2026-04-18-phase4b | **tech-debt Phase 4B** — logging completado en managers, metadata, comparar | develop | tech-debt | CLOSED | `2026-04-18-phase4b/01_PHASE_4B_COMPLETE.md` |
| 2026-04-20-fase3-managers | **refactor: Fase 3 consolidación managers/** — MetadataRequestBuilder, CharsetCollationParser, DDLNormalizer (v0.6.9) | develop | refactor | IN_PROGRESS | `2026-04-20-fase3-managers/TRACEABILITY.md` |
| 2026-04-20-reorganizacion-docs | **chore: reorganización .ai/sessions y docs/** — archivar docs/plan/, normalizar sesiones sueltas, mover FASE3_MIGRATION_NOTES a sesión | develop | chore | CLOSED | en sesión |
| 2026-04-21-refactor-legacy-cleanup | **refactor: eliminación completa de legacy** — 31 funciones wrapper deprecated eliminadas de 5 módulos managers/; 6 consumidores migrados a OOP directo; `DatabaseQueries.queries` property eliminada; MariaDB charset/collation gap corregido en `CharsetCollationParser`; 1881 tests verdes | develop | refactor | CLOSED | `2026-04-21-refactor-legacy-cleanup/TRACEABILITY.md` |
| 2026-04-21-tech-debt-comparar-doc | **tech-debt: inventario comparar/ + doc/** — 21 ítems (15 comparar/, 6 doc/); 2 bugs activos (C13 doble `;`, C15 routines modified); veredicto DEUDA_SIGNIFICATIVA; plan Fases 1-3 para v0.8.1 | develop | tech-debt | CLOSED | `2026-04-21-tech-debt-comparar-doc/TRACEABILITY.md` |
| 2026-04-21-fase3-estructural | **refactor: Fase 3 estructural comparar/ + doc/** — C3 RoutineFetcherRegistry, C9 DdlNormalizer unificado, D1 generate() explícito, D4 Port circular, D5 ports split; 1969 passed, mypy+ruff clean | develop | refactor | CLOSED | `2026-04-21-fase3-estructural/TRACEABILITY.md` |
| 2026-05-02 | **Documentation Generation Fases 1-6** — SyncDatabaseManager módulo piloto; documentación funcional + técnica + ejemplos verificables; mkdocs sync; auditoría APROBADA (100% referencias validadas, 0 módulos inventados) | develop | new_feature (documentation) | CLOSED | `2026-05-02/TRACEABILITY.md` |
| 2026-05-14 | **config_review: corrección instrucciones IA** — 7 referencias `project_copy` eliminadas; Python `>=3.11`→`>=3.12`; `sync.instructions.md` creado (referencia rota); 3 slash commands añadidos a CLAUDE.md | develop | config_review | CLOSED | `2026-05-14/TRACEABILITY.md` |
| 2026-05-14-docs-audit | **docs-audit: implementación 11 hallazgos Documentation Reviewer** — extras pip reales en INSTALLATION.md; ejemplo API real en example-connect-introspect.md; arquitectura real en SHARED_INSTRUCTIONS.md; versión 0.7.0→0.8.0; jerarquía excepciones corregida; cx_Oracle→oracledb; módulos results/async_utils/capabilities documentados; páginas huérfanas excluidas en mkdocs.yml; URLs rotas y versión actual en legacy-versions.md | develop | maturity_assessment | CLOSED | `2026-05-14-docs-audit/TRACEABILITY.md` |
| 2026-05-18-migrate-oracle-mariadb | **new_feature: módulo migrate/ DDL Oracle→MariaDB** — pipeline 3 capas (extractor/transformer/emitter), 30+ tipos mapeados, secuencias→AUTO_INCREMENT, FK circulares, ordenación topológica; tech-debt: 10 quick-wins + 3 fase_media; charset español; 82 tests; 3 páginas docs; mkdocs build limpio | develop | new_feature + tech_debt + audit_code + documentation | CLOSED | `2026-05-18-migrate-oracle-mariadb/TRACEABILITY.md` |
| 2026-05-19-migrate-refactor | **refactor: migrate/ tras primera ejecución producción** — INT(11) display width configurable (`int_display_width`); FK externas → ALTER TABLE al final con comentario (antes omitidas); PK única entera → AUTO_INCREMENT automático; 12 tests nuevos (94 migrate, 2072 total) | develop | refactor | CLOSED | `2026-05-19-migrate-refactor/TRACEABILITY.md` |
| 2026-05-19b-reporters-refactor | **refactor: reducción complejidad cognitiva reporters** — `markdown.py` 25→≤2 (4 helpers extraídos); `text.py` 22→≤2 (3 helpers + 2 constantes); API pública sin cambios; 94 tests verdes | develop | refactor | CLOSED | `2026-05-19b-reporters-refactor/TRACEABILITY.md` |
| 2026-05-19c-emitter-refactor | **refactor: `_topological_sort` complejidad 29→0** — extraídos `_build_deps`, `_kahn_result`, `_collect_circular_fk_pairs`; cada helper ≤ 10; comportamiento y tests intactos (94 verdes) | develop | refactor | CLOSED | `2026-05-19c-emitter-refactor/TRACEABILITY.md` |
| 2026-05-19d-docs-audit-migrate | **docs-audit: revisión documental módulo migrate/** — 2 hallazgos L1 cerrados (README sin mención, re-export verificado); 5 L2 aplicados (reglas negocio PK→AI + NUMBER>18→DECIMAL, docstrings int_display_width + propiedades + emit); typo "perda"→"pérdida" en DDL generado | develop | documentation_review | CLOSED | `2026-05-19d-docs-audit-migrate/TRACEABILITY.md` |
| 2026-05-19e-hotfix-number-pk | **hotfix: NUMBER sin precisión en PK → INT** *(SUPERSEDED por 2026-05-19f)* — fix frágil basado en `col.is_primary_key`; solo funcionaba vía `OracleSchemaExtractor` | develop | hotfix | SUPERSEDED | `2026-05-19e-hotfix-number-pk/TRACEABILITY.md` |
| 2026-05-19f-hotfix-number-pk-v2 | **hotfix v2: NUMBER PK → INT via `_handle_pk_auto_increment`** *(SUPERSEDED por 2026-05-19g)* — fix correcto en teoría pero insuficiente en producción por orden de iteración | develop | hotfix | SUPERSEDED | `2026-05-19f-hotfix-number-pk-v2/TRACEABILITY.md` |
| 2026-05-19g-hotfix-number-pk-v3 | **hotfix v3 DEFINITIVO: NUMBER PK → INT(11) AUTO_INCREMENT** — normalización `is_primary_key` en `new_table.columns` ANTES de transformar + iteración sobre copia profunda + check PK en `_transform_column`; validado con caso real `ACM_INTEGRACION`; 100 tests verdes | develop | hotfix | CLOSED | `2026-05-19g-hotfix-number-pk-v3/TRACEABILITY.md` |
| 2026-05-19h-ci-private-dep | **ci: credenciales git para dependencia privada fmanza/util** — `git config --global url.insteadOf` con `GH_PAT` antes de cada `pip install` en `tests.yml` (jobs test+package) y `docs.yml` (jobs build+deploy); requiere secret `GH_PAT` en repo | develop | hotfix | CLOSED | en sesión |

| 2026-05-20-migrate-oracle-sqlserver | **new_feature: módulo migrate/ Oracle → SQL Server** — `OracleToSQLServerTransformer` + `SQLServerDDLEmitter` + `TypeMappingSQLServer` (30+ tipos), IDENTITY(1,1), COLLATE columna opcional, FK circular/externa; `MigrationPlanner` soporta `target_engine="sqlserver"`; backward compat Oracle→MariaDB 100%; 113 tests nuevos (213 migrate, 2191 total) | develop | new_feature | CLOSED | `2026-05-20-migrate-oracle-sqlserver/TRACEABILITY.md` |
| 2026-05-20-migrate-oracle-postgresql | **new_feature: módulo migrate/ Oracle → PostgreSQL** — `OracleToPostgreSQLTransformer` + `PostgreSQLDDLEmitter` + `TypeMappingPostgreSQL` (30+ tipos), SERIAL/BIGSERIAL/SMALLSERIAL, `SET search_path`, FK circular/externa; `MigrationPlanner` soporta `target_engine="postgresql"` con `pg_schema`; 122 tests nuevos (335 migrate, 2313 total) | develop | new_feature | CLOSED | `2026-05-20-migrate-oracle-postgresql/TRACEABILITY.md` |
| 2026-05-20-migrate-views | **new_feature + feat: soporte de vistas Oracle → 3 targets + ordenación topológica** — `CanonicalView` IR, `rewrite_oracle_view()` best-effort (NVL/SYSDATE/DUAL/hints/schema prefix; ROWNUM/CONNECT BY/DECODE/LISTAGG→WARNING), `extract_views()` extractor, `transform_views()` en 3 transformers, `_emit_create_view()` en 3 emitters, `MigrationPlan.views`; `_topological_sort_views()` + `_detect_view_deps()` (Kahn); vistas circulares con AVISO; 93 tests nuevos (428 migrate, 2406 total) | develop | new_feature | CLOSED | `2026-05-20-migrate-views/TRACEABILITY.md` |
| 2026-05-20-migrate-mariadb-source | **new_feature: módulo migrate/ MariaDB → Oracle / SQL Server / PostgreSQL** — `MariaDBSchemaExtractor` (INFORMATION_SCHEMA), 3 type maps, 3 transformers (id. truncados 30/128/63), `OracleDDLEmitter` (double-quoted uppercase, SEQUENCE+TRIGGER, COMMENT ON, topological sort), `MigrationPlanner` soporta `source_engine="mariadb"` + `target_engine="oracle"`; vistas v1 pass-through; 177 tests nuevos (605 migrate, 2583 total) | develop | new_feature | CLOSED | `2026-05-20-migrate-mariadb-source/TRACEABILITY.md` |
| 2026-05-21-migrate-sqlserver-source | **new_feature: módulo migrate/ SQL Server → Oracle / MariaDB / PostgreSQL** — `SQLServerSchemaExtractor` (INFORMATION_SCHEMA + sys.*), IDENTITY via COLUMNPROPERTY, char_length=-1 sentinel para MAX; 3 type maps (25+ tipos/target), 3 transformers (id. truncados 30/64/63), `MigrationPlanner` soporta `source_engine="sqlserver"`; completa matriz 3×3 (9 flujos); vistas v1 pass-through T-SQL; ~184 tests nuevos (~789 migrate, ~2767 total) | develop | new_feature | CLOSED | `2026-05-21-migrate-sqlserver-source/TRACEABILITY.md` |

## Crear nueva sesión

1. Copia `TEMPLATE/` con nombre `YYYY-MM-DD/`.
2. Rellena `00_REQUEST.md` antes de invocar cualquier agente.
3. Rellena `00_CONTEXT_SNAPSHOT.md` y obtén veredicto Gate G0.
4. Añade esta sesión al índice anterior con estado `IN_PROGRESS`.
5. Al cerrar, actualiza el estado a `CLOSED` y completa `TRACEABILITY.md`.

## Estados válidos
| Estado       | Significado                                        |
|--------------|----------------------------------------------------|
| `IN_PROGRESS`| Sesión activa; al menos una fase en ejecución      |
| `CLOSED`     | Sesión cerrada con trazabilidad completa            |
| `ABANDONED`  | Sesión interrumpida; puede tener artefactos parciales |
