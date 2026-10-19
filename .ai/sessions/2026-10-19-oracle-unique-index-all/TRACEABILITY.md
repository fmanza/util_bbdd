# TRACEABILITY

## Session metadata
- id: 2026-10-19-oracle-unique-index-all
- fecha: 2026-10-19
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Ver `00_REQUEST.md`. Aprobación de IMPLEMENT: «IMPLEMENT con C3».

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md`, agentes del flujo
- `src/util_bbdd/bulk/_support/secondary_indexes.py`, `src/util_bbdd/metadata/facts.py`,
  `src/util_bbdd/metadata/oracle/indexes.py`, `bulk/_execution/maintenance.py`, `bulk/_execution/parallel_loader.py`,
  `dump/_indexes.py`, `bulk/_models.py`, `_core/exceptions.py`
- Sondeo en el banco Oracle 23.26 Free (`scratchpad/ora_probe.py`, fuera del repo)

## AI output summary
- Sondeo en el banco: `UNUSABLE` en un único → ORA-01502; `GET_DDL` ejecutable tal cual; ORA-01452 con duplicados;
  ORA-31603 sin privilegios; columnas ocultas en índices basados en función; falso positivo de claves todo-NULL.
- PLAN + AUDIT_PLAN (GO_CONDICIONAL; C3 aprobada).
- IMPLEMENT por capas (metadata → bulk → core/audit → docs); tests unitarios (5) y de integración (3 + 1 actualizado).
- AUDIT_CODE: corregido el escape de `:` en el diagnóstico; APROBADO.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-19-oracle-unique-index-all/00_REQUEST.md` | emitido |
| PLAN | `.ai/sessions/2026-10-19-oracle-unique-index-all/01_PLAN.md` | emitido |
| AUDIT_PLAN | `.ai/sessions/2026-10-19-oracle-unique-index-all/02_AUDIT_PLAN.md` | GO_CONDICIONAL |
| IMPLEMENT | `.ai/sessions/2026-10-19-oracle-unique-index-all/03_IMPLEMENT.md` | completado |
| AUDIT_CODE | `.ai/sessions/2026-10-19-oracle-unique-index-all/04_AUDIT_CODE.md` | APROBADO |

## VERSION

- Commit propuesto: `feat(bulk): índices únicos sin constraint de Oracle en disable_indexes="all"`.
- CHANGELOG: `[Unreleased]` (Added: `"skipped"` y `recovery_ddl`; Changed: comportamiento de Oracle; Fixed:
  diagnóstico con `ROWNUM` y sin claves todo-NULL). Va en la 4.0.0 junto al extra `oracle`.
- Impacto en API pública: aditivo (`Literal` ampliado, atributo nuevo). Cambio de comportamiento en Oracle con `"all"`.
- Rollback: revertir el commit; no hay migraciones ni datos persistidos.
- Pruebas sugeridas antes del release: Oracle 11g si hay uno disponible; índice particionado `LOCAL` en el banco.

## Directrices para Futuras IAs

- **[índices Oracle]**: un índice único `UNUSABLE` hace fallar el INSERT (ORA-01502); la única forma de no mantenerlo
  durante la carga es `DROP` + recrear con `DBMS_METADATA.GET_DDL` (`metadata/oracle/indexes.py`).
- **[índices Oracle]**: en índices basados en función, `ALL_IND_COLUMNS` da columnas ocultas `SYS_NC…$` que cambian al
  recrear; para consultar la clave hay que usar `ALL_IND_EXPRESSIONS` (`UniqueIndexFact.key_sql`).
- **[índices Oracle]**: `GET_DDL` sin privilegios de catálogo sobre otro esquema da ORA-31603 aunque el índice sea
  visible en `ALL_INDEXES`; `DISABLE CONSTRAINT` sobre una UNIQUE `USING INDEX` de un índice previo lo conserva
  `VALID UNIQUE` (H1, pendiente).
- **[secondary_indexes]**: el DDL leído del catálogo se ejecuta con `text()`; escapar los `:` (`_escape_colons`) y
  guardar el original en `recovery_ddl`. Un paso con `skip_reason` se devuelve en `disable()` para que `restore()` lo
  informe como `"skipped"` sin tocar a los consumidores.
- **[Oracle 11g]**: no usar `FETCH FIRST` en SQL que pueda ejecutarse contra Oracle (ADR-004); `ROWNUM` en subconsulta.

## Veredicto final
GO
