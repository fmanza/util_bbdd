# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p06-generar-sql-template
- fecha: 2026-09-24
- rama: develop
- skill: refactor (rendimiento, salida idéntica) + hotfix P-29 detectado durante el trabajo
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y sigo con P-06 …?". Antes, commits `7dc3ae8` y `8141ca6` de P-10.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-06: una sentencia compilada por fila, ~165 µs/fila; propuesta de `literal_processor` por columna)
- `02_BASELINE_MOTORES_REALES.md` (observación 0f: `%(nombre)s` → `?`)
- `src/util_bbdd/bulk/_support/sql_helpers.py`

## AI output summary
- **Diseño**: `_LiteralTemplate` compila la sentencia **una vez** con marcadores (`literal_column("__util_bbdd_literal_<n>__")`) y la trocea. Por fila solo renderiza literales:
  - con `compiler.render_literal_value(valor, tipo)` del compilador del dialecto, la misma función que usa `literal_binds`;
  - con el mismo tipo de parámetro que SQLAlchemy: el de la columna en VALUES/SET, `String` para JSON (P-20) y `tipo.coerce_compared_value(eq, valor)` en el WHERE;
  - `None` → `NULL`, salvo en el WHERE (SQLAlchemy genera `IS NULL`), que va por el camino anterior;
  - deshace `%%` como P-23.
- **Paso a paso**:
  - Primera plantilla del INSERT: con el marcador en la PK, SQLAlchemy añadía `RETURNING`/`OUTPUT`. Con `Insert.inline()` la forma es idéntica en 5 dialectos × 3 tipos de PK.
  - Al comprobar el INSERT **sin** PK apareció **P-29**: la salida anterior ya incluía `RETURNING` (PostgreSQL), `OUTPUT inserted.id` (SQL Server) y `RETURNING … INTO :ret_0` (Oracle).
  - P-29 verificado contra los servidores del banco: Oracle 23 no ejecuta el fichero (`DPY-4010`); PostgreSQL y SQL Server lo ejecutan devolviendo filas.
  - Se corrigió con `inline()` también en el camino fila a fila.
- **Camino anterior**: `render` devuelve `None` y la fila se genera con la función de antes en tres casos:
  - `None` en WHERE;
  - tipos sin renderizador de literales o valor rechazado;
  - en el INSERT, claves distintas de las de la plantilla, porque el camino anterior las incluiría o daría error.

  Si la plantilla no se puede construir, todas las filas van por el camino anterior.
- **Medición** (`scratchpad/p06_bench.py`, 100K filas, 6 columnas, mejor de 3 intercalado, HEAD frente a nuevo):

  | 100K filas | Antes | Ahora | Mejora |
  |---|---|---|---|
  | INSERT | 10,08–10,85 s | 0,48–0,59 s | 17–22× |
  | UPDATE | 13,19–13,98 s | 0,48–0,59 s | 22–29× |
  | DELETE | 4,20–5,00 s | 0,10–0,12 s | 35–50× |

  Salida idéntica en SQLite, PostgreSQL (psycopg) y SQL Server (pyodbc).
- **Tests**:
  - `tests/unit/bulk/test_generate_sql_template.py` (13 tests × 8 combinaciones dialecto/driver = 104). Equivalencia exacta con la compilación por fila en:
    - INSERT, INSERT con `OVERRIDING SYSTEM VALUE` y UPDATE, con y sin binarios;
    - PK compuesta en UPDATE y DELETE, con registros de `df.to_dict` (tipos numpy);
    - `None` en el WHERE (`IS NULL`).
  - Del mismo fichero:
    - P-29 sin `RETURNING`/`OUTPUT`/`:ret_`;
    - `%(nombre)s` conservado en INSERT, UPDATE y DELETE;
    - claves distintas por el camino anterior;
    - ninguna fila sin binarios pasa por el camino anterior (espía).
  - Integración: `test_generated_insert_without_pk_runs_and_keeps_pyformat_text` (6 motores; con el código anterior fallan SQLite, PostgreSQL, SQL Server y Oracle).
  - Los tests de integración previos de SQL generado (P-20, P-23, P-25) pasan por el camino nuevo.
- **Incidencia de la suite completa (previa)**: el paquete de tests `tests/integration/metadata/mariadb/` (con `__init__.py`) se importa como módulo de primer nivel `mariadb` y tapa al driver. En la suite completa, `create_engine("mariadb+mariadbconnector://")` falla. La fixture del test nuevo salta ese dialecto con el motivo; en solitario se ejecuta. No se corrige aquí.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4701 passed / 177 skipped;
  - integración 6 motores 162 passed / 24 skipped.

## AUDIT_CODE
- Regresiones potenciales:
  - la salida cambia solo en los dos casos buscados: P-29 y `%(nombre)s`;
  - `render_literal_value` y `coerce_compared_value` son API de SQLAlchemy 2.0; un cambio de versión quedaría cubierto por los tests de equivalencia.
- Edge cases:
  - marcador presente en un identificador: la plantilla no se construye y todo va por el camino anterior;
  - JSON `None` → `NULL` (igual que antes);
  - valores numpy en DELETE: mismo tipo coercionado que antes.
- Rendimiento: con binarios sin renderizador, esas filas pagan el camino anterior (como antes). El fichero se sigue escribiendo con `"\n".join` (streaming, fuera de alcance).
- Compatibilidad: sin cambios de API.

## Directrices para Futuras IAs
- **[generar_sql]**: cualquier cambio en la generación de SQL debe mantener verdes los tests de equivalencia de `test_generate_sql_template.py` en los 8 dialectos. Si la salida debe cambiar, que sea explícito y con su propio test.
- **[tests]**: `tests/integration/metadata/mariadb/__init__.py` tapa al driver `mariadb` en la suite completa. Antes de concluir que un test del conector `mariadb` falla, ejecutarlo en solitario.
- **[SQLAlchemy]**: un `literal_column` en la PK de un INSERT activa RETURNING/OUTPUT. `Insert.inline()` lo evita sin cambiar el resto.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Siguientes del bloque: P-07 (bloques), P-08.
- Posible tarea aparte: renombrar el paquete de tests `tests/integration/metadata/mariadb` (o quitar su `__init__.py`) para que no tape el driver.
