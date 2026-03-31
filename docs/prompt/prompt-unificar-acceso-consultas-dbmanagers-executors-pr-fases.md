# Prompt: Unificar acceso a consultas (sync/async), crear Executors, refactor SRP y plan “PR por fase” (Python >= 3.12)

> Nota Fase 4 (2026-03-31): este prompt es material histórico de planificación. Debe leerse como contrato de análisis de una fase previa, no como descripción vigente del código; donde pide eliminar compatibilidad hacia atrás o presenta rutas legacy y wrappers como estado actual, la referencia viva hoy es README y docs/MIGRATION_GUIDE.md.

> Lectura actual: para managers y superficie pública, los imports canónicos recomendados parten de util_bbdd. Las menciones a database_manager.py, async_database_manager.py, database_queries.py o wrappers con fetch_one pertenecen al contexto histórico de la refactorización.

Eres un asistente senior de ingeniería de software especializado en arquitectura Python, refactors sin duplicación, diseño de APIs sync/async, testing con pytest (sin servicios externos), y mantenimiento de documentación de librerías. Tu tarea es diseñar y ejecutar (como plan accionable) una refactorización **sin compatibilidad hacia atrás** para unificar y modernizar el acceso a consultas SQL y sus metadatos.

## Alcance y repositorio (rutas relevantes)
- Consultas SQL centralizadas:
  - `src\util_bbdd\data\sql_queries.json`
- Tipos de base de datos + características/metadata:
  - `src\util_bbdd\data\database_types.json`
- Implementación actual (sync):
  - `src\util_bbdd\database_manager.py`
- Implementación actual (async):
  - `src\util_bbdd\async_database_manager.py`
- Métodos de conveniencia / “queries helpers”:
  - `src\util_bbdd\database_queries.py`
- Documentación (NO romper en el análisis histórico):
  - `src\util_bbdd\doc\database_documentation.py`
- Docs repo:
  - `README.md`
  - `CHANGELOG.md`

## Objetivo (requisitos obligatorios)
1) **Unificar el acceso de las consultas** definidas en `sql_queries.json` (hoy implementado en `database_manager.py`) y darle compatibilidad funcional a `async_database_manager.py`, **manteniendo** las características de información de `database_types.json`.
2) **Crear Executors** para la obtención/ejecución/resolve de consultas (separar “obtener query” vs “ejecutar query” vs “validar query”).
3) Analizar si los **métodos de conveniencia** en `database_queries.py` son útiles y si se pueden extraer a funcionalidades de **responsabilidad única**.
4) Debes soportar explícitamente las siguientes categorías de funcionalidad (sin duplicación y con SRP):
   - métodos de consulta básicos
   - métodos de información de consultas
   - métodos avanzados de validación (por tipo de BD)
   - métodos de metadatos
   - métodos de documentación
5) Verificar que **no se rompe nada** en `src\util_bbdd\doc\database_documentation.py` (si requiere cambios, que sean mínimos y justificados).
6) Actualizar `README.md` y `CHANGELOG.md` con:
   - decisiones
   - estado de soporte
   - lista de incompatibilidades (ya que no hay compatibilidad hacia atrás)
7) Manejo de errores: siempre que se capture una excepción y se relance, usar **`raise ... from err`**.
8) Mantener consistencia de **excepciones y logging** (un estilo, jerarquía de exceptions, mensajes claros, no “print”).
9) Agregar **tests unitarios** que cubran:
   - contratos (sync y async: mismos resultados para mismas entradas)
   - timeout
   - errores (wrap/raise from)
10) Tests por defecto **sin dependencias de servicios externos** (no BD real, no red). Usar mocks/fakes.
11) Entregar el plan en formato **“PR por fase”**:
   - Cada fase = un PR pequeño y revisable.
   - Checklist exacto por archivo (`src/...` y `tests/...`) listo para ejecutar por un agente de codificación.
12) Python objetivo mínimo recomendado: **3.12**.
13) No repetir código; cada clase/fichero debe tener **responsabilidad única**.

### Restricción clave
- **Sin compatibilidad hacia atrás** dentro de la propuesta histórica, pero debes **informar explícitamente** de incompatibilidades (imports rotos, firmas cambiadas, rutas de módulos, etc.).

---

# Entregable: Documento Markdown (estructura obligatoria)

## 1. Resumen ejecutivo
- Qué problema resuelve (unificación + async + SRP).
- Resultado final esperado (nueva API, ejecutores, tests, docs actualizadas).

## 2. Estado actual (inspección obligatoria)
Inspecciona y resume:
- Cómo `database_manager.py` obtiene/arma consultas desde `sql_queries.json`.
- Qué hace `async_database_manager.py` hoy y dónde diverge del sync.
- Qué información consume `database_types.json` y cómo se expone.
- Qué métodos provee `database_queries.py` (categorízalos: básicos/info/validación/metadatos/docs).
- Cómo `database_documentation.py` consume esas APIs (para no romperlo).

> Si faltan piezas, declara supuestos y lista archivos a revisar primero. No inventes firmas sin verificarlas.

## 3. Decisiones de diseño (ADR-style)
Incluye decisiones y justificación:
- **Un solo “Query Registry/Store”**: componente responsable de leer/validar `sql_queries.json` y entregar objetos “QueryDefinition”.
- **Ejecutores**:
  - `QueryResolver` (obtiene la consulta por nombre/clave + valida placeholders/params)
  - `SyncQueryExecutor` (ejecución sync)
  - `AsyncQueryExecutor` (ejecución async)
  - (si aplica) `ValidationExecutor` por motor/tipo de BD
- **Separación SRP**: qué queda en manager vs qué se mueve a executors vs qué se mueve a validators vs qué se mueve a docs/meta.
- **API pública**: qué clases/funciones quedan como entrada principal para consumidores.
- **Excepciones**:
  - jerarquía única (ej. `UtilBbddError`, `QueryNotFoundError`, `QueryValidationError`, `DatabaseTypeError`, `TimeoutError` propio si aplica)
  - estilo de mensajes y `raise ... from err`
- **Logging**:
  - logger por módulo `logging.getLogger(__name__)`
  - nivel recomendado y campos mínimos (query_name, db_type, elapsed_ms)
- **Timeouts**:
  - cómo se aplican en sync y async (por ejemplo, timeout en executor, o delegar al driver; tests con fake clock/mocks)

## 4. Modelo unificado de consultas y metadata
Define (en el documento) un modelo conceptual (y nombres sugeridos) para:
- `QueryDefinition` (id/nombre, sql template, params esperados, docstring, metadata)
- `DatabaseTypeDefinition` (desde `database_types.json`): capacidades, validaciones avanzadas, placeholders, etc.
- “QueryInfo” (métodos de información, documentación, metadata)

Incluye un mapa de correspondencia:
- `sql_queries.json` → `QueryDefinition`
- `database_types.json` → `DatabaseTypeDefinition`

## 5. “Prompt con cambios a realizar por motor” (obligatorio)
Aunque el foco aquí es el acceso a consultas, debes segmentar decisiones por **motor/tipo de BD** usando `database_types.json`.

Para cada motor (SQLServer, MariaDB, Oracle, HSQL, PostgreSQL, SQLite) define:
- Reglas de validación avanzadas (si ya existen, conservar; si están duplicadas, centralizar).
- Particularidades de placeholders (ej. `?`, `:name`, `%s`) si aplica.
- Si hay métodos específicos de conveniencia, decidir:
  - mantenerlos (pero extraídos a SRP)
  - eliminarlos (sin backward compat) y por qué
- Qué tests de contrato deben cubrir ese motor (sin BD real):
  - validación de placeholders
  - resolución de query y metadata
  - error si motor no soporta una feature declarada en `database_types.json`

> Restricción: si decides que algo NO es necesario para un motor, debes **descartarlo y justificarlo**.

## 6. Plan “PR por fase” (checklist exacto por archivo)
Divide el trabajo en PRs pequeños. Cada PR debe incluir:

- **Objetivo**
- **Cambios por archivo** (checklist con paths exactos)
- **Tests a agregar/modificar** (paths exactos)
- **Criterios de aceptación** (comandos + qué debe pasar)
- **Incompatibilidades introducidas** (lista concreta)

### PR 0 (Preparación)
Ejemplo de checklist (ajusta tras inspección real):
- [ ] `src/util_bbdd/...` crear módulo base de exceptions
- [ ] `tests/...` añadir estructura base y helpers de fakes/mocks
- [ ] Config pytest (`pyproject.toml` o `pytest.ini`) con markers

### PR 1 (Query Registry unificado)
- [ ] `src/util_bbdd/data/sql_queries.json` (si requiere normalización: justificar)
- [ ] `src/util_bbdd/query_registry.py` (nuevo)
- [ ] `tests/unit/test_query_registry.py`

### PR 2 (Executors sync)
- [ ] `src/util_bbdd/executors/sync_executor.py`
- [ ] `src/util_bbdd/database_manager.py` adaptado a usar registry + executor (sin duplicar lógica)
- [ ] `tests/unit/test_sync_executor_contract.py`

### PR 3 (Executors async)
- [ ] `src/util_bbdd/executors/async_executor.py`
- [ ] `src/util_bbdd/async_database_manager.py` adaptado (mismo contrato conceptual)
- [ ] `tests/unit/test_async_executor_contract.py`

### PR 4 (Validación avanzada por motor)
- [ ] `src/util_bbdd/validators/<motor>.py` (o estrategia por mapping desde `database_types.json`)
- [ ] `src/util_bbdd/data/database_types.json` (si necesita campos extra, justificar)
- [ ] `tests/unit/test_validators_by_motor.py`

### PR 5 (Refactor SRP de `database_queries.py`)
- [ ] `src/util_bbdd/database_queries.py` analizar, dividir, eliminar duplicados
- [ ] `src/util_bbdd/<nuevo_modulo_srp>.py` (si aplica)
- [ ] `tests/unit/test_queries_convenience.py` (solo si mantiene valor)

### PR 6 (No romper docs + actualizar README/CHANGELOG)
- [ ] `src/util_bbdd/doc/database_documentation.py` ajustar lo mínimo si cambió API (sin romper funcionalidad)
- [ ] `README.md` actualizar decisiones, nueva API, soporte
- [ ] `CHANGELOG.md` reflejar breaking changes e incompatibilidades
- [ ] `tests/unit/test_documentation_contract.py` (si se puede testear sin servicios externos)

> Nota editorial 2026-03-31: en la documentación viva actual ya no debe presentarse este prompt como checklist operativo vigente, sino como insumo histórico del corte de refactorización.

## 7. Tests requeridos (contrato, timeout, errores)
Define explícitamente:
- **Contrato sync vs async**:
  - dado el mismo query_name + params + db_type, resolver la misma SQL final y misma metadata (salvo partes claramente async).
- **Timeout**:
  - sync: simular operación lenta con mock y verificar `Timeout...` consistente
  - async: usar `asyncio.wait_for` o mock de awaitable lento, verificar exception y `raise ... from err` si se envuelve
- **Errores**:
  - query inexistente → `QueryNotFoundError`
  - params inválidos → `QueryValidationError`
  - db_type desconocido → `DatabaseTypeError`
  - al capturar un error interno (JSON decode, KeyError, etc.) → relanzar con `raise ... from err`

Restricción test:
- No usar BD real por defecto.
- Usar `pytest` + `unittest.mock` (o `pytest-mock` si ya existe; evitar nuevas deps si no son imprescindibles).

## 8. Consistencia de excepciones y logging (normas)
- Todas las capas (registry, resolver, executor, validators, managers) deben:
  - levantar exceptions de dominio coherentes
  - loguear con el mismo patrón
  - usar `raise ... from err` al traducir excepciones

Incluye una tabla “excepción → cuándo se levanta → capa responsable”.

## 9. Incompatibilidades (sin backward compat)
Lista obligatoria:
- Imports/paths que se eliminan/cambian.
- Firmas de métodos cambiadas.
- Cambios en nombres de keys/estructura esperada de JSON (si ocurre).
- Cambios en nombres de excepciones.

## 10. Checklist final de salida
- [ ] `pytest -q` pasa sin servicios externos
- [ ] Sync y async usan el mismo registry y no duplican lógica
- [ ] Validación avanzada por motor está centralizada y testeada
- [ ] `database_documentation.py` sigue funcionando
- [ ] README/CHANGELOG actualizados con decisiones y soporte
- [ ] No hay duplicación sustancial de código (DRY + SRP)

---

# Instrucciones de ejecución (para el agente)
1) Inspecciona primero estos archivos (en este orden):
   1. `src/util_bbdd/database_manager.py`
   2. `src/util_bbdd/async_database_manager.py`
   3. `src/util_bbdd/data/sql_queries.json`
   4. `src/util_bbdd/data/database_types.json`
   5. `src/util_bbdd/database_queries.py`
   6. `src/util_bbdd/doc/database_documentation.py`
2) Identifica API pública actual y puntos de extensión.
3) Propon la nueva API (sin backward compat) con SRP y sin duplicación.
4) Implementa por PRs (fases) siguiendo el checklist exacto por archivo.
5) Añade tests unitarios por contrato/timeout/errores.
6) Actualiza README/CHANGELOG al final (PR dedicado).

---

## Preguntas mínimas (máximo 5; solo si imprescindible)
1) ¿La ejecución de queries hoy incluye “render” de parámetros (string formatting) o solo devuelve templates para que el driver parametrice?
2) ¿Qué motores están realmente soportados hoy según `database_types.json` (todos o subset)?
3) ¿Se usa actualmente alguna lib async (asyncio, anyio) o solo existe un async manager wrapper?
4) ¿Se permite añadir dependencia `pytest-asyncio` si no existe?
5) ¿Formato de placeholders esperado por motor (si no está en JSON/actual code)?

Ahora: genera este documento completo en Markdown con decisiones, “prompt por motor”, y plan PR por fase con checklist exacto por archivo (`src/...` y `tests/...`), cumpliendo Python >= 3.12, sin backward compat (pero informando incompatibilidades), con manejo de errores `raise ... from err`, consistencia de exceptions/logging, y tests unitarios sin servicios externos.
