# TRACEABILITY

## Session metadata
- id: 2026-10-01f-hotfix-oracle-routines-metadata
- fecha: 2026-10-01
- rama: develop
- skill: hotfix (P2: dato incorrecto en una API pública)
- fase: PLAN → AUDIT_PLAN → IMPLEMENT (RCA + fix, test-first) → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- `/hotfix` con las dos notas del hotfix R4: (1) el MySQL del banco no deja crear funciones sin SUPER (error 1419);
  (2) la `fetch_routines_sql` de Oracle de los adaptadores probablemente da nombre vacío.

## AI output summary
- **(2) Confirmado en el banco** (`r5_oracle_adapter.py`): `OracleSyncAdapter.fetch_routines_sync(owner)` devolvía
  `('', 'PROCEDURE', '78022')`, `('', 'FUNCTION', '78023')`, `('', 'PACKAGE', '78024')`…: nombre vacío y `object_id` en
  la columna `routine_owner`. `fetch_routine_definition_sync` (por nombre) sí funcionaba.
- **RCA** (`metadata/oracle/tables.py` `fetch_routines_sql`): devolvía `(procedure_name, object_type, object_id)`;
  `procedure_name` es NULL en rutinas sueltas y en la fila de cada package; y `decode_oracle_routine_rows` espera
  `(nombre, tipo, owner, object_id)`.
- **Fix mínimo** (solo la consulta): `SELECT COALESCE(procedure_name, object_name), object_type, owner, object_id`.
  Mismas filas que antes (sigue incluyendo TRIGGER/TYPE: filtrarlos cambiaría la API; anotado). Migrate no usa esta
  consulta desde R4. Docstring de `decode_oracle_routine_body` corregido (quedó falso tras R4).
- **Test first**: `tests/integration/test_oracle_routines_metadata.py` (procedimiento, función y package con miembro;
  fallaba antes del fix: solo salía el miembro, con un `object_id` como owner).
- **(1) No es un bug de código**: es la configuración del servidor (`log_bin_trust_function_creators=0` con binlog y el
  usuario del banco sin SUPER). Documentado en la guía en el hotfix R4; cambiar el banco es decisión del usuario.

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5746 passed, 253 skipped. `tests/integration`: 392 passed.

## Directrices para Futuras IAs
- **[metadata/oracle]**: toda consulta sobre `ALL_PROCEDURES` debe tomar el nombre de `COALESCE(procedure_name,
  object_name)` (o `object_name` para rutinas sueltas); `procedure_name` solo existe en miembros de package.
- **[release]**: la v0.23.1 es PATCH: solo correcciones; las funciones de metadatos nuevas (`fetch_routine_parameters_for_schema_sql`, `fetch_routines_for_schema_sql`) son consultas auxiliares de migrate y no cambia ninguna firma existente. El cuerpo de `CanonicalRoutine` cambia de contenido (R4).
- **[tests]**: los tests de texto de SQL («contiene `all_procedures`») no detectan columnas en orden equivocado; para
  consultas de catálogo, un test de integración contra el motor real.

## Veredicto final
Veredicto: CLOSED — hotfix aplicado y verificado en el banco; liberado en v0.23.1 (2026-10-01).
