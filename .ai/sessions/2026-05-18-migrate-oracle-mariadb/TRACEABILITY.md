# TRACEABILITY

## Session metadata
- id: 2026-05-18-migrate-oracle-mariadb
- fecha: 2026-05-18
- rama: develop
- skill: new_feature → tech_debt → audit_code → documentation
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + TECH_DEBT (quick_wins + fase_media) + AUDIT_CODE + VERSION

## Prompt issued
```
/new-feature

Objetivo: Crear módulo migrate/ para migración DDL Oracle→MariaDB

Alcance: src/util_bbdd/migrate/ (nuevo módulo completo)
         tests/unit/migrate/ (tests unitarios sin BD real)

Restricciones:
  - Reutilizar metadata/oracle/ sin duplicar queries
  - NUMBER sin precisión → DOUBLE
  - Tipos sin equivalente → propuesta A + comentario SQL (script ejecutable)
  - Charset MariaDB siempre requerido (utf8mb4 por defecto)
  - Script ejecutable + opción ejecución directa vía SyncDatabaseManager
  - Tests con IR fixtures (no requieren conexión real)
```
Seguido de:
```
/tech-debt revisa el nuevo módulo src\util_bbdd\migrate
IMPLEMENT
/audit-code (post-implement)
Aplicar condiciones opcionales
Actualizar charset.py para contemplar charset y collations en español
Generar documentación para el nuevo módulo
```

## Context supplied
- `src/util_bbdd/migrate/` — módulo nuevo (esta sesión lo crea)
- `src/util_bbdd/metadata/oracle/` — queries Oracle reutilizadas
- `src/util_bbdd/__init__.py` — para registrar exports públicos
- `docs/functional/schema-comparison.md` — referencia de formato documental
- `.github/prompts/functional_doc.prompt.md` y `technical_doc.prompt.md`
- `mkdocs.yml` — navegación existente

## AI output summary

### Fase new_feature — IMPLEMENT
1. Creado `src/util_bbdd/migrate/ir/models.py` — dataclasses IR: `CanonicalTable`, `CanonicalColumn`, `CanonicalFK`, `CanonicalIndex`, `MigrationWarning`, `MigrationPlan`
2. Creado `src/util_bbdd/migrate/_compat/type_map.py` — 30+ mapeos Oracle→MariaDB, `resolve_oracle_type`, `resolve_number_type`
3. Creado `src/util_bbdd/migrate/_compat/identifier_rules.py` — truncado hash MD5 para identificadores > 64 chars
4. Creado `src/util_bbdd/migrate/charset.py` — validación charset/collation con frozensets
5. Creado `src/util_bbdd/migrate/extractors/oracle.py` — `OracleSchemaExtractor` con queries RAW (preserva precision/scale)
6. Creado `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` — `OracleToMariaDBTransformer` con detección NEXTVAL
7. Creado `src/util_bbdd/migrate/emitters/mariadb.py` — `MariaDBDDLEmitter` con ordenación topológica Kahn y detección FKs circulares
8. Creado `src/util_bbdd/migrate/reporters/markdown.py` y `text.py` — reportes del plan
9. Creado `src/util_bbdd/migrate/planner.py` — `MigrationPlanner` orquestador principal
10. Creado `src/util_bbdd/migrate/__init__.py` — exports del módulo
11. Modificado `src/util_bbdd/__init__.py` — añadidos `MigrationPlanner`, `MigrationPlan`, `MigrationWarning`
12. Creados 78 tests en `tests/unit/migrate/` (4 ficheros): type_map, identifier_rules, transformer, emitter, planner
13. Ejecutados ruff + mypy + pytest: 0 errores, 78 tests verdes

### Fase tech_debt — AUDIT + IMPLEMENT (10 quick_wins + 3 fase_media)
14. Eliminado dead code: `_NEXTVAL_RE`, `_SEQUENCE_NAME_RE`, `_detect_sequence`, `import re` en `extractors/oracle.py`
15. Corregido `TypeMapping.severity`: `str` → `WarningSeverity`; `proposals = field(default_factory=tuple)` → `= ()`; importado `WarningSeverity` desde `ir.models`
16. Eliminados 2× `# type: ignore[arg-type]` en transformer (cascada de la corrección anterior)
17. Eliminado `NCLOB` de `_NVARCHAR_CHARSETS` (dead code; rama `_LOB_UTF8` lo cubre primero)
18. Eliminado `"_detect_sequence"` de `__all__` en transformer
19. Renombrado `MigrationPlan._emitter` → `.emitter`; `target_connection: object` → `Any`; eliminado `type: ignore`
20. Eliminado `IncompatibleTypeStrategy` de `__all__` en planner
21. Eliminado parámetro `target_type` sin uso de `_format_default`
22. Refactorizado `_emit_create_table`: separar comment_lines de ddl_lines → DDL válido para casos mixtos
23. Añadido guard en `_emit_create_table` para tabla sin columnas activas → sentinel `-- ERROR:`
24. Añadido filtrado en `_emit_indexes`: excluir índices sobre columnas omitidas
25. Ampliado allowlist en `_format_default`: añadidos `SYSDATE`, `SYSTIMESTAMP`, `SYS_GUID()`, `USER`
26. Añadidos 4 tests nuevos en `test_emitter.py`; total 82 tests verdes

### Fase audit_code
27. Veredicto: **APROBADO CON CONDICIONES** (2 condiciones opcionales menores)
28. Aplicadas condiciones: `IncompatibleTypeStrategy` eliminado del cuerpo de `planner.py`; assertion `"ERROR"` → `"sin columnas activas"` en test

### charset.py — collations español
29. Añadidas 6 collations: `utf8mb4_spanish2_ci`, `utf8mb4_spanish_ci`, `utf8mb4_unicode_520_ci`, `utf8_spanish2_ci`, `utf8_spanish_ci`, `latin1_spanish_ci`

### Documentación
30. Creado `docs/functional/migrate-oracle-mariadb.md` — objetivo negocio, precondiciones, `sequenceDiagram`, 8 reglas de negocio, ejemplo, límites
31. Creado `docs/api/migrate-oracle-mariadb.md` — responsabilidad, `sequenceDiagram` capas, API pública completa, contratos, errores, ejemplo técnico
32. Creado `docs/examples/migrate-oracle-mariadb.md` — 4 casos de uso verificables (script a disco, ejecución directa, reporte Markdown, NUMBER→DECIMAL)
33. Actualizado `mkdocs.yml`: 3 entradas de navegación en secciones Funcional, Técnica y Ejemplos
34. Corregido bug preexistente: `site_description` sin comillas causaba fallo en `mkdocs build`; verificado build exitoso

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IR models | `src/util_bbdd/migrate/ir/models.py` | creado |
| Type map | `src/util_bbdd/migrate/_compat/type_map.py` | creado |
| Identifier rules | `src/util_bbdd/migrate/_compat/identifier_rules.py` | creado |
| Charset validation | `src/util_bbdd/migrate/charset.py` | creado + ampliado (español) |
| Extractor Oracle | `src/util_bbdd/migrate/extractors/oracle.py` | creado |
| Transformer | `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` | creado |
| Emitter MariaDB | `src/util_bbdd/migrate/emitters/mariadb.py` | creado |
| Reporters | `src/util_bbdd/migrate/reporters/markdown.py`, `text.py` | creados |
| Planner | `src/util_bbdd/migrate/planner.py` | creado |
| Module init | `src/util_bbdd/migrate/__init__.py` | creado |
| Package init | `src/util_bbdd/__init__.py` | modificado |
| Tests (82) | `tests/unit/migrate/` (4 ficheros) | creados |
| Doc funcional | `docs/functional/migrate-oracle-mariadb.md` | creado |
| Doc técnica | `docs/api/migrate-oracle-mariadb.md` | creado |
| Ejemplo | `docs/examples/migrate-oracle-mariadb.md` | creado |
| Navegación | `mkdocs.yml` | modificado |
| Sesión | `.ai/sessions/2026-05-18-migrate-oracle-mariadb/` | completado |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Tech-debt resuelto, audit aprobado, condiciones aplicadas, docs publicadas, build mkdocs limpio.
