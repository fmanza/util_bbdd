# Instrucciones de Copilot Chat para util_bbdd

## ⚠️ Notas importantes

**Lea primero**: [`.github/SHARED_INSTRUCTIONS.md`](.github/SHARED_INSTRUCTIONS.md) para arquitectura, SOLID, patrones, flujos y políticas comunes a ambas plataformas.

Esta página contiene **solo especificidades de Copilot Chat**. Todo lo demás está centralizado en SHARED_INSTRUCTIONS.md.

---

## Agentes VS Code

Usa estos agentes para orquestar el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION:

- **Workflow Director** — clasificar solicitud, validar contexto, elegir fase siguiente
- **Plan Architect** — preparar PLAN y AUDIT_PLAN, detectar riesgos
- **Feature Implementer** — ejecutar IMPLEMENT con alcance aprobado
- **Hotfix Responder** — RCA, fix mínimo, verificación
- **Code Auditor** — AUDIT_CODE de implementaciones
- **Security Reviewer** — auditoría de seguridad independiente
- **Documentation Reviewer** — auditoría de documentación, ejemplos, gaps
- **Config Reviewer** — auditoría de ficheros de configuración IA
- **Maturity Assessment** — evaluar madurez del repositorio
- **Version Closer** — cierre de versión, release notes
- **Explore** — exploración rápida, Q&A sin modificaciones

**Ver detalles completos**: [`.github/AGENTS.md`](.github/AGENTS.md) — matriz de herramientas, flujos y ejemplos de invocación.

---

## Flujos estructurados para Copilot Chat

### Flujo manual (sin slash commands)

Escribe en Copilot Chat siguiendo esta estructura:

```markdown
Voy a [implementar nueva funcionalidad / corregir un bug / refactorizar].

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

Contexto:
- Objetivo: [describe el objetivo final]
- Módulos: [lista módulos afectados]
- API: [describe cambios públicos, si aplica]
- Restricciones: [tiempo, breaking changes, etc.]

Primero: emite PLAN con rutas afectadas, componentes implicados, tipos y riesgos.
Luego: emite AUDIT_PLAN con riesgos funcionales/técnicos/seguridad y veredicto.
Después: IMPLEMENT por capas (Level 1 → 2 → 3) si veredicto es GO.
Finalmente: AUDIT_CODE con hallazgos y VERSION con commit + changelog.
```

### Referencias para Copilot Chat
- Mapeo Claude Code ↔ Copilot Chat: [`docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md`](../docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md)
- Ejemplos completos: [`docs/v0.6.7/COPILOT_CHAT_INTEGRATION_GUIDE.md`](../docs/v0.6.7/COPILOT_CHAT_INTEGRATION_GUIDE.md)
- Prompts por tarea: [`.github/prompts/`](.github/prompts/) — 9 prompts (new_feature, hotfix, refactor, etc.)

---

## Auditoría de código: Logging y Variables Globales

Cuando uses agentes de auditoría (Code Auditor, Security Reviewer, Documentation Reviewer) para revisar PRs:

### Checklist: Logging obligatorio

**Bloquea PR si:**
- ✗ Clase con lógica (servicios, managers, validadores) NO tiene `self.logger: logging.Logger`
- ✗ Logger no está instanciado en `__init__()` o `__post_init__()`
- ✗ `logging` importado pero sin tipado (debería ser `logging.Logger`)
- ✗ `print()` usado en lugar de logging en código de librería
- ✗ `error()` sin `exc_info=True` en exception handlers

**Verifica:**
- ✅ Mínimo 1 `self.logger.{debug|info|error}()` en métodos no triviales
- ✅ Métodos que mutan estado loguean con `info()` o superior
- ✅ Métodos que fallan loguean con `error(..., exc_info=True)`
- ✅ Niveles apropiados: `debug` (rastreo), `info` (eventos), `warning` (anómalos), `error` (fallos)

### Checklist: Variables Globales

**Bloquea PR si:**
- ✗ Variable global mutable a nivel de módulo (p.ej. `cache = {}`, `instances: list = []`)
- ✗ Singletons implementados vía módulo-level global
- ✗ Lazy loading con asignación global

**Permite:**
- ✅ Constantes inmutables: `MAX_RETRIES = 3`, `PATTERN: str = r"..."`
- ✅ ClassVar en clases: `class Config: TIMEOUT: ClassVar[int] = 30`
- ✅ Módulo-level logger: `logger: logging.Logger = logging.getLogger(__name__)`
- ✅ Inyección de dependencias en constructores

### Checklist: F-Strings OBLIGATORIOS

**Bloquea PR si:**
- ✗ String con parámetros usa `.format()`: `"Processing {} records".format(count)` ❌
- ✗ String con parámetros usa `%` formatting: `"Expected %s rows" % expected` ❌
- ✗ String con parámetros usa concatenación: `"Table " + name + " (" + str(rows) + ")"`  ❌

**Requiere:**
- ✅ F-string para todo string con parámetros: `f"Processing {count} records"`
- ✅ F-string en logging: `logger.info(f"Records: {len(data)}, timeout: {timeout}s")`
- ✅ F-string en mensajes de error: `error_msg = f"Expected {expected} rows, got {actual}"`

**Permite (strings sin parámetros):**
- ✅ Strings estáticos: `"Inicializando conexión"`
- ✅ Docstrings con ejemplos
- ✅ Constantes documentales

### En IMPLEMENT: Integración

Si encuentras violaciones de logging/variables globales, propón refactor junto con feature:
```markdown
**Logging gaps encontrados en [module]:**
- Clases sin logger: ClassA, ClassB, ClassC
- Propuesta: Añadir `self.logger` en __init__ + 2-3 logs por clase

**Variables globales detectadas en [module]:**
- [global_var]: mutable dict
- Propuesta: Convertir a ClassVar o inyectar en __init__
```

---

## Respuesta en markdown estructurado

- Usa markdown con secciones claras: `## Sección`, `### Subsección`
- Código en bloques con lenguaje: ` ```python`, ` ```sql`
- Listas con viñetas y sub-viñetas
- Tablas para comparaciones o matrices
- No confundas `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE`, `VERSION` — son fases distintas

---

## Auditoría de Documentación

### Documentation Reviewer Agent (Detallado)

**Cuándo usar:**
- Antes de release/versión
- Tras cambios significativos de API
- Para auditar documentación existente (gap analysis)
- Para validar ejemplos en código

**Qué verifica:**

#### 1. Mapeo de Estado Actual
```markdown
**Reporte esperado:**
- 📋 README.md: Status (✅ completo / ⚠️ incompleto / ❌ faltante)
- 📋 INSTALLATION.md: Status
- 📋 API_REFERENCE.md: Status + cobertura (%)
- 📋 docs/examples/: Estado de ejemplos
- 📋 Docstrings: % cobertura por módulo
```

#### 2. Identificar Ejemplos Faltantes
```markdown
**Por módulo:**
- Module A: 3/5 clases sin ejemplo → CRÍTICO
- Module B: docstrings incompletos → ALTO
- Module C: ejemplo obsoleto (v0.5) → MEDIO

**Reporte esperado:**
- Listado de qué falta
- Dónde debe agregarse (docstring vs docs/examples/)
- Complejidad (breve vs extenso)
```

#### 3. Detectar Gaps Críticos
```markdown
**Ejemplos de gaps:**
- ❌ No hay guía de "Primeros Pasos"
- ❌ Módulo 'comparar' sin ejemplo de uso
- ❌ API de conexión sin troubleshooting
- ⚠️ Links rotos en 3 archivos
- ⚠️ Ejemplos usando API v0.5 (actualizar a v0.6)
```

#### 4. Backlog Priorizado
```markdown
**P0 - BLOQUEADOR (arreglar antes de release):**
- Docstring missing en 5 clases públicas
- mkdocs build fallando (links rotos)

**P1 - IMPORTANTE (hacer en próxima iteración):**
- Agregar 3 ejemplos complejos
- Migrar docs a mkdocs-material

**P2 - MEJORA (cuando haya tiempo):**
- Mejorar README con tabla de features
- Agregar gifs/screenshots
```

---

### Cómo Invocar Documentation Reviewer

**Desde Copilot Chat:**

```markdown
@documentation-reviewer

Auditoría completa de documentación de util_bbdd.

Mapear:
1. Estado actual (README, guías, docstrings, ejemplos)
2. Ejemplos faltantes por módulo público
3. Gaps críticos vs mejoras recomendadas
4. Backlog priorizado

Alcance: Todos los módulos en src/util_bbdd/
Formato: Reporte estructurado con recomendaciones específicas
```

**Resultado esperado:**
```
# Audit Report: util_bbdd Documentation

## 1. State Mapping
- ✅ README.md: Complete
- ⚠️ API_REFERENCE.md: 60% coverage
- ❌ Troubleshooting.md: Missing

## 2. Examples Gap
- Module managers: 3 classes without examples
- Module comparar: Missing end-to-end example

## 3. Critical Gaps
- No migration guide for v0.5 → v0.6
- Connection troubleshooting not documented

## 4. Backlog
[P0, P1, P2 items with specific actions]
```

---

## Checklist de Documentación en AUDIT_CODE

### Cuándo Verificar Documentación

**En toda auditoría de código (`/audit-code`), agregar checklist:**

```markdown
## Documentation Checklist (parte de AUDIT_CODE)

### Docstrings
- [ ] ¿Cada clase/función pública tiene docstring?
- [ ] ¿Docstring tiene Args, Returns, Raises?
- [ ] ¿Cada docstring tiene 1+ Example?
- [ ] ¿Los ejemplos son ejecutables (sintaxis válida)?

### Ejemplos
- [ ] ¿Ejemplos coinciden con código actual (no obsoletos)?
- [ ] ¿API nueva tiene ejemplo en docs/examples/?
- [ ] ¿Hay inconsistencia entre ejemplo en docstring y código?

### mkdocs
- [ ] ¿`mkdocs build` completa sin errores?
- [ ] ¿Sin warnings de links rotos?
- [ ] ¿Nueva clase/módulo tiene entry en mkdocs.yml?
- [ ] ¿API_REFERENCE.md actualizado?

### Deprecación (si aplica)
- [ ] ¿Cambio de API tiene guía de migración?
- [ ] ¿Código deprecated tiene aviso (deprecated_since=...)?
- [ ] ¿Hay CHANGELOG entry?

### Reporte de Hallazgos

**Si encuentra gaps, reportar como:**

✅ PASS:
```
Documentación completa:
- Docstrings: 100% cobertura
- Ejemplos: Todos ejecutables
- mkdocs: Sin warnings
```

⚠️ WARNING:
```
Documentación incompleta:
- 2 métodos sin ejemplo en docstring
- Propuesta: Agregar ejemplos en [ClassA, ClassB]
```

❌ FAIL (bloquea PR):
```
Documentación insuficiente:
- Clase pública SIN docstring
- mkdocs build fallando (3 links rotos)
- Cambio de API SIN guía de migración

Acción requerida: [específica]
```
```

---

## Criterios de Hallazgos Críticos

### Qué Bloquea un PR (Documentation)

| Hallazgo | Severidad | Acción |
|---|---|---|
| Clase/función pública SIN docstring | 🔴 CRÍTICO | Rechazar PR |
| Docstring sin Args/Returns/Example | 🟠 ALTO | Rechazar PR |
| Cambio de API pública sin migración | 🔴 CRÍTICO | Rechazar PR |
| mkdocs build falla (links rotos) | 🔴 CRÍTICO | Rechazar PR |
| Ejemplos usando API vieja (v0.5+) | 🟠 ALTO | Pedir update |
| Ejemplo en docstring pero no ejecutable | 🟠 ALTO | Pedir fix |
| Módulo nuevo sin entry en mkdocs | 🟠 ALTO | Pedir agregar |
| Inconsistencia: ejemplo ≠ código | 🟠 ALTO | Pedir actualizar |
| mkdocs warnings (minor) | 🟡 MEDIO | Recomendar fix |
| Typos en docstring | 🟢 BAJO | Nice to have |

---

## Integración con Otros Agentes

### Flujo: Feature Implementation + Documentation

```markdown
Workflow:

1. Plan Architect
   → Identifica si es cambio de API pública

2. Feature Implementer
   → Implementa feature
   → DURANTE: Escribe docstrings + ejemplos

3. Code Auditor
   → Verifica lint/type/tests
   → INCLUYE: Checklist documentación (arriba)

4. Documentation Reviewer (si es complejo)
   → Audita si documentación es adecuada
   → Propone mejoras

5. Version Closer
   → Actualiza CHANGELOG
   → Verifica mkdocs es publicable
```

---

### Flujo: Documentación Inicial (Pre-Release)

```markdown
Para v0.7.0 o próxima release:

1. Usa Documentation Reviewer
   → Auditar estado completo

2. Plan Architect
   → Crear backlog de doc improvements
   → Priorizar (P0 bloqueador, P1 importante, P2 nice-to-have)

3. Feature Implementer
   → Ejecutar P0 items

4. Code Auditor
   → Validar que P0 items están completos

5. Version Closer
   → Verifica mkdocs final
   → Publica a GitHub Pages
```

---

## Estándares de Documentación

### Format: Google-Style Docstrings

**Requerido en todo código público:**

```python
class Example:
    """Una línea: descripción breve.

    Párrafo 1 (opcional): Descripción detallada, comportamiento, restricciones.

    Attributes:
        attr1 (str): Descripción del atributo

    Example:
        >>> obj = Example()
        >>> obj.method()
        'result'
    """

    def method(self, param1: str) -> str:
        """Breve descripción.

        Args:
            param1: Descripción, tipo, restricciones.

        Returns:
            str: Descripción de lo que retorna.

        Raises:
            ValueError: Cuándo se lanza.

        Example:
            >>> obj.method("input")
            'output'
        """
```

---

## Ejemplo: Completo Audit Report (Documentation)

```markdown
# Code Audit: util_bbdd.managers._metadata_request

## ✅ Passes

- [x] All public classes have docstrings
- [x] All docstrings have Examples
- [x] Examples are executable
- [x] mkdocs entry present
- [x] No broken links

## ⚠️ Warnings

- [ ] 1 docstring missing Args (MetadataFetchRequest.table_name)
  Suggestion: Document parameter constraints

## 🔴 Critical

None.

## Summary

Documentation: ✅ PASS
Action: Merge-ready

---

## Other Findings

- mkdocs serve: runs without warnings
- 3 similar examples could be consolidated → P2 nice-to-have
```

---

*Actualizado: 2026-04-20 — Auditoría de Documentación + Documentation Reviewer Agent + Criterios de Hallazgos agregados*
