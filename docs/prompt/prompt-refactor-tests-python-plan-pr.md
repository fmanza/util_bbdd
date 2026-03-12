# Prompt: Refactorización de tests en un proyecto Python (pytest) + Plan de acción para PR

Eres un/a ingeniero/a senior especializado/a en calidad, testing en Python y optimización de suites de tests con **pytest**. Tu misión es **refactorizar la suite de tests** de este proyecto para mejorar **estructura, legibilidad, mantenibilidad y tiempos de ejecución**, sin perder señal.

## Objetivos (obligatorios)
1) **Optimizar estructura**
   - Reorganizar carpetas/módulos de tests con una convención clara.
   - Reducir duplicación (helpers/fixtures repetidos).
   - Nombres de tests consistentes y descriptivos.
   - Separar unit/integration/contract (si aplica).

2) **Optimizar ejecución**
   - Reducir tiempo total de `pytest`.
   - Hacer los tests más deterministas (evitar flakiness).
   - Mejorar la selección/filtrado: markers, subset por carpeta, etc.
   - Preparar la suite para CI rápido (sin dependencias externas si se puede).

3) **Plan de refactorización**
   - Presentar un plan por fases (iterativo).
   - Cada fase debe incluir: alcance, cambios, riesgos, y criterios de aceptación.

4) **Definir nombres de carpetas/módulos**
   - Tú defines la estructura final. Debe ser razonable y escalable.

## Restricciones
- No generar documentación extensa “histórica”; solo el plan y decisiones de refactor.
- Evitar introducir dependencias pesadas sin justificar.
- Mantener el suite ejecutable con un comando claro (por defecto `pytest -q`).

---

# Output requerido (documento Markdown)

## 1) Resumen ejecutivo
- Qué se va a mejorar (estructura + performance).
- Principios que guiarán la refactorización (alta señal, determinismo, no duplicación).

## 2) Estructura propuesta de tests (carpetas y módulos)
Propón un layout concreto. Por ejemplo (ajusta según el proyecto):
- `tests/unit/`  
- `tests/integration/`  
- `tests/contract/` (opcional)  
- `tests/e2e/` (opcional)  
- `tests/fixtures/` (opcional; si no, usar `conftest.py`)  
- `tests/helpers/` o `tests/_helpers.py`  
- `tests/conftest.py` (fixtures compartidas)

Incluye un árbol de ejemplo como:
```text
tests/
  conftest.py
  unit/
    test_<modulo>.py
  integration/
    test_<feature>.py
  helpers/
    factories.py
    asserts.py
```

## 3) Convenciones y estándares (decisiones)
Define reglas prácticas:
- Naming:
  - `test_<accion>_when_<condicion>_then_<resultado>`
- AAA pattern (Arrange-Act-Assert) o Given-When-Then
- Parametrización:
  - `@pytest.mark.parametrize` para evitar duplicación
- Fixtures:
  - `function` scope por defecto; `module/session` solo si reduce costo sin introducir acoplamiento
- Uso correcto de:
  - `tmp_path` (filesystem)
  - `monkeypatch` (env/config)
  - `caplog`, `capsys`
  - `pytest.raises`
- Qué NO se permite:
  - sleeps innecesarios
  - dependencias de orden entre tests
  - dependencias externas sin marker y sin opción de deshabilitarlas

## 4) Optimización de ejecución (tácticas)
Incluye tácticas concretas:
- Marcar tests:
  - `@pytest.mark.slow`
  - `@pytest.mark.integration`
- Configuración `pytest.ini` (o en `pyproject.toml`):
  - `--strict-markers`
  - `-q`
  - `testpaths = tests`
- Paralelización (si aplica y es seguro):
  - recomendar `pytest-xdist` con `-n auto` (solo si el repo lo soporta y lo justifica)
- Minimizar setup costoso:
  - cache de fixtures a `session` cuando sea determinista
  - fakes en memoria
- Control de tiempo:
  - congelar tiempo si es necesario (preferir `monkeypatch`/fake clock; `freezegun` solo si imprescindible)

## 5) Plan de refactorización por fases
Define un plan incremental que minimice riesgo. Ejemplo:

### Fase 0 — Auditoría e inventario
- Enumerar tests existentes y agrupar por “unidad bajo prueba”.
- Identificar:
  - duplicados por intención
  - flakiness
  - tests lentos
  - fixtures/Helpers duplicados
- Resultado: mapa de cambios + baseline de tiempos (si hay `--durations`).

### Fase 1 — Estructura y convenciones
- Crear/mover a nueva estructura (unit/integration/etc.).
- Establecer naming.
- Añadir markers y config base (`pytest.ini`).

### Fase 2 — Fixtures y deduplicación
- Consolidar fixtures en `tests/conftest.py`.
- Mover helpers repetidos a `tests/helpers/`.
- Parametrizar donde proceda.

### Fase 3 — Performance y determinismo
- Reemplazar sleeps por esperas deterministas.
- Aislar IO y usar `tmp_path`.
- Ajustar scopes de fixtures para reducir tiempo.
- (Opcional) xdist si es seguro.

### Fase 4 — Limpieza final y endurecimiento
- Eliminar tests redundantes/obsoletos (justificando con “está cubierto por X”).
- Activar `--strict-markers`.
- Asegurar que `pytest -q` pasa y que subsets por markers funcionan.

Para cada fase, incluye:
- Cambios concretos
- Riesgos
- Criterios de aceptación (DoD)

## 6) Plan de acción para PR (requerido)
Crea un “Plan de acción PR” con:
- Título del PR sugerido
- Alcance del PR (qué entra / qué no entra)
- Checklist de implementación:
  - [ ] mover estructura
  - [ ] introducir `pytest.ini` (o equivalente)
  - [ ] consolidar `conftest.py`
  - [ ] parametrizar
  - [ ] markers
  - [ ] reducir flakiness
  - [ ] medición de duración (`pytest --durations=20`)
- Checklist de revisión:
  - [ ] tests deterministas
  - [ ] tiempos en CI mejoran o al menos no empeoran
  - [ ] no se introducen dependencias innecesarias
- Comandos para validar:
  - `pytest -q`
  - `pytest -q -m "not integration"`
  - `pytest -q -m integration` (si existe)

## 7) (Opcional pero recomendado) Métricas y seguimiento
- Antes/después:
  - número de tests
  - duración total
  - top 20 tests más lentos
  - flakiness (si hay historial)
- Cómo medir:
  - `pytest --durations=20`
  - `pytest -q` en máquina limpia

## 8) Preguntas mínimas (máximo 5; solo si imprescindibles)
Si necesitas ajustar el plan, pregunta únicamente:
1) ¿Se usa pytest actualmente o unittest?
2) ¿Hay tests que dependan de BD/red/servicios externos?
3) ¿Se permite paralelizar en CI (xdist)?
4) ¿Tiempo objetivo en CI?
5) ¿Hay carpetas de tests fuera de `tests/`?

---

## Instrucciones finales
Ahora genera este documento (completo) adaptándolo al proyecto. Si no tienes detalles del repo, asume pytest y propón una estructura estándar. Debe ser accionable para abrir un PR de refactor de tests.