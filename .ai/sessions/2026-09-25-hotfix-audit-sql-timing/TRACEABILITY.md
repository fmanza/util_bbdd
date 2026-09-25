# TRACEABILITY

## Session metadata
- id: 2026-09-25-hotfix-audit-sql-timing
- fecha: 2026-09-25
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN (x3, ver decisiones) + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Se ha observado que en la exportación de auditoria se ha dejado de mandar el tiempo que se tarda en generar el SQL. PLAN y AUDIT_PLAN
Separar las medidas
No, tiempo_seg tiene que ser la única columna de tiempo. En excel incluir si es generación de SQL o no
si
```

## Context supplied
- `src/util_bbdd/bulk/{crud,audit}.py`, `bulk/_audit/{repository,service,exporters,html_template}.py`, `bulk/_support/persistence.py`
- Historial de git de `crud.py` y `_audit/`; `.ai/doc_old/sessions/2026-05-26-bulk-audit-fix/TRACEABILITY.md`
- Traza de un proyecto externo (`pruebas_util`) que usa `util_bbdd` desde `site-packages`

## AI output summary
- **RCA**: `__run_bulk_pipeline` dejaba `elapsed = 0.0` con `generar_sql=True` (commit `e7c19e2`, sesión `2026-05-26-bulk-audit-fix`, decisión deliberada: `tiempo_seg` = latencia de BD). Toda fila `sql=Sí` del CSV salía con `tiempo_seg = 0,000`. Los exportadores no eran el origen: nunca tuvieron un campo específico de SQL.
- **Decisiones (tres planes)**: (A) restaurar `tiempo_seg` → (B) columna nueva `tiempo_sql_seg` con migración de cabecera del CSV → **(A + columna `sql` en el Excel)**. La B se descartó a petición del usuario: `tiempo_seg` debe ser la única columna de tiempo.
- **IMPLEMENT**:
  - `crud.py`: `perf_counter` envuelve las dos ramas (generar y escribir el SQL / ejecutar); `elapsed` se calcula tras ambas.
  - `_audit/service.py`: `determinar_group_cols` añade `"sql"` en las tres listas; `agrupar_y_generar_resumen` agrupa con `dropna=False`.
  - `_audit/exporters.py`: la selección explícita de columnas de `Resumen_global` incluye `sql` tras `operacion`.
- **Tests nuevos**:
  - `tests/unit/bulk/test_audit_sql_generation_timing.py` (7): insert/update/delete × `generar_sql` True/False con `perf_counter` parcheado (10.0 → 12.5, `elapsed == 2.5`). Con el código anterior fallaban los 3 casos `True` (`0.0 == 2.5`).
  - `tests/unit/test_audit_excel_export.py` (6): `sql` en cada hoja de los tres modos, filas Sí/No separadas con sus agregados, orden de columnas de `Resumen_global`, y fila sin `sql` no descartada. No existía ningún test de `exportar_resumen_excel`.
- **Validación**:
  - 13 tests nuevos en rojo con el código anterior (8 fallos) y en verde después;
  - mutación: sin `dropna=False`, el test de la fila sin `sql` falla (30 ≠ 37);
  - `ruff check`, `ruff format --check` y `mypy src tests/unit/test_protocol_conformance.py` limpios (341 ficheros);
  - `tests/unit` completo: 4347 passed;
  - extremo a extremo (SQLite, 10.000 filas, insert/update/delete con y sin `generar_sql`): las filas `Sí` salen con 0,031 / 0,041 / 0,025 s y el Excel las separa de las `No`.

## AUDIT_CODE
- Regresiones potenciales:
  - `determinar_group_cols` y `agrupar_y_generar_resumen` solo los usa `exportar_resumen_excel` (grep);
  - el Excel gana la columna `sql` antes de `total_filas`: quien lo lea por posición verá el desplazamiento;
  - sin cambio de firmas, de esquema del CSV ni de API pública: no hay migración y el rollback es revertir el commit.
- Edge cases: fila con `sql` vacío (conservada por `dropna=False`); `elapsed >= 0` siempre (reloj monótono).
- No verificado: integración contra los motores reales (`tests/integration/test_bulk_engines.py` necesita URLs). El cambio no depende del dialecto.
- Fuera de alcance, pendiente de decisión: `obtener_estadisticas` (JSON), HTML y `dump/orchestrator.py` siguen sumando en `tiempo_seg` filas de ejecución y de generación (`tiempo_total_segundos`, `tiempo_promedio_segundos`, `tiempo_minimo_segundos`, `operacion_mas_lenta`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/bulk/crud.py` | modificado |
| Excel por `sql` | `src/util_bbdd/bulk/_audit/{service,exporters}.py` | modificado |
| Tests | `tests/unit/bulk/test_audit_sql_generation_timing.py`, `tests/unit/test_audit_excel_export.py` | nuevos |
| Docs | `docs/api/bulk-audit.md`, `docs/examples/bulk_insert_csv.md`, `CHANGELOG.md` (`[Unreleased]`) | modificados |

## Directrices para Futuras IAs
- **[auditoría / tiempo]**: `tiempo_seg` es la única columna de tiempo y mide la operación: ejecución en BD (`sql=No`) o generar y escribir el fichero SQL (`sql=Sí`). **Sustituye a la directriz de `2026-05-26-bulk-audit-fix`** ("`elapsed=0.0` con `generar_sql=True`, no restaurar el timing"): el usuario pidió expresamente recuperar el tiempo de generación. No añadir una segunda columna de tiempo.
- **[auditoría / Excel]**: los resúmenes agrupan siempre por `sql`; mezclar ambos tipos de fila en un mismo agregado da medias y totales sin significado. Toda agrupación nueva sobre `tiempo_seg` debe hacer lo mismo.
- **[pandas]**: `groupby` descarta por defecto las claves `NaN` (comprobado: 30 de 40 filas). Con una clave que puede venir vacía, usar `dropna=False`.
- **[medición]**: el tiempo de `sql=Sí` incluye la escritura del fichero: desde P-07 la generación es perezosa y se escribe a medida que se genera, así que no se pueden separar sin cargar el SQL en memoria.
- **[tests]**: `exportar_resumen_excel` no tenía ningún test hasta esta sesión; el error de `timestamp` con formato mixto (commits `3358060`, `f0f221f`) pasó por esa falta de cobertura.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit pendiente de petición del usuario. Mensaje sugerido: `fix(bulk): tiempo_seg vuelve a medir la generación de SQL y el Excel separa generación de ejecución`.
- Versión sugerida al publicar: 0.14.1 (fix; el Excel gana una columna).
- Decidir si JSON, HTML y las estadísticas también separan por `sql`.
- Verificar en `pruebas_util`: usa `util_bbdd` desde `site-packages`, hay que reinstalar la versión modificada.
