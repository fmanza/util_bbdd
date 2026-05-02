# Ejemplo completo de uso de Codex

## Resumen

Este documento muestra, con ejemplos completos y realistas, cómo se trabaja en este repositorio con **Codex** (extensión de OpenAI para VS Code).

Cubre:

- cómo Codex detecta el contexto del repositorio automáticamente
- cuáles son los archivos de configuración relevantes
- flujo de trabajo estructurado (similar a Claude Code)
- políticas aplicadas a Codex
- actualización de documentación con MkDocs, Mermaid y ejemplos verificables
- ejemplos completos por caso de uso
- diferencias con Claude Code y Copilot Chat

Para la configuración equivalente de Claude Code, consulta [claude_code_usage_complete_example.md](claude_code_usage_complete_example.md).
Para la configuración de Copilot Chat, consulta [github_usage_complete_example.md](github_usage_complete_example.md).

---

## Configuración de Codex para este repositorio

### Archivos que Codex puede leer automáticamente

| Archivo | Propósito |
|---|---|
| [../../CLAUDE.md](../../CLAUDE.md) | Instrucciones transversales para asistentes de código en este repositorio |
| [../../.github/SHARED_INSTRUCTIONS.md](../../.github/SHARED_INSTRUCTIONS.md) | Arquitectura, SOLID y políticas comunes |
| [../../.github/AGENTS.md](../../.github/AGENTS.md) | Registro de agentes y flujos especializados |
| [../../pyproject.toml](../../pyproject.toml) | Versión, Python soportado, herramientas reales |
| [../../.claude/settings.json](../../.claude/settings.json) | Hooks y permisos de desarrollo |
| [../../.github/instructions/](../../.github/instructions/) | Reglas por ruta o tipo de archivo |

### Cómo Codex funciona en este repositorio

1. **Carga inicial**: Codex lee `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md` y entiende el contexto de `util_bbdd`
2. **Validación de contexto**: Contrasta el código real con lo que ve en las instrucciones
3. **Edición manual**: Realiza cambios acotados con parches pequeños
4. **Verificación**: Ejecuta tests relevantes para validar

### Diferencia con Claude Code

| Aspecto | Codex | Claude Code |
|---|---|---|
| Slash commands | No aplica | Sí, `/new-feature`, `/hotfix`, etc. |
| Flujo estructurado | Manual o implícito | Obligatorio por comando |
| Contexto por defecto | Lee instrucciones del repositorio + el código real | Lee `CLAUDE.md` + comandos |
| Salida esperada | Código y cambios acotados | Salida estructurada (PLAN → VERSION) |
| Auditoría integrada | No | Sí, con `/audit-code` |
| Punto de entrada | `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md` | `CLAUDE.md` |

---

## Cómo trabajar con Codex

### Paso 1: Formulación clara de la tarea

Abre Codex y describe la tarea con alcance concreto:

```text
Trabaja sobre util_bbdd.

Objetivo: [describe el cambio]
Alcance: [rutas o módulos]
Restricciones: [compatibilidad, no refactor, docs, etc.]

Primero revisa `.github/SHARED_INSTRUCTIONS.md` y el código real.
Después implementa con cambios acotados y ejecuta tests relevantes.
```

**Ejemplo real**:

```text
Objetivo: añadir una validación explícita para formatos no soportados en DatabaseDocumentation
Alcance: src/util_bbdd/doc/database_documentation.py, tests/unit/test_database_documentation.py
Restricciones:
  - Compatibilidad hacia atrás con API existente
  - No refactorizar la arquitectura de renderers
  - Docs en docstrings y ejemplos
```

### Paso 2: Trabajo incremental

Codex debe:

1. **Leer el código real** — no inventar módulos
2. **Hacer cambios pequeños** — parches específicos, no refactors
3. **Respetar la arquitectura** — managers, comparadores, renderers, facades y adaptadores
4. **Validar con tests** — ejecuta tests unitarios relevantes

Ejemplo de cambio acotado:

```python
# doc/database_documentation.py
def generate(self) -> None:
    """Genera la documentación configurada en los formatos solicitados.

    Raises:
        ValueError: Si la lista de formatos contiene un valor no soportado.

    Example:
        >>> documentation = DatabaseDocumentation(db_manager, formatos=["html"])
        >>> documentation.generate()
    """
```

### Paso 3: Verificación

Después de cada cambio:

```bash
# Lint
python -m ruff check src tests

# Type check
python -m mypy src

# Tests relevantes
python -m pytest tests/unit/test_database_documentation.py -v
```

Si algún comando falla, Codex corrige antes de continuar.

---

## Criterios de cierre

Antes de terminar, Codex debe:

- ✅ Actualizar documentación si cambia CLI, API pública o archivos generados
- ✅ Si cambia documentación publicada, sincronizar `mkdocs.yml` y mantener separados los apartados funcionales, técnicos y ejemplos
- ✅ Sincronizar instrucciones IA si cambian reglas comunes
- ✅ Ejecutar pruebas relevantes o explicar por qué no se ejecutaron
- ✅ Resumir archivos modificados y comportamiento verificado

---

## Ejemplos completos

### Ejemplo 1. Cambio en un servicio

**Solicitud a Codex**:

```text
Trabaja sobre util_bbdd.

Objetivo: permitir que SchemaComparator normalice el nombre de dialecto SQL Server como mssql al resolver routines
Alcance: src/util_bbdd/comparar/comparator.py, tests/comparar/test_comparator.py
Restricciones: cambios mínimos, mantener la API pública

Revisa el código actual y propón la validación. Luego ejecuta tests relevantes.
```

**Flujo esperado de Codex**:

1. Lee `src/util_bbdd/comparar/comparator.py`
2. Identifica `SchemaComparator` y el mapa `_DB_TYPE_TO_DIALECT`
3. Propone una validación o ajuste acotado del dialecto
4. Actualiza tests en `tests/comparar/test_comparator.py`
5. Ejecuta `python -m pytest tests/comparar/test_comparator.py -v`
6. Resume: "Validación añadida. Tests relevantes pasan. API pública sin cambios."

### Ejemplo 2. Fix de bug acotado

**Solicitud a Codex**:

```text
Trabaja sobre util_bbdd.

Objetivo: corregir que SyncDatabaseManager acepte un db_type con espacios sin normalización previa
Alcance: src/util_bbdd/managers/sync_mgr.py
Restricciones: solo fix mínimo, sin refactor

Después, verifica con tests.
```

**Flujo esperado de Codex**:

1. Lee el código afectado
2. Identifica dónde se normaliza y valida `db_type`
3. Añade lógica de validación simple
4. Añade test que valide el comportamiento
5. Ejecuta tests: `pytest tests/unit/test_sync_executor_contract.py -v`
6. Resume cambios y cierra

### Ejemplo 3. Crear o actualizar documentación

**Solicitud a Codex**:

```text
Trabaja sobre util_bbdd.

Objetivo: actualizar la documentación de DatabaseDocumentation.
Alcance: README.md, docs/, docs/examples/, mkdocs.yml
Restricciones:
- no refactorizar código existente
- no inventar capacidades, parámetros ni salidas
- excluir generación mediante APIs externas

Incluye apartados funcionales, técnicos y un ejemplo de funcionamiento verificable.
Actualiza mkdocs.yml si creas o mueves páginas.
```

**Flujo esperado de Codex**:

1. Lee `src/util_bbdd/doc/database_documentation.py`
2. Lee `README.md`, `docs/`, `docs/examples/` y `mkdocs.yml`
3. Decide si actualiza una página existente o crea una nueva
4. Separa claramente documentación funcional, técnica y ejemplo de uso
5. Usa Mermaid solo si el flujo se infiere del código real
6. Verifica que los ejemplos sean ejecutables o marca lo pendiente de verificación
7. Ejecuta `mkdocs build` si el entorno lo permite
8. Resume cambios en documentación y navegación

### Ejemplo 4. Auditoría independiente (requiere intervención del usuario)

Si quieres que Codex audite sin escribir código:

```text
Trabaja sobre util_bbdd.

Objetivo: revisar la clase DatabaseDocumentation
Alcance: src/util_bbdd/doc/database_documentation.py
Quiero: bugs potenciales, edge cases de configuración, validaciones de formatos y tests insuficientes

NO escribas código. Solo analiza.
```

**Salida esperada**:

- Lista de hallazgos potenciales
- Edge cases identificados
- Recomendaciones

---

## Integración con el flujo de desarrollo

### Flujo recomendado

```
Usa Codex para → cambios acotados en código, tests, documentación
Usa Claude Code para → PLAN/AUDIT_PLAN/IMPLEMENT/AUDIT_CODE/VERSION (flujos complejos)
Usa Copilot Chat para → consultas rápidas, exploración, orientación
```

### Cuándo prefieres a cada uno

| Tarea | Mejor opción | Razón |
|---|---|---|
| Cambio pequeño en 1-2 archivos | Codex | Rápido y directo |
| Nueva feature compleja | Claude Code | Flujo estructurado, auditoría |
| Pregunta rápida sobre código | Copilot Chat | Conversación natural |
| Auditoría de seguridad | Claude Code + Security Reviewer | Especialización dedicada |
| Documentación puntual | Codex | Actualización acotada con `mkdocs.yml` |
| Documentación de proyecto completo | Documentation Generator o Claude Code | Inventario, secciones funcional/técnica/ejemplos y revisión final |

---

## Comandos útiles referenciados

```bash
# Lint — verificar estilo
python -m ruff check src tests

# Format — aplicar formato automático
python -m ruff format src tests

# Type-check — verificar tipos
python -m mypy src

# Tests — ejecutar todas las pruebas
python -m pytest

# Tests específicos — enfoque en módulo
python -m pytest tests/unit/services -q

# Build — empaquetar
python -m build

# Documentación local
mkdocs serve
mkdocs build
```

---

## Resumen de diferencias

| Herramienta | Mejor para | Entrada principal |
|---|---|---|
| **Codex** | Cambios pequeños, acotados, verificables | Descripción clara + código real |
| **Claude Code** | Features complejas, flujos estructurados | `/command` + `CLAUDE.md` |
| **Copilot Chat** | Consultas, orientación, exploración | Preguntas naturales + `copilot-instructions.md` |
| **Agentes de Copilot** | Roles especializados, auditoría | Selección de agente + instrucciones |

---

*Actualizado: 2026-04-28*
