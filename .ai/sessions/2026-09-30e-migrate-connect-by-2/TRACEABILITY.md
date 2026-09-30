# TRACEABILITY

## Session metadata
- id: 2026-09-30e-migrate-connect-by-2
- fecha: 2026-09-30
- rama: develop
- skill: new_feature (deuda E3 de la 0.21.0)
- fase: PLAN + AUDIT_PLAN («Plan y Audit de las deudas») → IMPLEMENT → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- «Plan y Audit de las deudas» (E1–E3) → «IMPLEMENT». Opciones recomendadas tomadas como aprobadas; orden E3 → E2 → E1
  para la 0.22.0, una sesión por ítem.

## Context supplied
- `src/util_bbdd/migrate/views/_rewrites.py` (`oracle_connect_by`, V4 de la sesión `2026-09-29c-migrate-views`),
  `views/transpiler.py`, `tests/unit/migrate/test_view_connect_by.py`, `tests/integration/test_migrate_views_e2e.py`.

## AI output summary
- **`AND LEVEL <= n`** en la condición de `CONNECT BY` (`_connect_condition`: un `PRIOR a = b` y cotas de `LEVEL`,
  cualquier orden; se toma la menor): la rama recursiva añade `WHERE connect_by_parent.cb_level < n` (en `CONNECT BY`,
  `LEVEL` es el del hijo). Otra condición adicional (`AND activo = 1`) sigue sin reescribir.
- **`CONNECT_BY_ISLEAF`** (`_is_leaf`): `CASE WHEN [cb_level < n AND] EXISTS (SELECT 1 FROM tabla cb_child WHERE
  cb_child.hijo = fila.padre) THEN 0 ELSE 1 END` en la consulta exterior. Contra la tabla, no contra el resultado: el
  `WHERE` de la vista no convierte en hoja a un nodo cuyos hijos filtra (Oracle igual). Proyección sin alias →
  alias `connect_by_isleaf`.
- **`NOCYCLE` solo hacia PostgreSQL**: columna `cb_keys` = `ARRAY[padre]` en el ancla y `cb_keys || ARRAY[padre]` en la
  rama recursiva, que filtra `NOT padre = ANY(connect_by_parent.cb_keys)`; `CONNECT_BY_ISLEAF` excluye el hijo que ya
  está en `cb_keys`. Primer intento con la cláusula `CYCLE` de PostgreSQL 14+: filas correctas, pero el e2e contra
  Oracle mostró que Oracle da `CONNECT_BY_ISLEAF = 1` a la fila cuyo único hijo es un antepasado, y `CYCLE` no da los
  antepasados a ISLEAF → se sustituyó por el array (sirve además en PostgreSQL < 14). Resultado nuevo
  `"hierarchy_nocycle"` (`CONNECT_BY_CONVERTED`) para el aviso «VIEW (jerarquía)» específico.
- `ORDER SIBLINGS BY` y `CONNECT_BY_ISCYCLE` siguen sin reescribir.
- Tests: unitarios `TestLevelBoundAndLeaf` (SQL ejecutado en SQLite) y `TestNocycle` (estructura; SQLite no tiene
  arrays), `TestNotRewritten` actualizado; e2e: vistas Oracle `jerarquia_nivel` y `jerarquia_hoja` en los 20 pares y
  `test_oracle_nocycle_hierarchy_to_postgresql` (tabla con ciclo Ana → Luis → Eva → Ana, comparación fila a fila).
- Docs: `docs/functional/migrate_views.md` (tabla y límites), `docs/api/migrate_views.md`, guía §3.5; CHANGELOG
  `[Unreleased] › Added`.

## Verificación
- `ruff check`/`ruff format`, `mypy src tests/unit/test_protocol_conformance.py` (386 ficheros): sin errores.
- `pytest`: 5702 passed, 227 skipped. `tests/integration` (banco de 5 servidores): 366 passed.

## AUDIT_CODE
- Contrato: `oracle_connect_by` añade el resultado `"hierarchy_nocycle"`; el único consumidor (`transpiler`) usa
  `CONNECT_BY_CONVERTED`. Sin cambios de API pública.
- Supuesto documentado: con `NOCYCLE` la columna de `PRIOR` identifica la fila (Oracle detecta el ciclo por fila); con
  valores repetidos en esa columna el corte podría diferir.
- Alias internos nuevos (`cb_keys`, `cb_child`): la tabla con columnas `cb_*` ya se rechaza; `cb_child` pasa por
  `_free_name`.
- Veredicto: APROBADO.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Conversión | `src/util_bbdd/migrate/views/_rewrites.py`, `views/transpiler.py` | completado |
| Tests | `tests/unit/migrate/test_view_connect_by.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Docs | `docs/functional/migrate_views.md`, `docs/api/migrate_views.md`, `docs/guides/ddl_migration_guide.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/views/CONNECT BY]**: comprobar cada ampliación de `oracle_connect_by` contra Oracle real (e2e), no solo en
  SQLite: la semántica de `CONNECT_BY_ISLEAF` con `NOCYCLE` (1 si el único hijo es un antepasado) solo apareció así.
- **[migrate/views/CONNECT BY]**: los identificadores sin comillas del SQL reescrito salen en mayúsculas (`qualify` con
  dialecto Oracle); comparar el SQL generado sin distinguir mayúsculas en los tests.
- **[migrate/views/CONNECT BY]**: el aviso por tipo de conversión depende del resultado de `oracle_connect_by`
  (`"hierarchy"`, `"hierarchy_nocycle"`, `"generator"`); un resultado nuevo se añade a `CONNECT_BY_CONVERTED`.

## Veredicto final
Veredicto: CLOSED — E3 implementado y verificado; pendiente de `/version-closure` 0.22.0 con E2 y E1.
