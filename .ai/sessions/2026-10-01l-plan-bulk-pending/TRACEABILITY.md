# TRACEABILITY

## Session metadata
- id: 2026-10-01l-plan-bulk-pending
- fecha: 2026-10-01
- rama: develop (`e2ce535`, v0.25.1 publicada)
- skill: plan (PLAN + AUDIT_PLAN; sin IMPLEMENT)

## Prompt issued
«Hazlo, PLAN Y AUDIT-PLAN» sobre los pendientes de `bulk`: coste del filtro de OPENJSON del hotfix y Fase 3 del roadmap.

## AI output summary
- Medición de CPU del filtro de OPENJSON (1M claves): INT 0,40 s, VARCHAR 0,31 s, NUMERIC **2,06 s**; prototipo por
  columna INT 0,04 s.
- Verificado: lock de auditoría solo entre hilos (`repository.py:31`), lectores `lambda` en `range_partitioner.py` y guía,
  `py-spy` no instalado.
- `PLAN.md` (P-1, S-1…S-4) y `AUDIT_PLAN.md` (GO_CONDICIONAL; R-1…R-7; D-1…D-3).

## Directrices para Futuras IAs
- **[bulk/delete mssql]**: el filtro `_fits` del hotfix A1 cuesta 2,06 s/1M con PK `DECIMAL` (quantize con contexto
  local por valor); cualquier optimización debe probar equivalencia exacta con `_fits`.
- **[bulk/parallel]**: `ParallelBulkLoader` con procesos exige lectores serializables y un lock de fichero para la
  auditoría CSV (hoy `threading.Lock`).

## Veredicto final
Veredicto: GO_CONDICIONAL (pendiente D-1…D-3)
