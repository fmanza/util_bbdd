# TRACEABILITY

## Session metadata
- id: 2026-10-01g-oracle-routines-filter
- fecha: 2026-10-01
- rama: develop
- skill: fix (fuera del flujo /hotfix: cambia qué filas devuelve una API pública)
- fase: explicación → decisión del usuario («Sí, la recomendada») → IMPLEMENT (test-first) → commit sin push

## Prompt issued
- «Dime qué es esto: Queda anotado, fuera de alcance: el listado de rutinas de Oracle sigue incluyendo disparadores y
  tipos» → opciones (1: solo PROCEDURE/FUNCTION, recomendada; 2: + PACKAGE; 3: documentar) → «Sí, la recomendada».

## AI output summary
- `fetch_routines_sql` (Oracle, adaptadores de metadatos) leía todo `ALL_PROCEDURES`: packages y sus subprogramas,
  disparadores (en el banco aparecía uno, `75049`) y tipos con métodos. El resto de motores lista solo procedimientos y
  funciones. Ningún consumidor interno usa `fetch_routines_sync` (migrate tiene su consulta; los managers y el
  comparador van por otra vía).
- Fix: `AND object_type IN ('PROCEDURE', 'FUNCTION')`.
- Test first: `tests/integration/test_oracle_routines_metadata.py` añade una tabla con disparador y comprueba que el
  listado solo trae procedimientos y funciones (fallaba antes: salían el package, su miembro y el disparador).

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest` con las URLs del banco (unitarios + integración): 5999 passed.

## Directrices para Futuras IAs
- **[metadata/oracle]**: `fetch_routines_sync/async` = solo `PROCEDURE` y `FUNCTION` (como los demás motores); los
  packages, disparadores y tipos de `ALL_PROCEDURES` quedan fuera a propósito (0.23.2).
- **[proceso]**: cambiar qué filas devuelve una API pública no es un hotfix (fix mínimo) aunque sea pequeño: va como
  `fix:` con entrada «Changed» en el CHANGELOG.

## Veredicto final
Veredicto: CLOSED — implementado y verificado (commit sin push).
