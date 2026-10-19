# AUDIT_PLAN

## Riesgos funcionales
- Cambio de comportamiento en Oracle con `"all"`: los índices únicos sin constraint dejan de comprobarse durante la
  carga; un duplicado se detecta al recrear (`IndexRebuildError`) y el índice queda borrado (R1). Va en el CHANGELOG
  como cambio de comportamiento.
- El nuevo estado `"skipped"` lo ve quien recorra `index_results`; quien compare `action` contra los cuatro valores de
  antes puede no esperarlo (Literal ampliado: cambio aditivo).
- El test de integración `test_manage_indexes_restores_indexes` cambia su expectativa para Oracle (`ux_big` tocado).

## Riesgos técnicos
- LSP: `IndexDdlRunner`/`SecondaryIndexPlanner` mantienen firma y contrato; los consumidores no cambian.
- ISP: `UniqueIndexFact` gana dos campos opcionales; `IndexStep` uno. Sin interfaces nuevas.
- Sync/async: sin impacto (todo el DDL va por conexión sync, como hoy).
- `GET_DDL` dentro de la transacción de `maintenance_scope`: en Oracle un SELECT fallido no aborta la transacción.
- Coste: una llamada a `GET_DDL` por índice único sin constraint, solo en `"all"` (decenas de ms).
- 11g no verificable en el banco (R3); se cubre con SQL compatible y tests unitarios del SQL.

## Riesgos de seguridad
- Se ejecuta DDL leído del propio servidor (`DBMS_METADATA`), no de entrada del usuario; nombres citados con el
  `identifier_preparer`. El DDL va al log (como ya hace PostgreSQL): contiene nombres de objetos y tablespaces, no datos.
- Sin privilegios de catálogo no se borra nada (`"skipped"`).

## Simplificaciones posibles
- No aplicar transformaciones de `DBMS_METADATA` (`SET_TRANSFORM_PARAM`): el DDL por defecto se ejecuta tal cual y no
  cambia el estado de la sesión.
- No hay FK que referencien un índice único sin constraint en Oracle (las FK solo referencian PK/UNIQUE): no hace falta
  gestionar FK entrantes para estos pasos.

## Hallazgos fuera de alcance (no se implementan)
- H1: una UNIQUE/PK que usa un índice único **creado antes** (`USING INDEX`) conserva el índice al
  `DISABLE CONSTRAINT … CASCADE` (comprobado en el banco: sigue `VALID UNIQUE` y da `ORA-00001`). `"all"` lo informa
  como `"rebuilt"` sin haberlo desactivado. Pendiente para otra sesión.
- H2: `duplicates_sql` usa `FETCH FIRST` en Oracle (12c+); en 11g el diagnóstico de duplicados falla (se loguea en
  debug y no salen las claves). Ver condición C3.

## Veredicto: GO_CONDICIONAL

## Condiciones
- C1: integración en el banco Oracle con tres casos: recreado (incluida una expresión con `:` en un literal),
  duplicados → `IndexRebuildError` con `recovery_ddl`, y `"skipped"` (índice de otro esquema sin privilegios, con
  `UTIL_BBDD_TEST_ORACLE_ADMIN_URL`).
- C2: puerta completa (ruff, mypy, pytest sin URLs del banco y con banco en Oracle) y `zensical build --strict`.
- C3 (decisión del usuario): corregir también H2 (`FETCH FIRST` → `ROWNUM`, compatible con 11g) en este cambio, porque el
  diagnóstico de duplicados forma parte del flujo nuevo. Recomendado: sí.
