# REQUEST

## Session metadata
- id: 2026-10-18b-index-modes-bulk-dump
- fecha: 2026-10-18
- rama: develop
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN (sin IMPLEMENT)

## Solicitud original saneada
En el módulo `dump` se usa `manage_indexes`: si `True`, deshabilita los índices secundarios no únicos del destino antes
de la carga y los reconstruye al final (mssql `ALTER INDEX DISABLE`→`REBUILD` solo NONCLUSTERED, oracle
`UNUSABLE`→`REBUILD`, postgresql `DROP` + recreate desde `pg_get_indexdef`, mariadb/mysql no soportado). Nunca toca
índices que respaldan PK/UNIQUE. Medido a 3,5M filas con 2 índices secundarios: Oracle −14 %, SQL Server −8 %,
PostgreSQL sin ganancia.

Se quiere incorporar esta estrategia en el módulo `bulk` para acelerar la carga de datos por tabla, revisar la
implementación actual y ver si tiene sentido compartir estrategia. Solo PLAN.

Ampliaciones posteriores de la misma sesión:
1. Explicar por qué nunca se tocan PK, UNIQUE ni el índice clustered y por qué no aplica a MariaDB.
2. Añadir un paso opcional de medición para MariaDB/MySQL y el resto de motores; poder desactivar **todos** los índices,
   **solo los secundarios** o **ninguno**. Objetivo: ganar rendimiento en la carga final (los procesos de carga pasan
   por varias iteraciones para garantizar la calidad del dato).
3. Revisar si `SET FOREIGN_KEY_CHECKS = 0/1` en MariaDB/MySQL es una opción a incluir en el plan.
4. AUDIT_PLAN; confirmar decisiones y guardar PLAN y AUDIT_PLAN en `.ai/sessions/`.

## Objetivo operativo de esta sesión
- Diagnóstico comparado de `dump.IndexManager` y `bulk` `TableMaintenance._disable_indexes`.
- PLAN de una estrategia de índices compartida con tres modos (`False` / `"secondary"` / `"all"`) y medición previa (G0).
- AUDIT_PLAN con veredicto y condiciones; decisiones confirmadas por el usuario.

## Restricciones explícitas
- Solo PLAN y AUDIT_PLAN: no se modifica `src/`, `tests/` ni `docs/`.
- `docs/architecture.md` tiene cambios del usuario en curso: no se toca.

## Resultado esperado
- `.ai/sessions/2026-10-18b-index-modes-bulk-dump/` con `00_REQUEST.md`, `01_PLAN.md`, `02_AUDIT_PLAN.md` y
  `TRACEABILITY.md`; fila en `.ai/sessions/INDEX.md`.
