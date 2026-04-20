# REQUEST — 2026-04-20 fase3-managers

**Fecha:** 2026-04-20
**Versión objetivo:** 0.6.9
**Skill:** refactor

## Objetivo

Fase 3 de consolidación de `managers/`: 28 funciones distribuidas → 8 clases SOLID-compliant.
Componentes: MetadataRequestBuilder, CharsetCollationParser, DDLNormalizer.

## Estado

IN_PROGRESS — notas de migración en `03_MIGRATION_NOTES.md`.

## Restricciones

- 100% backward compatible (wrappers de deprecación)
- Sin breaking changes en API pública
- Todos los tests en verde antes de cierre
