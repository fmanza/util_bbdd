# REQUEST

## Session metadata
- id: 2026-10-19-oracle-unique-index-all
- fecha: 2026-10-19
- rama: develop
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN (IMPLEMENT tras aprobación)

## Solicitud original saneada

Oracle, modo `"all"` de índices (bulk `maintenance_scope`/`ParallelOptions(disable_indexes="all")`, dump
`manage_indexes="all"`): gestionar los índices únicos sin constraint. Opción híbrida: si `DBMS_METADATA.GET_DDL`
funciona (privilegios y DDL recreable), `DROP INDEX` (logueando el DDL antes) y recrear al restaurar con ese DDL (si
falla por duplicados, `IndexRebuildError` con el DDL); si no, no tocarlo pero reportarlo en `index_results` con estado
`"skipped"` y un warning. SQL de catálogo solo en `metadata/` (ADR-003), compatible con Oracle 11g (ADR-004). Tests
unitarios + integración contra el Oracle del banco.

## Objetivo operativo de esta sesión
- Que `"all"` en Oracle desactive (DROP) y recree los índices únicos sin constraint cuando su DDL se puede obtener.
- Que los que no se pueden recrear aparezcan en `index_results` como `"skipped"` con el motivo y un warning.
- Que un fallo al recrearlos dé `IndexRebuildError` con el DDL para recrearlos a mano.

## Restricciones explícitas
- Política `new_feature`: sin refactor de código no relacionado.
- SQL de catálogo solo en `metadata/` (ADR-003); compatible con Oracle 11g (ADR-004).
- Sin dependencias nuevas.

## Resultado esperado
- Código en `metadata/` y `bulk/_support/secondary_indexes.py`, tests unitarios y de integración (banco Oracle),
  documentación y CHANGELOG; artefactos de sesión en esta carpeta.
