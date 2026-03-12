# Prompt: Normalizar `execute_query` / `execute_custom_query` (sync vs async), SRP/SOLID, limpieza y PR plan (sin backward compat)

Eres un asistente senior de ingeniería de software especializado en arquitectura Python, async/sync parity, refactors grandes sin duplicación, SOLID/Clean Code, y tests con pytest. Tu misión es revisar el proyecto y **normalizar** el acceso a consultas para que **Async y Sync funcionen igual**, eliminando duplicidad de responsabilidades (especialmente `execute_query` y `execute_custom_query`) y aplicando responsabilidad única.

## Contexto y archivos foco (obligatorio)
Debes analizar y proponer cambios, como mínimo, en:
- `src\util_bbdd\async_database_manager.py`
- `src\util_bbdd\database_manager.py`
- `src\util_bbdd\database_queries.py`
- `src\util_bbdd\executors\sync_query_executor.py`

Pero si es necesario para SRP y normalización, puedes revisar el resto del repo (con criterio).

## Problemas conocidos (debes abordarlos explícitamente)
1) `def execute_query` y `def execute_custom_query` aparecen en varios lugares (duplicidad por responsabilidad).
2) Diferencia de tipos de retorno:
   - Sync devuelve **listas** directamente.
   - Async devuelve **tuplas** y se usa `maybe_await` de `src\util_bbdd\async_utils.py`.
   - Objetivo: **obtener listas siempre y directamente** para ambos, salvo que justifiques por qué tuplas serían mejor (en cuyo caso, debes argumentarlo claramente: rendimiento, inmutabilidad, compatibilidad con drivers, etc., y proponer contrato consistente).
3) Normalizar todo el acceso a consultas: **Async y Sync deben tener la misma funcionalidad**, mismos nombres y semántica.
4) Aplicar **responsabilidad única** en todas las modificaciones (si hace falta, reorganiza módulos/clases).
5) Limpiar dependencias no usadas.
6) **Sin compatibilidad hacia atrás**:
   - puedes romper imports y firmas.
   - debes informar incompatibilidades y el impacto.

## Requisitos no negociables
- Diseño y arquitectura **SOLID**:
  - SRP, OCP, LSP, ISP, DIP donde aplique.
- **Legibilidad y Clean Code**:
  - nombres claros, módulos cohesivos, funciones pequeñas.
- Identificar **posibles bugs/errores ocultos** (tipos, awaits faltantes, mutabilidad de resultados, timeouts, manejo de excepciones, leaks de conexión).
- Cumplimiento **PEP 8** (y recomendar ruff/black si aplica; sin introducir deps innecesarias).
- Añadir **tests** que cubran cambios (unitarios + contrato sync/async).
- Documentar **impacto en la rama**:
  - qué se supone que hace la rama (según el estado actual) y si lo cumple tras el refactor.
- Considerar:
  - seguridad (logging de credenciales, SQL injection en custom queries, etc.)
  - rendimiento (materialización list vs tuple, streaming vs fetchall, pool usage)
  - dependencias (limpieza + compatibilidad)
  - migraciones (breaking changes)

---

# Entregable: Documento Markdown (estructura obligatoria)
Tu salida debe ser un documento Markdown completo con las siguientes secciones.

## 1) Resumen ejecutivo
- Qué se cambia y por qué.
- Resultado esperado: paridad sync/async, SRP, retorno consistente (lista o tupla, decisión justificada).

## 2) Estado actual (inspección obligatoria)
Inspecciona los 4 archivos foco y resume:
- Dónde están `execute_query` / `execute_custom_query`.
- Qué responsabilidades tienen hoy (resolver query, validar, ejecutar, transformar resultados, logging, errores).
- Diferencias entre sync y async (tipos retornados, uso de `maybe_await`, etc.).

Incluye una tabla:
- Archivo | Método | Responsabilidad actual | Problemas (duplicidad/SRP/bugs) | Propuesta

## 3) Decisiones clave (ADR-style)
Debes decidir y justificar:

### 3.1 Contrato de retorno: list vs tuple
- Preferencia solicitada: **lista siempre y directamente**.
- Si aceptas lista:
  - Define exactamente: `list[Row]` donde `Row` es `dict`/`tuple`/`Mapping` (según driver) y cómo se normaliza.
- Si propones tupla:
  - Justifica de forma técnica (inmutabilidad, performance, contract stability, menor copia).
  - Aun así debes mantener consistencia en ambos (sync y async) y eliminar `maybe_await` si ya no es necesario o encapsularlo.
- Define el contrato final con typing.

### 3.2 Dónde vive cada responsabilidad (SRP)
Define componentes (nombres sugeridos; ajusta al repo):
- `QueryCatalog/QueryRegistry` (obtención de SQL por nombre/clave desde JSON u origen).
- `QueryExecutor` (ejecución; NO decide qué query ejecutar).
- `ResultNormalizer` (convierte tuple→list, rows→estructura común, etc.).
- `DatabaseManager` (orquestación; composición de los anteriores).
- `DatabaseQueries` (si queda, que sea SRP: solo conveniencia de “query names” / wrappers finos).

### 3.3 Paridad sync/async
- Define “paired APIs”:
  - `SyncDatabaseManager` y `AsyncDatabaseManager` deben exponer los mismos métodos (nombres y semántica).
  - `SyncQueryExecutor` y `AsyncQueryExecutor` deben exponer el mismo set de operaciones (execute/fetch, etc.).
- Decide si compartir código:
  - Compartir solo lo “pure” (resolver query, validar inputs, normalizar resultados).
  - Evitar mezclar `asyncio` con sync.

### 3.4 Manejo de errores y logging
- Excepciones de dominio consistentes:
  - `UtilBbddError` base
  - `QueryExecutionError`, `QueryNotFoundError`, `InvalidQueryError`, `TimeoutError` etc.
- Reglas:
  - Al envolver excepciones: `raise ... from err`
  - Logging sin filtrar secretos (DSN, passwords)
  - Mensajes consistentes (incluye query_name, db_type, elapsed_ms si aplica)

### 3.5 Limpieza de dependencias
- Detecta imports no usados y dependencias declaradas innecesarias.
- Proponer cambios mínimos y verificables.

## 4) “Prompt con cambios a realizar por motor” (obligatorio)
Aunque la refactorización es transversal, debes describir implicaciones por motor (SQLServer, MariaDB, Oracle, HSQL, PostgreSQL, SQLite). Para cada motor incluye:

- **Estado actual**: cómo afecta hoy a `execute_query` / `execute_custom_query` (placeholders, cursor behavior, return types).
- **Decisión**: qué normalización aplica (por ejemplo: row shape, placeholder style, custom query allowed/validated).
- **Cambios**:
  - validación específica (si hay)
  - normalización de resultados (si un motor retorna algo distinto)
  - manejo de timeouts/errores específicos
- **Riesgos/bugs** detectables
- **Tests** por motor (sin DB real; con mocks/fakes):
  - contrato de retorno (list/tuple)
  - error wrapping `raise ... from err`
  - timeout simulado
  - custom query safety (si aplica)

Restricción: si una normalización o comportamiento no aplica a un motor, **descartarlo y justificar**.

## 5) Plan de acción en formato “PRs” (obligatorio)
Define PRs pequeños y revisables. Cada PR debe incluir checklist exacto por archivo y tests.

### PR 1 — Inventario + base de exceptions + contrato de retorno
Checklist:
- [ ] `src/util_bbdd/...` (nuevo) `exceptions.py` (jerarquía consistente)
- [ ] `src/util_bbdd/...` (nuevo) `result_types.py` (typing: Row/Rows)
- [ ] `tests/unit/test_contract_return_types.py`
- [ ] Ajustar `async_utils.maybe_await` si se encapsula o se reduce uso

Criterios de aceptación:
- `pytest -q` pasa
- contrato de retorno documentado en docstrings/types

### PR 2 — Extraer `ResultNormalizer` y eliminar diferencias list/tuple
Checklist:
- [ ] `src/util_bbdd/result_normalizer.py` (nuevo)
- [ ] `src/util_bbdd/executors/sync_query_executor.py` usa normalizer
- [ ] `src/util_bbdd/async_database_manager.py` usa normalizer (y decide si sigue necesitando maybe_await)
- [ ] `tests/unit/test_result_normalizer.py`
- [ ] `tests/unit/test_async_sync_parity_results.py`

Criterios:
- sync y async devuelven mismo tipo y estructura

### PR 3 — Unificar responsabilidades de `execute_query` / `execute_custom_query`
Checklist:
- [ ] Redefinir API pública: dónde quedan esos métodos (probablemente en Managers o Executors, pero no duplicados)
- [ ] `src/util_bbdd/database_manager.py` simplificar a orquestación SRP
- [ ] `src/util_bbdd/async_database_manager.py` equivalente async
- [ ] `src/util_bbdd/database_queries.py` refactor SRP (o eliminar si no aporta)
- [ ] `tests/unit/test_execute_query_contract.py`
- [ ] `tests/unit/test_execute_custom_query_contract.py`

Criterios:
- No existe duplicación de la misma responsabilidad en múltiples clases.
- Métodos sync/async tienen misma semántica.

### PR 4 — Paridad funcional completa + validaciones por motor
Checklist:
- [ ] `src/util_bbdd/validators/` (si aplica) validación de custom query / placeholders
- [ ] `tests/unit/test_validations_by_motor.py`
- [ ] `tests/unit/test_error_wrapping_raise_from.py`

Criterios:
- validación coherente y testeada por motor
- errores envueltos con `raise ... from err`

### PR 5 — Limpieza final (deps, PEP8, hidden bugs)
Checklist:
- [ ] eliminar imports no usados
- [ ] revisar posibles bugs (awaits, mutabilidad, pool leaks)
- [ ] ruff/format si está en el repo (sin añadir deps si no se requiere)
- [ ] `tests/unit/test_timeout_behavior.py` (mock de timeout)

Criterios:
- `pytest -q` pasa
- codebase más simple y coherente

## 6) Posibles bugs/errores ocultos (lista obligatoria)
Incluye hallazgos esperables a buscar en la inspección:
- Async devolviendo tuples por `fetchall()` y luego consumo inconsistentes (posible bug de callers).
- `maybe_await` aplicado donde no corresponde (doble-await o no-await).
- Excepciones atrapadas y relanzadas sin `from err` (pierde traceback).
- Logging de queries completas con datos sensibles.
- `execute_custom_query` permitiendo SQL injection sin validación mínima (si acepta interpolación).
- Fugas de conexiones: falta `close()` o `__aenter__/__aexit__`.
- Timeouts no aplicados realmente (solo parámetro ignorado).

## 7) Tests (requisitos mínimos)
Debes añadir tests unitarios (sin DB):
- Contrato de retorno (list/tuple) sync y async
- Paridad de API (mismos métodos expuestos) — opcional con introspección
- Timeout simulado:
  - sync: mock que bloquea o tarda; ver que se transforma en `TimeoutError` de dominio
  - async: awaitable que excede `asyncio.wait_for`
- Errores:
  - driver error → `QueryExecutionError` con `raise ... from err`
- Logging:
  - opcional: usar `caplog` para verificar que no se loguean secretos

## 8) Impacto en la rama + incompatibilidades
- Describe qué hace hoy la rama (según el código) y si lo cumple.
- Lista incompatibilidades concretas:
  - métodos renombrados o eliminados
  - rutas de imports modificadas
  - cambios de tipos de retorno
  - eliminación o encapsulación de `maybe_await`

## 9) Seguridad, rendimiento, dependencias, migraciones
- Seguridad:
  - reglas para `execute_custom_query` (validar que NO se interpolen strings con datos sin sanitizar; si se permite, advertirlo)
- Rendimiento:
  - coste de materializar list vs tuple (y por qué se elige)
  - evitar copias dobles (tuple->list) innecesarias, hacerlo en un solo punto
- Dependencias:
  - qué se elimina y cómo comprobar (pip check, import graph)
- Migración:
  - pasos mínimos para consumidores (en bullets)

---

# Instrucciones finales
1) Inspecciona los 4 archivos foco y busca todas las definiciones/variantes de `execute_query` / `execute_custom_query`.
2) Diseña la nueva arquitectura SRP con paridad sync/async.
3) Decide el contrato de retorno (preferido list) y aplícalo consistentemente.
4) Implementa el plan por PRs con checklist exacto por archivo y tests.
5) Reporta incompatibilidades (sin backward compat) y riesgos.

## Preguntas mínimas (máximo 5; solo si imprescindible)
1) ¿Se permite añadir `pytest-asyncio` si no existe?
2) ¿Qué representa una “row” hoy (tuple, dict, objeto)? ¿Hay un estándar interno?
3) ¿`execute_custom_query` permite params parametrizados o hace string formatting?
4) ¿Existen drivers async reales o el async actual envuelve sync?
5) ¿Timeouts se delegan al driver o se implementan en capa util_bbdd?

Ahora: genera el documento Markdown completo con decisiones, plan PR, “prompt por motor”, riesgos/bugs, PEP8, SOLID, y suite de tests propuesta, cumpliendo “sin compatibilidad hacia atrás” y sin dependencia de servicios externos en tests.