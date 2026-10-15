# TRACEABILITY

## Session metadata
- id: 2026-10-15-engine-conditions-doc
- fecha: 2026-10-15
- rama: develop
- skill: audit_code → new_feature
- fase: audit_code (PLAN + AUDIT_PLAN + AUDIT_CODE) sobre `doc/audit/`; new_feature (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)

## Prompt issued
Auditar el código generado en otra sesión (`src/util_bbdd/doc/audit/{__init__,adapters,audit_documentation,domain_models}.py`)
cuyo objetivo era mostrar en `doc/` la auditoría de `connection/performance_advisor.py` como apartado independiente en
HTML, Excel y Word reutilizando el desarrollo actual. Después: implementarlo como sección dentro de
`DatabaseDocumentation`.

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`, `.github/prompts/new_feature.prompt.md`
- Decisiones del usuario: sección dentro de `DatabaseDocumentation`; checks estáticos + dinámicos; eliminar `doc/audit/`;
  nombre «Condiciones del motor»; al final de cada formato, como almacenamiento

## AI output summary
- audit_code de `doc/audit/`: RECHAZADO (no generaba ficheros, TypeError con `AdvisoryFinding`, adaptador «hallazgos
  como tablas» incompatible con los renderers, tubería paralela a `DatabaseDocumentation`)
- PLAN + AUDIT_PLAN de la sección: GO_CONDICIONAL (puerto opcional, estáticos con `conn_params` del manager, avisos
  diferenciados, puerta completa)
- IMPLEMENT: `EngineReadinessReport` + `EngineReadinessAdvisor.assess()`; `SyncDatabaseManager.get_engine_readiness()`;
  puertos `EngineReadinessSourcePort`/`EngineConditionsPort` y vistas estructurales; `EngineConditionsSectionBuilder`;
  caché en `DocumentationSession`; flag `condiciones_motor` en `PrintConfigManager`; bloques en Word, Excel y HTML;
  plantillas `detail`/`index`; cabecera `CONDICIONES_MOTOR`; `doc/audit/` eliminado
- El test golden `test_doc_matches_golden[sqlite]` detectó la opción del índice HTML visible sin la sección: corregido
  (bloque condicional)
- AUDIT_CODE: 3 correcciones (cabeceras de longitud distinta, título de la página HTML, fila en `managers_sync.md`)
- Puerta: ruff, mypy (`src` + conformidad), pytest 5793 pasan / 531 saltos sin URLs del banco, `gen_arquitectura_capas`
  sin aristas nuevas, `zensical build --strict` sin incidencias

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Informe de auditoría inicial y PLAN | conversación | emitido |
| IMPLEMENT | `src/util_bbdd/{connection,managers,doc}/…` | completado |
| Tests | `tests/unit/test_doc_engine_conditions.py`, `tests/unit/test_protocol_conformance.py` | completado |
| Docs | `docs/api/database_documentation.md`, `docs/api/managers_sync.md`, `CHANGELOG.md` [Unreleased], `.github/prompts/engine_readiness_integration.prompt.md` §2b, `docs/guides/engine_readiness_usage_guide.md` | completado |
| Logs | `build/logs/engine_conditions_pytest.txt`, `build/logs/engine_conditions_zensical.txt` | no versionado |

## Directrices para Futuras IAs
- **[doc/puertos]**: una capacidad nueva del origen va en un Protocol `@runtime_checkable` aparte
  (`EngineReadinessSourcePort`), no en `DocumentationSourcePort`/`DocumentationBackendPort`/`DocumentationManagerPort`:
  son públicos (`doc.application`) y ampliarlos rompe a quien los implemente.
- **[doc/capas]**: `doc` no importa `connection`; consume `EngineReadinessReport` mediante la vista estructural
  `EngineReadinessReportView`. `gen_arquitectura_capas.py` cuenta también los imports bajo `TYPE_CHECKING`, así que una
  arista nueva obliga a dibujarla a mano en `render_svg()`.
- **[doc/secciones]**: patrón de sección final = flag en `PrintConfigManager` (`normalize`, valores por defecto y los tres
  `resolve_for_*`) → método con caché en `DocumentationSession` → un bloque por renderer (Word `idx == total_chunks`,
  hoja de Excel, página HTML + entrada del índice).
- **[doc/HTML]**: el test golden compara el texto de `index.html`: cualquier elemento nuevo del índice debe ser
  condicional para que la salida no cambie con la sección desactivada.
- **[doc/Excel]**: `SafeWorkbook` (`_core/export_safety.py`) ya neutraliza fórmulas y caracteres de control; no hace falta
  escapar celdas en hojas nuevas.
- **[connection/advisor]**: los checks estáticos deben usar los `conn_params` del usuario, nunca
  `_conn_params_from_engine(get_sqlalchemy_engine())`: ese engine no recibe parámetros de pool y mostraría los valores
  por defecto de SQLAlchemy como configuración leída.
- **[connection/advisor]**: `dynamic=True` significa que hubo conexión, no que todas las variables se leyeran: los
  validadores por motor se tragan sus errores (`logger.debug`).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit (rutas de la sesión solamente) y subida de versión a 2.2.0 con `/version-closure`
- Async: `AsyncDatabaseManager` sin `get_engine_readiness()` (DatabaseDocumentation es solo síncrono)
- `docs/api/engine_readiness_advisor.md` sigue sin existir (entregable de la «Integración 2» del prompt)
