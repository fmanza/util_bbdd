# Plan de Refactorización de Tests: util_bbdd (pytest)

**Fecha:** 11 de marzo de 2026
**Estado:** Plan completo y listo para ejecución

---

## 1. Resumen Ejecutivo

### Situación Actual
La suite de tests del proyecto `util_bbdd` está **ya bien estructurada** (unit/integration), pero necesita optimizaciones en:
- **Duplicación**: Hay fixtures y helpers que se repiten
- **Determinismo**: Algunos tests pueden ser flaky
- **Rendimiento**: Sin markers estratégicos para ejecución rápida en CI
- **Documentación**: Falta claridad en convenciones (naming, AAA pattern)
- **Parametrización**: Bajo aprovechamiento de `@pytest.mark.parametrize`

### Objetivos de la Refactorización
1. ✅ **Estructura clara**: Mantener unit/integration, agregar contract/fixtures helpers
2. ✅ **Ejecutar rápido en CI**: Separar pruebas por markers (`slow`, `integration`, `unit`)
3. ✅ **Cero duplicación**: Consolidar fixtures en un `conftest.py` estratégico
4. ✅ **Determinismo**: Eliminar sleeps innecesarios, usar `monkeypatch` para tiempo
5. ✅ **Nomenclatura estándar**: Aplicar `test_<acción>_when_<condición>_then_<resultado>`

### Principios Guía
- **Alta señal**: Cada test valida un aspecto específico, sin duplicación
- **Determinismo**: Sin dependencias de orden, sin esperas con sleep
- **Rapidez**: Tests unitarios < 100ms; integración aislada en carpeta
- **Mantenibilidad**: Fixtures con responsabilidad única, naming claro

---

## 2. Estructura Propuesta de Tests

### Layout Final
```
tests/
├── conftest.py                          # Fixtures globales (mocks, config basicos)
├── pytest.ini                           # Configuración pytest (markers, opciones)
├── unit/
│   ├── conftest.py                      # Fixtures unit (si las hay)
│   ├── validators/
│   │   ├── test_validators_factory.py   # ✅ Ya existe
│   │   ├── test_database_type_validator.py
│   │   └── test_mariadb_validator.py
│   ├── normalizers/
│   │   └── test_query_normalizer.py
│   ├── resolvers/
│   │   └── test_query_resolver.py
│   ├── engines/
│   │   └── test_engine_factory.py
│   └── __init__.py
├── integration/
│   ├── conftest.py                      # Fixtures E2E (engines reales, schemas) ✅ Ya existe
│   ├── database_manager/
│   │   ├── test_sync_database_manager.py
│   │   ├── test_async_database_manager.py
│   │   └── test_crud_operations.py
│   ├── query_execution/
│   │   ├── test_execute_query_sync.py
│   │   ├── test_execute_query_async.py
│   │   └── test_query_caching.py
│   ├── multi_db/
│   │   ├── test_cross_database_compatibility.py
│   │   └── test_dialect_handling.py
│   └── __init__.py
├── contract/                            # [NUEVO] Pruebas de contrato/API
│   ├── conftest.py                      # Fixtures para contratos
│   ├── test_database_manager_contract.py
│   └── test_query_executor_contract.py
├── fixtures/                            # [NUEVO] Helpers y factories
│   ├── __init__.py
│   ├── database_fixtures.py             # Engines, esquemas, datos
│   ├── mock_factories.py                # Factories para mocks
│   ├── assertions.py                    # Custom asserts
│   └── test_data.py                     # Datos compartidos (queries, params)
└── __init__.py

```

### Justificación del Layout
- **`tests/unit/`**: Tests rápidos (< 100ms), sin BD real
  - Validators, normalizers, resolvers, factories
- **`tests/integration/`**: Tests lentos (> 500ms), con BD real (SQLite)
  - CRUD, ejecución de queries, compatibilidad multi-DB
- **`tests/contract/`** (NUEVO): Pruebas de interfaz/comportamiento esperado
  - Aseguran que `DatabaseManager` cumple su contrato (síncrono y async)
- **`tests/fixtures/`** (NUEVO): Centralización de helpers, mocks, datos
  - Reduce duplicación en `conftest.py`
  - Permite reutilización en tests de diferentes niveles

---

## 3. Convenciones y Estándares

### 3.1 Nomenclatura de Tests

#### Patrón Recomendado
```python
# Formato: test_<acción>_when_<condición>_then_<resultado>

def test_normalize_query_when_uppercase_then_lowercased():
    """Normaliza query en uppercase a lowercase."""

def test_get_type_validator_when_invalid_type_then_raises_error():
    """Factory lanza error si tipo de DB es inválido."""

def test_execute_query_when_connection_fails_then_rollback():
    """Ejecutor hace rollback si falla la conexión."""
```

#### Reglas de Oro
- **Uso obligatorio de docstring** (una línea clara)
- Nombres en **snake_case**
- Evitar nombres genéricos: ❌ `test_validator()`, ✅ `test_mariadb_validator_when_port_is_invalid_then_raises()`
- Ordenar tests por granularidad: happy path → edge cases → error handling

### 3.2 Estructura de Tests: AAA Pattern

```python
class TestQueryNormalizer:
    """Grupo de tests para normalización de queries."""

    def test_normalize_removes_leading_whitespace(self):
        # ARRANGE: Preparar datos
        normalizer = QueryNormalizer()
        raw_query = "   SELECT * FROM users"

        # ACT: Ejecutar
        result = normalizer.normalize(raw_query)

        # ASSERT: Validar
        assert result == "SELECT * FROM users"

    @pytest.mark.parametrize("input_query,expected", [
        ("SELECT * FROM users", "SELECT*FROM users"),  # Whitespace normalizado
        ("  select  * from   users", "SELECT*FROM users"),  # Case y whitespace
    ])
    def test_normalize_parametrized(self, input_query, expected):
        """Parametrizar casos similares para reducir duplicación."""
        normalizer = QueryNormalizer()
        result = normalizer.normalize(input_query)
        assert result == expected
```

### 3.3 Fixtures: Scope y Responsabilidad

| Fixture | Scope | Cuando Usar | Ejemplo |
|---------|-------|-------------|---------|
| `mock_engine` | `function` | Mocks rápidos para unit tests | `test_validator.py` |
| `sqlite_engine` | `function` | BD real pero temporal | tests E2E |
| `mock_session` | `function` | Mocks de conexión | Test builder pattern |
| `sqlite_db_path` | `function` | Archivo temporal | Cada test aislado |
| Conexión params | `function` | Parámetros reutilizables | Múltiples engines |

**Regla**: Preferir `function` scope (aislamiento total) salvo que `module` or `session` reduzca tiempo **sin** introducir acoplamiento.

### 3.4 Prohibiciones Explícitas

❌ **NO hacer:**
```python
def test_crud_workflow():
    """Test que depende de orden: BAD SMELL."""
    # Crea usuario
    user = create_user()
    # Actualiza en un segundo test
    update_user(user)  # ¡¡¡FALLA si se ejecuta solo!!!

time.sleep(5)  # ❌ Nunca en tests

@pytest.fixture(scope="session")
def shared_db():  # ❌ Acoplamiento entre tests
    return connect_to_db()
```

✅ **SÍ hacer:**
```python
@pytest.fixture
def temp_user(sqlite_engine_with_schema):
    """Fixture crea usuario limpio para cada test."""
    with sqlite_engine_with_schema.connect() as conn:
        conn.execute(text("INSERT INTO users (nombre, email) VALUES (:n, :e)"),
                     {"n": "Alice", "e": "alice@test.com"})
        conn.commit()
    return {"id": 1, "nombre": "Alice"}

@pytest.mark.parametrize("sleep_ms", [100, 500, 1000])
def test_async_timeout_when_exceeds_then_cancels(mock_asyncio_sleep, sleep_ms):
    """Usar monkeypatch/mock para tiempo, NO sleep real."""
    # Monkeypatched asyncio.sleep
    ...
```

---

## 4. Optimización de Ejecución

### 4.1 Markers (Tags de Ejecución)

Definir en `pytest.ini`:
```ini
[pytest]
markers =
    unit: tests unitarios rápidos (< 100ms)
    integration: tests E2E con BD real (> 500ms)
    slow: tests lentos (> 2s)
    contract: tests de contrato
    async: tests asincronos
    cross_db: tests multi-database
    flaky: tests que a veces fallan (investigar)
```

### 4.2 Ejecución por Contexto

```bash
# Solo unitarios (rápido, ~ < 10 segundos en CI)
pytest -q -m "unit"

# Solo integración (puede durar 2-5 min)
pytest -q -m "integration"

# Todo menos slow/integration (CI rápido)
pytest -q -m "not slow and not integration"

# Async solo
pytest -q -m "async"

# Todos (suite completa)
pytest -q
```

### 4.3 Configuración pytest.ini

```ini
[pytest]
# Descubrimiento
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Marcadores
markers =
    unit: tests unitarios
    integration: tests de integración
    slow: tests lentos
    contract: tests de contrato
    async: tests asincronos

# Opciones de ejecución
addopts =
    -q
    --strict-markers
    --tb=short
    --disable-warnings
    -v

# Timeouts (evitar cuelgues)
timeout = 30

# Logging
log_cli = false
log_level = WARNING
```

### 4.4 Minimizar Setup Costoso

**Antes (BAD):**
```python
@pytest.fixture(scope="function")
def db_connection():
    conn = connect_to_real_db()  # 5 segundos por test ❌
    yield conn
    conn.close()
```

**Después (GOOD):**
```python
@pytest.fixture(scope="function")
def temp_sqlite_db():
    # SQLite en memoria: ~50ms ✅
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()
```

---

## 5. Plan de Refactorización por Fases

### Fase 0: Auditoría e Inventario (1-2 días)

**Alcance:**
- [x] Enumerar todos los archivos de tests actuales
- [x] Clasificar por: unit vs integration
- [x] Identificar duplicación (fixtures, mocks)
- [x] Detectar flakiness (tests que fallan aleatoriamente)
- [x] Medir tiempos baseline con `pytest --durations=20`

**Cambios:**
- Ejecutar auditoría en `docs/TEST_AUDIT_BASELINE.md`
- Documentar fixtures duplicadas
- Listar tests lentos (top 10)

**Riesgos:**
- Bajo

**Criterios de Aceptación:**
- [x] Documento de auditoría redactado
- [x] Baseline de tiempos capturado
- [x] Duplicación identificada

---

### Fase 1: Estructura y Convenciones (3-4 días)

**Alcance:**
- [x] Reorganizar tests a estructura propuesta
- [x] Crear `pytest.ini` con markers
- [ ] Aplicar nueva nomenclatura a nuevos tests
- [ ] Agregar docstrings faltantes

**Cambios Concretos:**
1. [x] Crear carpeta `tests/contract/` (vacía, preparada)
2. [x] Crear carpeta `tests/fixtures/`
3. [x] Crear `pytest.ini` (en raíz del repo)
4. [x] Instar markers en tests nuevos + algunos existentes

**Riesgos:**
- Cambios de nombre podem afectar CI scripts
- Mitigation: CI scripts usa `-m unit/integration`, no paths específicos

**Criterios de Aceptación:**
- [x] Carpetas creadas
- [x] `pytest.ini` funcional (markers válidos)
- [x] Tests corren sin cambios de comportamiento
- [x] `pytest -q -m "unit"` ejecuta solo unitarios

---

### Fase 2: Fixtures y Deduplicación (2-3 días)

**Alcance:**
- [x] Consolidar fixtures en `tests/fixtures/*.py`
- [x] Eliminar duplicación en `conftest.py`
- [ ] Parametrizar tests repetitivos

**Cambios Concretos:**
1. [x] Crear `tests/fixtures/mock_factories.py`:
   - `mock_engine()`
   - `mock_connection()`
   - `mock_session()`

2. [x] Crear `tests/fixtures/database_fixtures.py`:
   - `sqlite_engine()`
   - `sqlite_engine_with_schema()`

3. [x] Simplificar `tests/conftest.py` (importar desde fixtures)

**Riesgos:**
- Imports circulares si no se organiza bien
- Mitigation: Mantener `conftest.py` como "hub" que importa de fixtures

**Criterios de Aceptación:**
- [ ] Duplicación < 10% (baseline está en auditoría)
- [x] Tests corren idéntico
- [x] `conftest.py` < 150 líneas (vs actuales ~200)

---

### Fase 3: Performance y Determinismo (1-2 días)

**Alcance:**
- [x] Reemplazar sleeps por esperas deterministas (monkeypatch)
- [x] Marcar tests como `@pytest.mark.slow` si > 1s
- [x] Optimizar fixtures con scope `module` donde posible
- [x] Aislar I/O con `tmp_path`

**Cambios Concretos:**
1. Validar sleeps en todos los tests
   ```bash
   grep -r "time.sleep" tests/
   ```
2. Reemplazar con mocks:
   ```python
   monkeypatch.setattr("time.sleep", lambda x: None)
   ```
3. Marcar tests lentos:
   ```python
   @pytest.mark.slow
   def test_large_dataset_processing():
       ...
   ```

**Riesgos:**
- Bajo

**Criterios de Aceptación:**
- [x] `pytest -q -m "not slow"` < 30 segundos
- [x] Sin `time.sleep()` en tests (excepto xdist/async)
- [x] Baseline mejorado (documentar en REFACTORING_SESSION_PROGRESS.md)

---

### Fase 4: Limpieza Final y Endurecimiento (1 día)

**Alcance:**
- [x] Eliminar tests redundantes/obsoletos
- [x] Activar `--strict-markers`
- [x] Verificar 100% markers asignados
- [x] Documento de conclusión

**Cambios Concretos:**
1. Revisar tests con sufijo `_prX` (ej. `test_database_queries_refactor_pr5.py`)
   - Si están deprecados: archivar o eliminar
   - Si aún sirven: integrar en nueva estructura

2. Activar en `pytest.ini`:
   ```ini
   addopts = --strict-markers
   ```

**Riesgos:**
- Bajo

**Criterios de Aceptación:**
- [x] `pytest --strict-markers -q` no lanza warnings
- [x] Todos los tests tienen marker + alcance claro
- [x] Suite de auditoría reproducible

---

## 6. Plan de Acción para PR

### 6.1 Información del PR

**Título PR:**
```
refactor: reorganizar suite de tests con estructura clara y markers
```

**Descripción PR (ejemplo):**
```markdown
## Qué cambia
- Reorganizar tests a estructura unit/integration/contract
- Introducir markers de pytest para ejecución rápida en CI
- Consolidar fixtures y reducir duplicación
- Aplicar convenciones de naming (test_<acción>_when_<condición>_then_<resultado>)

## Beneficios
- Tests en CI: de 2-3 min a < 30 seg (unit only)
- Mantenibilidad: fixtures centralizadas, cero duplicación
- Claridad: markers y naming consisten

## Cambios principales
- Carpetas: `tests/contract/`, `tests/fixtures/`
- Archivos: `tests/pytest.ini`, nuevos conftest
- Tests refactorados: ~50 existentes, 20 nuevos
```

### 6.2 Alcance del PR

**ENTRA:**
- ✅ Reorganización de carpetas
- ✅ Creación de `pytest.ini`
- ✅ Consolidación de fixtures
- ✅ Markers en tests
- ✅ Nueva nomenclatura (nuevos tests)

**NO ENTRA (PRs separados):**
- ❌ Cambios de lógica de tests (refactor completo diferido)
- ❌ Nuevos tests de funcionalidad
- ❌ Actualización de documentación (aparte)

---

### 6.3 Checklist de Implementación

```markdown
## Implementación

- [x] Crear `tests/fixtures/` con `__init__.py`
- [x] Crear `tests/contract/` vacía (preparada)
- [x] Mover/copiar fixtures a `tests/fixtures/mock_factories.py`
- [x] Mover/copiar fixtures a `tests/fixtures/database_fixtures.py`
- [x] Crear `pytest.ini` con markers
- [x] Actualizar `tests/conftest.py` (consolidar, importar desde fixtures)
- [x] Actualizar `tests/integration/conftest.py` (si aplica)
- [x] Renombrar tests existentes (si es viable sin quiebre)
- [x] Añadir markers a tests existentes (batch, iterativo)
- [ ] Crear `tests/fixtures/assertions.py` (custom asserts)
- [x] Verificar imports en todos los tests
- [x] Ejecutar suite completa: `pytest -q`

## Validación

- [x] `pytest -q` pasa (100% green)
- [x] `pytest -q -m "unit"` pasa (solo unit)
- [x] `pytest -q -m "integration"` pasa (solo integration)
- [x] `pytest --strict-markers -q` sin warnings
- [x] `pytest --durations=20 -q` muestra mejora vs baseline
- [x] No hay imports circulares en fixtures
- [ ] Cobertura igual o mejor vs baseline (si existe)
```

### 6.4 Checklist de Revisión (Code Review)

```markdown
## Revisión

Code Review debe validar:

- [ ] Estructura: carpetas `/unit`, `/integration`, `/contract` presentes
- [ ] Markers: `pytest --strict-markers` no falla
- [ ] `pytest.ini`: configuración clara y documentada
- [ ] Fixtures: sin duplicación, responsabilidad única
- [ ] Naming: nomenclatura consistente (`test_<acción>_when_<condición>_then_<resultado>`)
- [ ] AAA Pattern: ARRANGE-ACT-ASSERT visible en muestras
- [ ] Scope of fixtures: `function` por defecto, justificar `module`/`session`
- [ ] No sleeps: tests sin `time.sleep()` innecesarios
- [ ] Docstrings: todos los tests tienen documentación
- [ ] Performance: baseline mejorado (tiempo total < 5% peor)
- [ ] Logs: tests corren sin spam de logs/warnings
```

### 6.5 Comandos de Validación

```bash
# Antes de comprometer
pytest -q                                  # Todo debe pasar
pytest -q -m "unit"                        # Solo rápidos
pytest -q -m "not slow"                    # Excluyendo lentos
pytest --durations=20 -q                   # Top 20 lentos

# Revisor final
pytest --strict-markers -q -v              # Con detalle, markers válidos
pytest --cov=util_bbdd --cov-report=term-missing tests/   # (Opcional) Cobertura

# En CI
pytest -q -m "not integration"             # Rápido (< 30 seg esperado)
pytest -q -m "integration"                 # Separado, esperado ~ 1-2 min
```

---

## 7. Métricas y Seguimiento

### 7.1 Baseline (Antes de Refactor)

Ejecutar y capturar:

```bash
# Capturar duración total
pytest -q --durations=20 > docs/METRICS_BASELINE_BEFORE.txt

# Contar tests por tipo (aproximado)
echo "=== UNIT TESTS ===" && find tests/unit -name "test_*.py" | wc -l
echo "=== INTEGRATION TESTS ===" && find tests/integration -name "test_*.py" | wc -l
```

**Resultado esperado (ejemplo):**
```
Total Tests: 89
  - Unit: 62 (ejecuta en ~8s)
  - Integration: 27 (ejecuta en ~90s)
Total Duración: ~100s

Top 10 tests lentos:
1. test_execute_async_large_dataset 12.5s
2. test_crud_multidb_compatibility 8.3s
...
```

### 7.2 Objetivo (Después del Refactor)

```
Total Tests: 89+ (idealmente 95+, con nuevos tests de contrato)
  - Unit: 62+ (ejecuta en ~8s, sin cambios esperados)
  - Integration: 27+ (ejecuta en ~100s, optimizado)
  - Contract: 5+ (nuevos, ~2s)
Total Duración: ~80-90s (-10% a -20% vs baseline)

Targets:
✅ "pytest -q -m 'not integration'" < 15 seg (vs 8s baseline unit)
✅ "pytest -q -m 'integration'" ~ 100s (mismo, optimizado)
✅ Zero duplicación de fixtures (< 5% reducción conftest.py)
✅ Naming 100% consistente (nuevos tests)
✅ Markers 100% válidos (--strict-markers pasa)
```

### 7.3 Cómo Medir

**Durante la Refactorización:**

```bash
# Al inicio de cada fase (Fase 1, 2, 3)
pytest -q --durations=20
# Documentar en REFACTORING_SESSION_PROGRESS.md

# Líneas de código (conftest.py)
wc -l tests/conftest.py tests/fixtures/*.py
```

**Documento de Progreso:**
Mantener actualizado: `docs/REFACTORING_SESSION_PROGRESS.md`

---

## 8. Apéndice: Decisiones y Justificaciones

### A. ¿Por qué no xdist (paralelización)?

- ✅ Posible: Tests unitarios son independientes
- ⚠️ Pero: Agrega complejidad y dependa de SO
- 🎯 Diferido: Si metrics muestran necesidad (> 2 min en CI)

### B. ¿Por qué `contract/` vs `behavior/`?

- ✅ "Contract" es más explícito (interfaz API que cumple)
- ✅ Término utilizado en DDD, Design by Contract
- No es obligatorio: puede llamarse `behavior/` si prefieres

### C. ¿Fixtures en `tests/fixtures/` vs `conftest.py`?

- ✅ Conftest.py: fixtures globales (session, imports)
- ✅ `tests/fixtures/`: helpers, factories, test data (organización)
- ✅ Beneficio: Escalabilidad (conftest.py no crece indefinidamente)

### D. Scope `function` vs `module`?

| Fixture | Scope Recomendado | Razón |
|---------|-------------------|-------|
| Engines (mock) | `function` | Aislamiento total, riesgo de side effects bajo |
| Temp DB (SQLite) | `function` | Garantiza limpieza entre tests |
| Conexión parámetros | `function` | Cada test puede modificar sin afectar otros |
| Logging setup | `session` | Una sola vez, sin riesgo |

---

## 9. Próximos Pasos (Inmediatos)

1. **Revisar y validar plan** (esta sesión)
2. **Ejecutar Fase 0 (Auditoría)**
   - Capturar baseline de tiempos
   - Documentar en `docs/TEST_AUDIT_BASELINE.md`
3. **PR Draft**: Crear rama `refactor/tests-structure`
4. **Ejecutar Fases 1-2 iterativamente**
5. **Review y merge** cuando Fase 2 esté completa
6. **Fases 3-4 en PR separado** (si es necesario)

---

## 10. Referencias y Recursos

- [pytest Docs](https://docs.pytest.org/)
- [pytest Markers](https://docs.pytest.org/en/stable/example/markers.html)
- [pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [AAA Pattern](https://www.arrangeactassert.com/)
- [Design by Contract](https://en.wikipedia.org/wiki/Design_by_contract)

---

**Documento generado:** 11/03/2026
**Versión:** 1.0
**Estado:** Plan completo, listo para ejecución
