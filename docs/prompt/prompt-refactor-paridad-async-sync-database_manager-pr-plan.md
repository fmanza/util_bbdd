# Prompt: Refactor definitivo para paridad Async/Sync en Database Managers (SOLID, SRP, sin backward compat) + plan PR + cambios por motor

Eres un asistente senior de ingeniería de software especializado en arquitectura Python, diseño sync/async, refactors definitivos (no “fixes” temporales), y testing con pytest. Tu tarea es **revisar el proyecto actual** y **refactorizar** para que `src\util_bbdd\async_database_manager.py` tenga **exactamente la misma funcionalidad** que `src\util_bbdd\database_manager.py`, con una arquitectura SOLID, SRP y Clean Code.

## Objetivos (obligatorios)
1) **Paridad funcional total**:
   - `async_database_manager.py` debe exponer la misma funcionalidad (mismos casos de uso, métodos equivalentes, mismas validaciones y errores de dominio) que `database_manager.py`.
   - Misma semántica y mismos resultados, adaptados a async (await).

2) **Reutilización de código sin mezclar sync/async**:
   - Async y Sync deben ir por separado (módulos/clases separadas).
   - Aun así, debes buscar reutilización de código “pure” o compartible:
     - resolución/validación de consultas
     - normalización de resultados
     - tipados/DTOs
     - parsing de JSON/config
     - lógica de construcción de SQL o metadata
   - Prohibido duplicar lógica compleja entre ambos si se puede extraer.

3) **Soluciones definitivas**:
   - No “parches” ni “workarounds”.
   - No dejar TODOs.
   - No dejar APIs a medio migrar.
   - Si hay que rediseñar módulos, hazlo de forma completa.

4) **Sin compatibilidad hacia atrás**:
   - Se pueden romper imports, nombres de clases, firmas, ubicaciones de módulos.
   - Debes informar incompatibilidades y pasos mínimos de migración (bullets).

5) **Calidad y estándares**:
   - SOLID (especialmente SRP + DIP)
   - Clean Code (nombres claros, módulos cohesivos, complejidad baja)
   - PEP8 (y recomendar ruff/black si ya están en el repo; no metas deps innecesarias)
   - Seguridad: no loguear secretos, minimizar riesgo de SQL injection en custom queries, sanitización/parametrización
   - Rendimiento: pooling correcto, evitar copias inútiles, timeouts consistentes
   - Dependencias: limpiar lo no usado (imports y dependencias declaradas)
   - Migración: describir breaking changes (sin documentos largos extra)

6) **Tests obligatorios**
   - Añadir tests unitarios (y de contrato) que cubran:
     - paridad sync/async (mismos casos con el mismo input → output equivalente)
     - errores y wrapping (usar `raise ... from err`)
     - timeouts (mock, sin sleeps largos)
     - logging (opcional con `caplog`, especialmente no filtrar secretos)
   - Sin servicios externos en tests por defecto (no BD real, no red). Usar mocks/fakes.

---

## Alcance mínimo de inspección (obligatorio)
Debes inspeccionar al menos:
- `src\util_bbdd\database_manager.py`
- `src\util_bbdd\async_database_manager.py`

Y además, si lo requiere la reutilización/refactor definitivo:
- `src\util_bbdd\database_queries.py`
- `src\util_bbdd\executors\...` (sync/async)
- `src\util_bbdd\async_utils.py` (por ejemplo `maybe_await`)
- `src\util_bbdd\data\sql_queries.json`
- `src\util_bbdd\data\database_types.json`
- factories/pools/connections relacionadas

---

# Entregable: Documento Markdown (estructura obligatoria)

## 1) Resumen ejecutivo
- Qué cambia.
- Qué se elimina/rompe (por “sin backward compat”).
- Beneficios: paridad real, menos duplicación, SRP.

## 2) Estado actual y gap analysis (inspección)
- Lista de métodos/capacidades en `DatabaseManager` (sync).
- Lista de métodos/capacidades en `AsyncDatabaseManager` (async).
- Tabla de brechas:
  - Feature | Sync | Async | Gap | Plan de solución (extraer/reutilizar/reescribir)
- Identificar duplicidades (lógica repetida) y responsabilidades mezcladas.

## 3) Decisiones de arquitectura (ADR-style)
Debes tomar decisiones y justificarlas:

### 3.1 Contratos públicos (API final)
- Qué clases quedarán como punto de entrada sync y async (nombres exactos).
- Qué métodos expone cada una (lista exacta).
- Semántica: qué retorna cada método (tipos), cómo se manejan errores, timeouts.

### 3.2 Componentes SRP y reutilización segura
Define módulos/clases propuestos y su responsabilidad única, por ejemplo:
- `QueryRegistry` (carga/valida `sql_queries.json`)
- `DatabaseTypeRegistry` (carga/expone `database_types.json`)
- `QueryResolver` (elige query + valida params + motor)
- `ResultNormalizer` (shape de resultados, list/tuple, etc.)
- `SyncQueryExecutor` (ejecuta usando connection/pool sync)
- `AsyncQueryExecutor` (ejecuta usando connection/pool async)
- `SyncDatabaseManager` (orquesta; mínimo)
- `AsyncDatabaseManager` (orquesta; mínimo)

Reglas:
- Lo compartido debe ser “pure” (no IO, no await, no drivers).
- Sync/async en carpetas separadas (`executors/sync.py` y `executors/async_.py` o subpaquetes).

### 3.3 Errores y logging coherentes
- Jerarquía de excepciones única en `src/util_bbdd/exceptions.py`.
- Norma obligatoria: al traducir errores internos → `raise DomainError(...) from err`.
- Logging:
  - `logging.getLogger(__name__)`
  - nunca loguear passwords/DSN completos
  - incluir `db_type`, `query_name`, `elapsed_ms` si corresponde

### 3.4 Estrategia de timeouts
- Cómo se aplica timeout en sync y async de forma equivalente.
- Tests sin sleeps largos (usar mocks).

### 3.5 Seguridad y validación
- `execute_custom_query`:
  - ¿se permite? si sí, debe ser parametrizada y validada (evitar interpolación insegura).
  - si no aporta valor, se elimina (sin backward compat) y se justifica.
- Validación por motor (placeholders, sintaxis) guiada por `database_types.json`.

## 4) “Prompt con cambios a realizar por motor” (obligatorio)
Para cada motor (SQLServer, MariaDB, Oracle, HSQL, PostgreSQL, SQLite), define:

- **Estado actual** (cómo se conecta/ejecuta hoy, y diferencias sync/async)
- **Decisión**:
  - qué validaciones específicas se aplican
  - cómo se normalizan resultados
  - cómo se manejan particularidades (placeholders, fetch behavior)
- **Cambios**:
  - archivos/módulos a tocar o crear
  - ajustes de executor/manager/validators
- **Tests** (sin BD real):
  - contrato paridad sync/async
  - validación por motor
  - errores/timeouts

> Si decides que alguna validación o feature no aplica a un motor, debes **descartarla y justificar**.

## 5) Plan de acción “PR por fase” (obligatorio, estricto)
Divide en PRs pequeños con checklist exacto por archivo. Cada PR incluye:
- Objetivo
- Archivos a modificar/crear (paths exactos)
- Tests a añadir
- Criterios de aceptación (`pytest -q`, etc.)
- Incompatibilidades introducidas

### PR 1 — Inventario + contratos + exceptions base
Checklist:
- [ ] `src/util_bbdd/exceptions.py` (nuevo o refactor)
- [ ] `src/util_bbdd/types.py` (nuevos tipos/Protocol si aplica)
- [ ] `tests/unit/test_manager_api_parity_introspection.py` (paridad de métodos)
- [ ] `tests/unit/test_error_wrapping_raise_from.py`

Criterios:
- `pytest -q` pasa
- excepciones unificadas existen y se usan en un caso mínimo

### PR 2 — Extraer registries/resolvers compartidos (reutilización real)
Checklist:
- [ ] `src/util_bbdd/query_registry.py`
- [ ] `src/util_bbdd/db_type_registry.py`
- [ ] `src/util_bbdd/query_resolver.py`
- [ ] `tests/unit/test_query_registry.py`
- [ ] `tests/unit/test_query_resolver_by_motor.py`

Criterios:
- ambos managers pueden consumir el resolver sin duplicación

### PR 3 — Refactor SyncDatabaseManager para depender de componentes SRP (DIP)
Checklist:
- [ ] `src/util_bbdd/database_manager.py` simplificado (orquestación)
- [ ] `src/util_bbdd/executors/sync_query_executor.py` (o equivalente)
- [ ] `tests/unit/test_sync_manager_contract.py`

Criterios:
- sync funcionando con nueva arquitectura

### PR 4 — Implementar/Refactor AsyncDatabaseManager para paridad 1:1
Checklist:
- [ ] `src/util_bbdd/async_database_manager.py` reescrito o refactor (definitivo)
- [ ] `src/util_bbdd/executors/async_query_executor.py` (nuevo/refactor)
- [ ] `src/util_bbdd/async_utils.py` revisar `maybe_await` (eliminar si sobra o encapsular correctamente)
- [ ] `tests/unit/test_async_manager_contract.py`
- [ ] `tests/unit/test_async_sync_parity_same_inputs.py`

Criterios:
- misma funcionalidad (features) y resultados equivalentes
- sin duplicación de lógica compartible

### PR 5 — Limpieza, PEP8, dependencias, rendimiento y seguridad
Checklist:
- [ ] eliminar imports no usados
- [ ] revisar logging (no secretos)
- [ ] validar `execute_custom_query` (o eliminarlo)
- [ ] `tests/unit/test_timeout_behavior.py` (sync y async)
- [ ] `tests/unit/test_no_secret_logging.py` (opcional)

Criterios:
- `pytest -q` pasa
- decisiones de seguridad implementadas

## 6) Incompatibilidades (sin backward compat)
Lista obligatoria:
- Cambios de nombres/rutas de clases
- Firmas cambiadas
- Cambios en tipos devueltos
- Eliminación de métodos “convenience” o reubicación

Incluye “pasos mínimos de migración” en bullets (sin crear docs extra).

## 7) Riesgos / bugs ocultos a buscar (obligatorio)
- Divergencias de retorno (list vs tuple; shape de rows)
- `maybe_await` aplicado incorrectamente
- Fugas de pool/conexión (close missing, context managers mal usados)
- Timeouts no efectivos
- SQL injection en custom query (string formatting)
- Errores envueltos sin `from err` (pierde causa)
- Duplicación por motor (validators repetidos)

## 8) Suite de tests propuesta (obligatorio)
- Unit tests por componente SRP:
  - registry/resolver/validators/normalizer
- Contract tests:
  - paridad sync/async por feature (misma entrada → mismo output)
- Error/timeout tests:
  - mocks/fakes, sin servicios externos
- Marcadores:
  - `unit` por defecto
  - `integration` solo si se agrega y sin DB real (si no, no usar)

## 9) Checklist final (obligatorio)
- [ ] AsyncDatabaseManager = funcionalidad sync (paridad)
- [ ] SRP aplicado (clases pequeñas, cohesivas)
- [ ] DIP: managers dependen de abstracciones/servicios internos, no de detalles
- [ ] Sin duplicación sustancial entre sync y async
- [ ] `raise ... from err` aplicado al traducir excepciones
- [ ] PEP8 cumplido
- [ ] Tests pasan en CI sin servicios externos
- [ ] Lista de breaking changes incluida

---

## Preguntas mínimas permitidas (máximo 5; solo si imprescindible)
1) ¿Qué métodos exactos expone hoy `DatabaseManager` y cuáles faltan en `AsyncDatabaseManager`?
2) ¿El async actual usa driver async real o envuelve sync (thread executor)?
3) ¿Se permite añadir `pytest-asyncio` si no existe?
4) ¿Hay un contrato de “row” esperado (tuple/dict/objeto) por el resto del proyecto?
5) ¿`execute_custom_query` debe permanecer por requerimiento funcional o puede eliminarse?

Ahora: genera el documento completo en Markdown con decisiones, plan PR por fase, y cambios por motor, aplicando estrictamente SOLID/SRP, sin backward compatibility, con tests y consideraciones de seguridad/rendimiento/dependencias.
