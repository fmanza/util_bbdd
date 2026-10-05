# TRACEABILITY

## Session metadata
- id: 2026-10-06-version-closure-mariadb-charset-fallback-option-c
- fecha: 2026-10-06
- rama: no verificada en esta sesión (sin acceso a comando git status)
- skill: version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (Opción C) + AUDIT_CODE + VERSION

## Prompt issued
VERSION CLOSURE: MariaDB Charset Fallback Hotfix (Opción C).
Cierre solicitado con resumen de incidencia P1, archivos modificados, validación completada,
riesgos residuales, rollback, compatibilidad y veredicto APROBADO.

## Context supplied
- Solicitud de cierre con detalle de implementación y validaciones reportadas por el usuario.
- Estado de workspace y árbol del repositorio.
- Fecha de sesión: 2026-10-06.

## AI output summary
- Se leyeron guías de contexto de producto y calidad: .ai/product.md, .ai/standards.md, .ai/glossary.md.
- Se leyó la política de sincronización de versión: .github/instructions/sync.instructions.md.
- Se leyó el contrato de salida de cierre: .github/prompts/version_closure.prompt.md.
- Se verificó en código fuente la presencia del fallback defensivo en pool MariaDB:
  src/util_bbdd/connection/mariadb/pool_connection_mariadb.py.
- Se verificó en pruebas unitarias la existencia de:
  test_pool_retries_without_charset_if_driver_rejects_it,
  test_pool_reraises_type_error_when_not_related_to_charset,
  test_pool_fallback_validates_no_unicode_regression.
- Se verificó en integración la existencia de smoke test con pool y charset explícito:
  tests/integration/test_mariadb_engine_e2e.py::test_sync_manager_pool_smoke_with_explicit_charset.
- No se modificó código de src/ ni tests/ durante esta sesión de cierre.
- No se actualizaron campos de versión ni CHANGELOG en esta sesión, siguiendo el alcance indicado
  por la solicitud (hotfix interno de compatibilidad ya validado).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| VERSION closure traceability | .ai/sessions/2026-10-06-version-closure-mariadb-charset-fallback-option-c/TRACEABILITY.md | emitido |

## Directrices para Futuras IAs
**[connection/mariadb]**: En pool sync MariaDB, el fallback debe activarse solo cuando el TypeError incluya simultáneamente "unexpected keyword argument" y "charset" para evitar falsos positivos.

**[connection/mariadb]**: Si ConnectionPool rechaza charset, el reintento debe conservar todos los parámetros originales excepto charset; no alterar host, user, database, pool_size, ni pool_name.

**[observabilidad]**: El warning de fallback debe incluir la versión detectada de mariadb driver para facilitar RCA en producción.

**[tests/unit]**: Mantener cobertura explícita de tres ramas: fallback exitoso, TypeError no relacionado (re-raise) y no regresión semántica de Unicode en ruta fallback.

**[tests/integration]**: El smoke test con use_pool=True y charset explícito debe permanecer para detectar regresiones cross-driver en CI cuando haya URL MariaDB disponible.

**[release-policy]**: En cierres internos de compatibilidad sin bump aprobado, evitar tocar campos de versión y concentrar evidencia en TRACEABILITY.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Evaluar en próxima release si se fija versión mínima recomendada de mariadb driver para retirar fallback defensivo.
- Revisar si el mismo patrón de fallback aplica a conexión directa sync (no pool), según evidencia de campo.
- Garantizar ejecución en CI de integración MariaDB con variable UTIL_BBDD_TEST_MARIADB_URL configurada.
