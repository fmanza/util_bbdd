# Ejemplo completo de uso de `.github`

## Resumen

Este documento muestra, con ejemplos completos y realistas, cómo se usa lo definido en la carpeta [../../.github](../../.github) de este repositorio.

La idea no es describir GitHub en abstracto, sino explicar cómo se trabaja aquí con:

- políticas base de Copilot
- agentes especializados de VS Code
- instrucciones por tipo de archivo
- prompts reutilizables
- plantillas de issue y pull request
- validación CI
- gobernanza del repositorio

## Primeros pasos

### Jerarquía de decisión

El orden efectivo de aplicación está resumido en [../../.github/README.md](../../.github/README.md):

| Nivel | Archivo o carpeta | Para qué sirve | Cuándo manda |
|---|---|---|---|
| 1 | [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md) | Política transversal del repositorio | Siempre |
| 2 | [../../.github/agents](../../.github/agents) | Roles especializados con límites de herramientas y responsabilidades | Cuando se delega o selecciona un agente |
| 3 | [../../.github/instructions](../../.github/instructions) | Reglas por ruta o tipo de archivo | Cuando el archivo coincide con `applyTo` |
| 4 | [../../.github/prompts](../../.github/prompts) | Flujos de trabajo para tareas concretas | Cuando se invoca el prompt |
| 5 | [../../.github/ISSUE_TEMPLATE](../../.github/ISSUE_TEMPLATE), [../../.github/pull_request_template.md](../../.github/pull_request_template.md), [../../.github/workflows/tests.yml](../../.github/workflows/tests.yml) | Operativa de GitHub | Al abrir issues, PRs o ejecutar CI |

### Regla práctica

- Si vas a pedir trabajo al agente, empieza por la política base.
- Si la tarea necesita separar planificación, implementación o auditoría, usa además el agente especializado correspondiente.
- Si el cambio cae en una ruta concreta, además aplican las instrucciones de esa ruta.
- Si quieres forzar un formato de salida o un modo de trabajo, usa el prompt correspondiente; el prompt define la salida y el agente define el rol.
- Si el cambio se va a revisar o registrar en GitHub, usa las plantillas y la validación definidas.

## Configuración

La carpeta [../../.github](../../.github) ya deja configurados estos comportamientos:

| Elemento | Archivo | Configuración relevante |
|---|---|---|
| Política base | [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md) | Senior Python, librería multibase, salida estructurada, políticas por tipo de trabajo |
| Agentes | [../../.github/agents](../../.github/agents) | Routing, planificación, implementación, hotfix, auditoría, seguridad y cierre |
| Instrucciones docs | [../../.github/instructions/docs.instructions.md](../../.github/instructions/docs.instructions.md) | Markdown portable, ejemplos claros, secciones consistentes |
| Instrucciones Python | [../../.github/instructions/python.instructions.md](../../.github/instructions/python.instructions.md) | Python 3.12+, tipado, separación introspect/render |
| Instrucciones introspección | [../../.github/instructions/introspection.instructions.md](../../.github/instructions/introspection.instructions.md) | Multibase, introspección agnóstica, límites por motor |
| Instrucciones render | [../../.github/instructions/render.instructions.md](../../.github/instructions/render.instructions.md) | Salida determinista y render puro |
| Instrucciones render Markdown | [../../.github/instructions/render-markdown.instructions.md](../../.github/instructions/render-markdown.instructions.md) | Orden de secciones y formato por tabla |
| Instrucciones tests | [../../.github/instructions/tests.instructions.md](../../.github/instructions/tests.instructions.md) | Tests pequeños, deterministas y sin red |
| Prompts | [../../.github/prompts](../../.github/prompts) | Flujos estandarizados para feature, hotfix, refactor, revisión y cierre |
| Issues | [../../.github/ISSUE_TEMPLATE](../../.github/ISSUE_TEMPLATE) | Formularios para bug y feature |
| PR | [../../.github/pull_request_template.md](../../.github/pull_request_template.md) | Resumen, alcance, validación y riesgos |
| Seguridad | [../../.github/SECURITY.md](../../.github/SECURITY.md) | Reporte privado y alcance prioritario |
| Contribución | [../../.github/CONTRIBUTING.md](../../.github/CONTRIBUTING.md) | Flujo mínimo y validación local |
| Ownership | [../../.github/CODEOWNERS](../../.github/CODEOWNERS) | Responsable por áreas |
| Dependabot | [../../.github/dependabot.yml](../../.github/dependabot.yml) | Actualizaciones semanales de pip y GitHub Actions |
| CI | [../../.github/workflows/tests.yml](../../.github/workflows/tests.yml) | Windows y Ubuntu, Python 3.12 a 3.14 |

### Agentes disponibles

La carpeta [../../.github/agents](../../.github/agents) añade una capa de especialización operativa sobre la política base y los prompts.

| Agente | Archivo | Úsalo cuando |
|---|---|---|
| `Workflow Director` | [../../.github/agents/workflow-director.agent.md](../../.github/agents/workflow-director.agent.md) | Necesitas clasificar una petición y decidir skill, fase o flujo |
| `Plan Architect` | [../../.github/agents/plan-architect.agent.md](../../.github/agents/plan-architect.agent.md) | Necesitas construir `PLAN` y `AUDIT_PLAN` contra el código real |
| `Feature Implementer` | [../../.github/agents/feature-implementer.agent.md](../../.github/agents/feature-implementer.agent.md) | Ya existe alcance aprobado y hay que ejecutar `IMPLEMENT` |
| `Hotfix Responder` | [../../.github/agents/hotfix-responder.agent.md](../../.github/agents/hotfix-responder.agent.md) | Hay que aplicar un fix mínimo con RCA y rollback |
| `Code Auditor` | [../../.github/agents/code-auditor.agent.md](../../.github/agents/code-auditor.agent.md) | Quieres un `AUDIT_CODE` o revisión de regresiones |
| `Security Reviewer` | [../../.github/agents/security-reviewer.agent.md](../../.github/agents/security-reviewer.agent.md) | Quieres una auditoría de seguridad independiente |
| `Version Closer` | [../../.github/agents/version-closer.agent.md](../../.github/agents/version-closer.agent.md) | Necesitas cerrar una sesión, release o bloque de cambios |
| `Maturity Assessment` | [../../.github/agents/maturity-assessment.agent.md](../../.github/agents/maturity-assessment.agent.md) | Quieres evaluar la madurez del repositorio para publicación o revisión integral |
| `Explore` | [../../.github/agents/explore.agent.md](../../.github/agents/explore.agent.md) | Necesitas explorar el repositorio de forma read-only sin modificar nada |

## Uso

### Caso 1. Política base siempre activa

Cuando pides un cambio cualquiera, la política de [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md) fija el marco:

- hay que responder en Markdown estructurado
- no se deben inventar módulos, clases o tests
- hay que emitir PLAN y AUDIT_PLAN antes del resto cuando el trabajo lo requiera
- `new_feature`, `hotfix`, `refactor` y `security_review` tienen restricciones distintas

Ejemplo de petición:

```text
Necesito añadir documentación Markdown para vistas y relaciones FK en el renderer.
```

Efecto esperado:

- el agente debe identificar que es una feature
- debe separar plan, riesgos, implementación y cierre
- no debe mezclarlo con un refactor no solicitado

### Caso 2. Instrucciones activadas por ruta

Las instrucciones de [../../.github/instructions](../../.github/instructions) se activan por patrón `applyTo`.

| Si editas | Se activa | Qué añade |
|---|---|---|
| `docs/**` | [../../.github/instructions/docs.instructions.md](../../.github/instructions/docs.instructions.md) | Markdown portable, secciones consistentes, ejemplos claros |
| `**/*.py` | [../../.github/instructions/python.instructions.md](../../.github/instructions/python.instructions.md) | Python 3.12+, tipado, API estable |
| `src/**/introspect/**/*.py` | [../../.github/instructions/introspection.instructions.md](../../.github/instructions/introspection.instructions.md) + reglas Python | Nada de asumir un solo motor, adaptar por dialecto |
| `src/**/render/**/*.py` | [../../.github/instructions/render.instructions.md](../../.github/instructions/render.instructions.md) + [../../.github/instructions/render-markdown.instructions.md](../../.github/instructions/render-markdown.instructions.md) + reglas Python | Orden determinista, formato consistente, Markdown real |
| `tests/**` | [../../.github/instructions/tests.instructions.md](../../.github/instructions/tests.instructions.md) | Tests pequeños, deterministas, reproducibles |

Ejemplos rápidos:

#### 2.1 Editar documentación

Archivo objetivo:

```text
docs/examples/nuevo_ejemplo.md
```

Qué debe pasar:

- usar Markdown estándar
- incluir ejemplos sin credenciales reales
- evitar HTML embebido si no es imprescindible

#### 2.2 Editar introspección

Archivo objetivo:

```text
src/util_bbdd/algun_modulo/introspect/sqlite.py
```

Qué debe pasar:

- no asumir que SQLite representa a todos los motores
- documentar limitaciones reales
- encapsular diferencias por motor

#### 2.3 Editar render Markdown

Archivo objetivo:

```text
src/util_bbdd/algun_modulo/render/markdown.py
```

Qué debe pasar:

- mantener salida determinista
- respetar orden de secciones por tabla
- usar Mermaid solo si deriva de metadatos reales y aporta valor claro

#### 2.4 Editar tests

Archivo objetivo:

```text
tests/test_markdown_renderer.py
```

Qué debe pasar:

- usar fixtures pequeñas
- asserts sobre fragmentos clave o snapshots controlados
- no depender de red ni servicios externos obligatorios

### Caso 3. Uso de agentes

Los agentes de [../../.github/agents](../../.github/agents) no sustituyen a los prompts. Su función es aislar responsabilidad, limitar herramientas y hacer explícita la fase de trabajo.

Cadena recomendada en este repositorio:

```text
Workflow Director -> Plan Architect -> Feature Implementer o Hotfix Responder -> Code Auditor -> Version Closer
```

Para exploración previa o análisis de madurez:

```text
Explore -> Maturity Assessment -> Version Closer
```

Regla práctica:

- usa `Workflow Director` cuando la petición todavía no esté clasificada; incluye tabla de transiciones `skill → siguiente agente`
- usa `Explore` para exploración read-only del repositorio antes de planificar
- usa `Plan Architect` antes de implementar una feature o un hotfix relevante
- usa `Feature Implementer` solo cuando el alcance ya está aprobado
- usa `Hotfix Responder` para incidencias con fix mínimo
- usa `Code Auditor` para revisar regresiones, contratos y cobertura
- usa `Security Reviewer` cuando el objetivo principal sea seguridad
- usa `Maturity Assessment` para evaluar readiness de publicación o revisión integral
- usa `Version Closer` al cerrar una versión, PR o sesión de trabajo

Todos los agentes cargan automáticamente contexto de `.ai/` (product, architecture, standards, runtime, glossary) antes de responder.

Tabla de mapeo rápido entre prompts y agentes:

| Tipo de tarea | Prompt habitual | Agente recomendado |
|---|---|---|
| Clasificar una petición ambigua | opcional | `Workflow Director` |
| Explorar el repositorio sin modificar | — | `Explore` |
| Planificar una feature | `new_feature` | `Plan Architect` |
| Implementar una feature ya aprobada | `new_feature` | `Feature Implementer` |
| Corregir un bug acotado | `hotfix` | `Hotfix Responder` |
| Refactorizar sin cambio funcional | `refactor` | `Plan Architect` y luego `Feature Implementer` |
| Auditar código | `audit_code` | `Code Auditor` |
| Revisar seguridad | `security_review` | `Security Reviewer` |
| Inventariar deuda técnica | `tech_debt` | `Plan Architect` y luego `Code Auditor` |
| Evaluar madurez | `maturity_assessment` | `Maturity Assessment` |
| Cerrar una versión o sesión | `version_closure` | `Version Closer` |

### Caso 4. Uso de prompts

Los prompts de [../../.github/prompts](../../.github/prompts) sirven para encauzar tareas frecuentes con una salida fija.

En este repositorio pueden invocarse como símbolos en chat, por ejemplo:

```text
@#sym:new_feature
@#sym:hotfix
@#sym:version_closure
```

Tabla resumen:

| Prompt | Archivo | Úsalo cuando | Salida esperada |
|---|---|---|---|
| `new_feature` | [../../.github/prompts/new_feature.prompt.md](../../.github/prompts/new_feature.prompt.md) | Vas a añadir comportamiento nuevo | `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE`, `VERSION` |
| `hotfix` | [../../.github/prompts/hotfix.prompt.md](../../.github/prompts/hotfix.prompt.md) | Hay que corregir un bug acotado | `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE`, `VERSION` |
| `refactor` | [../../.github/prompts/refactor.prompt.md](../../.github/prompts/refactor.prompt.md) | Quieres mejorar estructura sin cambiar comportamiento | `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE`, `VERSION` |
| `security_review` | [../../.github/prompts/security_review.prompt.md](../../.github/prompts/security_review.prompt.md) | Quieres revisar seguridad | `PLAN`, `AUDIT_PLAN`, `AUDIT_CODE`, `VERSION` |
| `audit_code` | [../../.github/prompts/audit_code.prompt.md](../../.github/prompts/audit_code.prompt.md) | Quieres una revisión técnica de código | `PLAN`, `AUDIT_PLAN`, `AUDIT_CODE`, `VERSION` |
| `tech_debt` | [../../.github/prompts/tech_debt.prompt.md](../../.github/prompts/tech_debt.prompt.md) | Quieres inventariar deuda técnica | `PLAN`, `AUDIT_PLAN`, `AUDIT_CODE`, `VERSION` |
| `maturity_assessment` | [../../.github/prompts/maturity_assessment.prompt.md](../../.github/prompts/maturity_assessment.prompt.md) | Quieres valorar madurez del repositorio | `PLAN`, `AUDIT_PLAN`, `AUDIT_CODE`, `VERSION` |
| `version_closure` | [../../.github/prompts/version_closure.prompt.md](../../.github/prompts/version_closure.prompt.md) | Quieres cerrar una versión o un bloque de cambios | commit message, changelog, impacto, rollback y checklist |

Relación entre prompt y agente:

- el prompt fija el contrato de salida
- el agente fija la fase, el rol y el nivel de autonomía
- cuando ambos se usan juntos, el resultado es más predecible y más fácil de revisar

## Ejemplos

### Ejemplo completo 1. `new_feature`

Invocación:

```text
@#sym:new_feature

Objetivo: añadir exportación Markdown de vistas con Mermaid opcional.
Módulo(s) o clase(s) afectadas: src/util_bbdd/doc/render_markdown.py, tests/test_render_markdown.py
API pública esperada: parámetro opcional para habilitar diagramas Mermaid
Contrato de entrada: modelo de metadatos ya introspectado
Contrato de salida: Markdown portable y determinista
Reglas de negocio: no inventar metadatos, Mermaid solo con datos reales
Restricciones: sin dependencias nuevas
Motores o formatos afectados: Markdown
Migraciones necesarias: ninguna
Archivos existentes: sí
```

Qué obliga este prompt:

- presentar `PLAN`
- presentar `AUDIT_PLAN`
- implementar por capas o rutas
- cerrar con `AUDIT_CODE` y `VERSION`
- no convertir la tarea en refactor general

Agente recomendado:

- `Plan Architect` para construir `PLAN` y `AUDIT_PLAN`
- `Feature Implementer` solo después de aprobar alcance
- `Code Auditor` para la revisión posterior

### Ejemplo completo 2. `hotfix`

Invocación:

```text
@#sym:hotfix

Bug: el renderer HTML pierde iconos offline cuando se exporta fuera del workspace.
Rutas afectadas: src/util_bbdd/doc/render_html.py, tests/test_html_assets.py
Dato faltante o supuesto: se asume que la salida debe ser portable sin acceso a red
```

Qué obliga este prompt:

- arreglar solo la causa raíz
- no refactorizar
- no optimizar fuera del bug
- añadir test de reproducción si es viable

Agente recomendado:

- `Plan Architect` si todavía falta delimitar impacto
- `Hotfix Responder` para ejecutar el fix mínimo

### Ejemplo completo 3. `refactor`

Invocación:

```text
@#sym:refactor

Objetivo: separar construcción de payload de leyenda y render HTML sin cambiar comportamiento.
Módulos: src/util_bbdd/doc/diagram_legend.py, src/util_bbdd/doc/render_html.py
Contrato público: sin cambios
Restricciones: preservar snapshots y orden actual de salida
```

Qué obliga este prompt:

- no introducir cambios funcionales
- priorizar responsabilidad única y legibilidad
- justificar cualquier cambio en API pública

Agente recomendado:

- `Plan Architect` para delimitar alcance y riesgos
- `Feature Implementer` para ejecutar el refactor aprobado

### Ejemplo completo 4. `security_review`

Invocación:

```text
@#sym:security_review

Revisa la generación documental para detectar fuga de secretos, exposición de SQL sensible e inyección por identificadores.
Áreas: src/util_bbdd/doc, src/util_bbdd/analysis, docs/examples
```

Qué obliga este prompt:

- ordenar hallazgos por severidad
- separar confirmados de supuestos
- dar remediación accionable
- no mezclarlo con una feature

Agente recomendado:

- `Security Reviewer`

### Ejemplo completo 5. `audit_code`

Invocación:

```text
@#sym:audit_code

Revisa src/util_bbdd/doc/render_markdown.py y src/util_bbdd/doc/render_html.py.
Quiero bugs, edge cases, compatibilidad y tests faltantes.
```

Qué obliga este prompt:

- emitir veredicto final
- citar evidencias concretas por archivo o módulo
- diferenciar hallazgos confirmados de hipótesis

Agente recomendado:

- `Code Auditor`

### Ejemplo completo 6. `tech_debt`

Invocación:

```text
@#sym:tech_debt

Analiza la deuda técnica de src/util_bbdd/doc y src/util_bbdd/analysis.
Quiero quick wins, prioridades y plan por fases.
```

Qué obliga este prompt:

- confirmar inputs requeridos antes de responder: módulo objetivo, deuda conocida, versión actual y política de compatibilidad
- listar deuda por módulo con archivo y línea si aplica
- clasificar cada hallazgo como `quick_win`, `fase_media` o `deuda_estructural`
- proponer quick wins con estrategia de prueba mínima
- emitir veredicto: `LIMPIO | DEUDA_MENOR | DEUDA_SIGNIFICATIVA | CRÍTICO`

Agente recomendado:

- `Plan Architect` para delimitar alcance y dependencias entre ítems de deuda
- `Code Auditor` para el análisis técnico detallado

### Ejemplo completo 7. `maturity_assessment`

Invocación:

```text
@#sym:maturity_assessment

Evalúa la madurez del repositorio para una publicación estable centrada en documentación multibase y render HTML offline.
```

Qué obliga este prompt:

- emitir veredicto de madurez: `PRODUCTION_READY | NEAR_READY | BLOCKED`
- separar bloqueantes de mejoras recomendadas
- revisar APIs, contratos, seguridad, tests y mantenibilidad

Agente recomendado:

- `Explore` para recopilar evidencia del estado real antes de valorar
- `Maturity Assessment` para el análisis y veredicto formal

### Ejemplo completo 8. `version_closure`

Invocación:

```text
@#sym:version_closure
```

Uso típico:

- después de alinear metadatos, CI y documentación
- al finalizar una release o un bloque coherente de cambios
- para preparar commit message, changelog, impacto, compatibilidad y rollback

Salida mínima esperada, según [../../.github/prompts/version_closure.prompt.md](../../.github/prompts/version_closure.prompt.md):

- commit message
- changelog
- impacto en API pública
- migraciones
- compatibilidad
- rollback
- checklist final
- pruebas ejecutadas o sugeridas

Agente recomendado:

- `Version Closer`

### Ejemplo completo 9. Crear una issue de bug

La plantilla está en [../../.github/ISSUE_TEMPLATE/bug_report.md](../../.github/ISSUE_TEMPLATE/bug_report.md).

Ejemplo de issue:

```md
## Descripción
La exportación HTML offline no copia los iconos SVG del toolbar y deja botones sin imagen.

## Módulo, clase o función afectada
src/util_bbdd/doc/render_html.py

## Pasos para reproducir
1. Generar documentación HTML offline.
2. Abrir index.html fuera del workspace.
3. Ir a la vista global "Ver todo".

## Resultado esperado
Los iconos se muestran correctamente sin acceso a red.

## Resultado actual
Los botones aparecen sin icono.

## Motor, entorno y versión
SQLite, Windows 11, util_bbdd 0.6.3, Python 3.12

## Configuración implicada
Salida HTML offline con assets locales.

## Riesgo
La documentación exportada pierde claridad visual y parece incompleta.

## Evidencia mínima
Captura de la página generada y listado de assets ausentes.
```

### Ejemplo completo 10. Crear una issue de feature

La plantilla está en [../../.github/ISSUE_TEMPLATE/feature_request.md](../../.github/ISSUE_TEMPLATE/feature_request.md).

Ejemplo de issue:

```md
## Objetivo
Permitir exportar diagramas de relaciones en Mermaid además de Graphviz para Markdown.

## Contexto
Algunos consumidores publican documentación en renderers Markdown sin soporte SVG incrustado.

## Módulo, clase o área afectada
src/util_bbdd/doc/render_markdown.py

## API pública esperada
Nuevo parámetro opcional `diagram_format="graphviz" | "mermaid"`.

## Motores o formatos afectados
Markdown

## Criterios de aceptación
- salida determinista
- sin inventar relaciones
- tests con metadatos reales o fixtures mínimas

## Riesgos
Duplicar lógica de render si no se separa bien el payload común.

## Restricciones o supuestos
No introducir servicios externos ni dependencias pesadas.
```

### Ejemplo completo 11. Abrir una PR

La plantilla está en [../../.github/pull_request_template.md](../../.github/pull_request_template.md).

Ejemplo de PR rellenada:

```md
## Resumen
Se alinea el soporte oficial a Python 3.12+ y se sincronizan CI, metadatos y documentación.

## Tipo de cambio
- [x] hotfix

## Rutas afectadas
- pyproject.toml
- README.md
- .github/workflows/tests.yml
- docs/plan/**

## Impacto en API pública y compatibilidad
No cambia la API Python, pero el runtime soportado pasa a 3.12+.

## Supuestos o datos faltantes
Se asume que no se dará soporte oficial a 3.11 en adelante.

## Validación
- [x] revisión manual
- [ ] lint ejecutado
- [ ] tests ejecutados
- [ ] type-check ejecutado
- [x] rollback definido

## Riesgos
Usuarios con entornos 3.11 deberán recrear el runtime.

## Evidencia
Se adjuntan diff de CI, metadatos y README.
```

### Ejemplo completo 12. Reporte de seguridad

El punto de entrada está en [../../.github/SECURITY.md](../../.github/SECURITY.md) y se enlaza desde [../../.github/ISSUE_TEMPLATE/config.yml](../../.github/ISSUE_TEMPLATE/config.yml).

Ejemplo de reporte privado:

```md
Asunto: Posible fuga de credenciales en artefactos HTML generados

- Descripción: se detecta que el HTML exportado puede incluir DSN completos en un bloque de metadatos.
- Impacto estimado: exposición de host, usuario técnico y estructura interna.
- Pasos mínimos: generar documentación con un DSN explícito y revisar el bloque de cabecera.
- Versiones afectadas: 0.6.1, 0.6.2 y 0.6.3
- Mitigación propuesta: sanear configuración sensible antes del render y añadir test de regresión.
```

### Ejemplo completo 13. Flujo de contribución

El flujo está en [../../.github/CONTRIBUTING.md](../../.github/CONTRIBUTING.md).

Ejemplo de uso correcto:

1. Abrir una rama corta solo para `hotfix`.
2. Revisar [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md) y la instrucción específica del área.
3. Aplicar cambio pequeño.
4. Añadir tests.
5. Ejecutar localmente:

```bash
python -m ruff check src tests
python -m mypy src
python -m pytest
```

6. Abrir PR con plantilla y riesgos explícitos.

### Ejemplo completo 14. `CODEOWNERS`

La definición está en [../../.github/CODEOWNERS](../../.github/CODEOWNERS).

Uso práctico:

- si cambias `src/`, el owner por defecto es `@fmanza`
- si cambias `tests/`, el owner por defecto es `@fmanza`
- si cambias `docs/`, el owner por defecto es `@fmanza`
- si cambias `.github/`, el owner por defecto es `@fmanza`

Ejemplo:

```text
Una PR que modifica src/util_bbdd/doc/render_html.py y tests/test_render_html.py solicitará revisión del owner definido.
```

### Ejemplo completo 15. Dependabot

La configuración está en [../../.github/dependabot.yml](../../.github/dependabot.yml).

Qué hace:

- revisa semanalmente dependencias `pip`
- revisa semanalmente GitHub Actions
- limita PRs abiertas a 5 por ecosistema
- etiqueta con `dependencies` y, para Actions, también `github-actions`

Ejemplo esperado:

```text
Dependabot abre una PR semanal para subir codecov/codecov-action o una dependencia Python del proyecto.
```

### Ejemplo completo 16. CI

La validación está en [../../.github/workflows/tests.yml](../../.github/workflows/tests.yml).

Qué valida hoy:

| Sistema | Versiones Python |
|---|---|
| Ubuntu | 3.12, 3.13, 3.14 |
| Windows | 3.12, 3.13, 3.14 |

Qué ejecuta:

1. checkout
2. instalación editable con extras `dev`
3. `ruff`
4. `mypy`
5. `pytest` con cobertura
6. subida de cobertura desde Ubuntu 3.12
7. `python -m build` en un job de empaquetado dedicado

Ejemplo de lectura correcta del workflow:

- un fallo de `pytest` rompe el job
- `ruff`, `mypy` y `pytest` bloquean la matriz de calidad si fallan
- la cobertura se publica una sola vez para evitar duplicados
- el empaquetado se valida aparte para detectar roturas de distribución antes de publicar

## FAQ

### ¿Cuándo uso un prompt, un agente o una instrucción?

Usa instrucción cuando la regla depende de la ruta o del tipo de archivo. Usa prompt cuando quieras imponer una forma de trabajo o de salida para una tarea concreta. Usa agente cuando quieras fijar el rol operativo, aislar una fase o limitar el tipo de acciones y herramientas.

### ¿Los agentes sustituyen a los prompts?

No. En este repositorio los prompts siguen marcando el contrato de salida y los agentes añaden especialización por fase. Lo normal es combinarlos.

### ¿Qué agente debo usar primero si la petición es ambigua?

Empieza por [../../.github/agents/workflow-director.agent.md](../../.github/agents/workflow-director.agent.md). Si la tarea requiere contraste con el código real, el siguiente paso suele ser [../../.github/agents/plan-architect.agent.md](../../.github/agents/plan-architect.agent.md).

### ¿Puedo usar `new_feature` para un bug?

No es lo recomendable. Para un bug acotado usa [../../.github/prompts/hotfix.prompt.md](../../.github/prompts/hotfix.prompt.md), porque prohíbe refactorizar y optimizar fuera del fix.

### ¿Puedo meter Mermaid en cualquier Markdown?

No. La política actual permite Mermaid solo cuando aporta valor claro y se genera desde metadatos reales, según [../../.github/instructions/docs.instructions.md](../../.github/instructions/docs.instructions.md) y [../../.github/instructions/render-markdown.instructions.md](../../.github/instructions/render-markdown.instructions.md).

### ¿Qué pasa si una regla de prompt choca con una regla de instrucciones?

Primero manda la política base de [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md). Después, la instrucción aplicable por ruta. El prompt fuerza sobre todo el formato y el flujo de trabajo de la tarea, pero no debería contradecir la política base ni el estado real del repositorio.

### ¿Qué archivo debo leer primero si soy nuevo en el repositorio?

Empieza por [../../.github/README.md](../../.github/README.md) y luego por [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md).

### ¿Cuándo debo usar `Explore` en lugar de preguntar directamente al agente de turno?

Usa `Explore` cuando necesites recopilar evidencia del estado real del repositorio (estructura, módulos, tests, contratos) antes de planificar o evaluar. Es read-only y más rápido que lanzar directamente un `Plan Architect` o `Maturity Assessment` sin contexto suficiente.

### ¿Cómo sé qué agente sigue al `Workflow Director`?

El agente `Workflow Director` incluye una tabla de transiciones `skill → agente → siguiente fase`. Consúltala en [../../.github/agents/workflow-director.agent.md](../../.github/agents/workflow-director.agent.md).

### ¿Qué debo rellenar antes de invocar `tech_debt`?

El prompt `tech_debt` exige cinco inputs antes de responder: módulo objetivo, deuda conocida o síntomas, versión actual, restricciones de scope (solo análisis o también IMPLEMENT) y política de compatibilidad. Si falta alguno, el agente lo declarará como supuesto explícito.

### ¿Qué archivo debo usar para cerrar una versión?

Usa [../../.github/prompts/version_closure.prompt.md](../../.github/prompts/version_closure.prompt.md) y acompáñalo con revisión de [../../.github/pull_request_template.md](../../.github/pull_request_template.md), [../../.github/CONTRIBUTING.md](../../.github/CONTRIBUTING.md) y [../../.github/workflows/tests.yml](../../.github/workflows/tests.yml).
