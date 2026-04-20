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

*Actualizado: 2026-04-18 — Config Reviewer audit*
