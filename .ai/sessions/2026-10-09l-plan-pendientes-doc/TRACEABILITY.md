# TRACEABILITY

## Session metadata
- id: 2026-10-09l-plan-pendientes-doc
- fecha: 2026-10-09
- rama: develop
- skill: PLAN + AUDIT_PLAN (pendientes de `documentation-architecture-audit`)
- fase: PLAN + AUDIT_PLAN (solo lectura)

## Prompt issued
```text
PLAN y AUDIT_PLAN de lo Pendiente
```

## Context supplied
- `.ai/sessions/2026-10-09k-doc-architecture-audit/06_VERIFY.md` § 3 y `TRACEABILITY.md` (pendientes al cierre).
- Banco docker (6 motores + HSQLDB) para las comprobaciones de § 1.

## AI output summary
- B-04: sonda contra HSQLDB 2.7.4: `LISTAGG … WITHIN GROUP (ORDER BY ORDINAL_POSITION)` y `GROUP_CONCAT` funcionan; la
  rama de vistas usa `INFORMATION_SCHEMA.VIEWS.TEXT`, que no existe; los `CASE` dejan relleno de `CHAR`.
- S-02: vista con `'&amp;<b>'` en los 6 motores: todos devuelven el texto sin entidades → la decodificación de HTML es
  un bug de fidelidad, no una protección.
- Orden del inventario: `ORDER BY total_mb DESC` sin desempate en MySQL/MariaDB; sin `ORDER BY` en PostgreSQL y SQLite.
- Oracle: el contexto de metadatos es siempre el usuario conectado → el dorado aislado necesita un usuario propio.
- `mypy --strict`: 72 `type-arg` + 9 python-docx.
- Plan P0–P7 con cinco decisiones pendientes (D1–D5).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-09l-plan-pendientes-doc/PLAN_AUDIT_PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[HSQLDB/DDL]**: en HSQLDB 2.7 `INFORMATION_SCHEMA.VIEWS` tiene `VIEW_DEFINITION`, no `TEXT`; `LISTAGG` exige
  `WITHIN GROUP (ORDER BY …)`; un `CASE` con literales de distinta longitud se tipa `CHAR` y rellena con espacios.
- **[doc/entidades]**: ningún motor del banco devuelve DDL o definiciones con entidades HTML (comprobado con
  `'&amp;<b>'` en PostgreSQL, MySQL, MariaDB, SQL Server, Oracle y SQLite).
- **[Oracle/contexto]**: `MetadataContextResolver` usa el usuario conectado como schema en Oracle; documentar otro
  owner exige conectar como él.

## Veredicto final
Veredicto: GO_CONDICIONAL (AUDIT_PLAN)
Pendientes al cierre:
- Decisiones D1–D5 del usuario antes de IMPLEMENT.
