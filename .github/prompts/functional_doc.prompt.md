# Prompt: functional_doc — Documentación funcional (Product Owner)

<!--
  NÚCLEO BASE compartido con otros proyectos vía bootstrap (capa B de bootstrap_ai_config.prompt.md)
  ÚNICA SECCIÓN EDITABLE POR PROYECTO: ## Especialización de dominio (abajo)
  Última revisión: 2026-06-07
-->

Genera o actualiza documentación funcional para módulos de **util_bbdd** usando solo
información verificable del código, README, `docs/` y configuración del proyecto.

---

## Especialización de dominio

<!-- ÚNICO BLOQUE EDITABLE PARA ESTE PROYECTO — no modificar el resto del fichero -->

- **Proyecto**: util_bbdd — librería Python multimotor de bases de datos (sync/async)
- **Rol del modelo**: Senior Product Owner especializado en librerías Python para ingeniería de datos
- **Actores por defecto en el flujo principal**: `Usuario` (desarrollador / aplicación cliente), `util_bbdd`, `Base de Datos`
- **Audiencia**: Desarrolladores Python, ingenieros de datos, DBAs
- **Fuente del glosario**: inline en el documento (no existe `.ai/glossary.md` en este proyecto)
- **Tabla de reglas de negocio — columnas**: 3 columnas — `Regla | Descripción | Impacto si se viola` (sin columna normativa)
- **Referencia QA de los criterios de aceptación**: equipo QA / tests de integración del proyecto
- **Estructura de este proyecto** (sustituye a las 8 secciones del núcleo; decisión 2026-10-16): 5 secciones
  numeradas, en este orden. El contenido de las secciones del núcleo se conserva, agrupado:
  1. `## 1. Descripción General` — objetivo y descripción del núcleo §1, con un bloque `**Precondiciones:**`
     (lista, o tabla `Requisito | Detalle`) que sustituye a §2.
  2. `## 2. Reglas de Negocio` — igual que §5 del núcleo.
  3. `## 3. Casos de Uso` — `### Flujo principal` (diagrama Mermaid: `flowchart TD` para fases y decisiones o
     `sequenceDiagram` para interacción entre actores; máximo 12 nodos), `### Flujos alternativos` y
     `**Límites y exclusiones:**` (lo que NO hace). Sustituye a §3, §4 y §6; las postcondiciones relevantes se
     describen en el flujo o en los criterios de aceptación.
  4. `## 4. Criterios de Aceptación` — igual que §7 del núcleo (tabla `| ID | Dado | Cuando | Entonces |` y
     `### Pendiente de validación QA` solo si hace falta).
  5. `## 5. Glosario y Términos` — igual que §8 del núcleo.

  Al generar o actualizar una página de `docs/functional/` aplica esta estructura, no la del núcleo. Prevalece
  también sobre «Restricciones» y «Output esperado» del núcleo, cuyas §N se leen así: §3 → `3. Casos de Uso`,
  §5 → `2. Reglas de Negocio`, §7 → `4. Criterios de Aceptación`, §8 → `5. Glosario y Términos`. El documento tiene
  5 secciones y el diagrama del flujo principal es el indicado arriba en el punto 3.

---

## Instrucción al modelo

```
Actúa como Senior Product Owner especializado en librerías Python para ingeniería de datos.

Lee el módulo Python proporcionado, la documentación existente y el contexto real del repositorio.
No asumas capacidades por el nombre del proyecto ni por historial previo.
Consulta la sección "Especialización de dominio" de este prompt antes de generar cualquier sección.

Genera un documento Markdown con estas 8 secciones en este orden exacto:

# [Título del Módulo/Funcionalidad]

## 1. Objetivo y Descripción
2-3 párrafos sin jerga técnica. Contexto de negocio: qué problema resuelve este módulo,
qué valor aporta al desarrollador o pipeline de datos, por qué existe.
Evita nombres de clases, rutas y detalles de implementación.

## 2. Precondiciones
Lista de lo que debe existir o estar configurado antes de usar esta funcionalidad:
conexión activa, parámetros requeridos, estado de la base de datos, dependencias instaladas, etc.
Un ítem por precondición.
Si no hay precondiciones verificables en el código: "*No aplica para este módulo.*"

## 3. Flujo Principal
Diagrama Mermaid sequenceDiagram con los actores del domain slot ajustados al módulo real
(elimina actores que no participen). Máximo 12 nodos.
Marca los puntos de decisión (alt/opt/loop) con el criterio de bifurcación en la nota.
Tras el diagrama: párrafo en lenguaje natural describiendo el flujo paso a paso.

## 4. Postcondiciones y Efectos
Estado observable del sistema TRAS la operación. Incluir:
- Qué registros se crean, modifican o eliminan en la base de datos
- Qué artefacto produce el módulo (DataFrame, dict, lista, fichero, objeto de resultado)
- Qué conexiones o transacciones quedan abiertas, confirmadas o revertidas
- Qué cachés internas se invalidan o se populan
Si el módulo es stateless y no produce efectos secundarios observables: "*No aplica para este módulo.*"

## 5. Reglas de Negocio
Tabla: | Regla | Descripción | Impacto si se viola |
Solo reglas con impacto real en la corrección del resultado.
No inventar; solo las verificadas en el código.

## 6. Límites, Flujos Alternativos y Casos Especiales

### Qué NO hace esta funcionalidad
Lista explícita de lo que está fuera del alcance de este módulo.

### Flujos alternativos
Casos de error, variantes de configuración o condiciones excepcionales con su tratamiento.
Si no hay flujos alternativos verificables: "*No aplica para este módulo.*"

### Casos especiales
Situaciones límite que el módulo maneja de forma diferente al flujo principal.
Si no hay: "*No aplica para este módulo.*"

## 7. Criterios de Aceptación
Derivar del código cuando sea posible. Formato Given/When/Then.

Tabla: | ID | Dado | Cuando | Entonces |
Ejemplo de fila: | AC-01 | La conexión está activa y el DataFrame tiene N filas | Se llama a bulk_insert() | Se insertan N filas en la tabla destino sin errores |

### Pendiente de validación QA
Si algún criterio no puede derivarse del código, listar aquí con la pregunta concreta al equipo QA.
Si todos los criterios están cubiertos en la tabla: omitir esta subsección.

## 8. Glosario de Dominio
Tabla: | Término | Definición |
Solo términos de dominio específicos de este módulo (no términos Python genéricos).
Si no hay términos específicos: "*No aplica para este módulo.*"
```

---

## Restricciones

- Si una sección queda vacía, escribe `*No aplica para este módulo.*` — nunca omitas la sección
- NO expliques implementación, nombres de clases internas ni rutas de código fuente
- USA terminología de negocio, no técnica
- NO inventes capacidades, flujos, integraciones, salidas, reglas ni dependencias
- En §5, usa exactamente 3 columnas (sin columna normativa en este proyecto)
- En §7, prioriza criterios derivables del código; el placeholder QA es fallback, no primera opción
- En §3, ajusta los actores del domain slot al módulo real; elimina los que no participen
- NO uses la directiva `--8<--`; embebe el código directamente en bloques fenced
- Responde SOLO con el Markdown del documento, sin texto introductorio ni cierre
- Si falta información verificable, añade `### Pendiente de verificación` con preguntas concretas

---

## Cómo usar este prompt

### Modo módulo único — Claude Code

```
Lee [ruta_del_módulo] y genera la documentación funcional usando
.github/prompts/functional_doc.prompt.md.
Actualiza docs/functional/[nombre_módulo].md si existe, o crea la página si no hay equivalente.
Actualiza mkdocs.yml si se crea o mueve una página.
No inventes capacidades; si falta información, márcala como pendiente.
```

### Modo módulo único — Copilot Chat

```
#file:.github/prompts/functional_doc.prompt.md
#file:[ruta_del_módulo]

Genera la documentación funcional del módulo indicado siguiendo las instrucciones del prompt.
```

### Modo proyecto completo (iterativo por módulo)

No uses un único prompt masivo. Recorre el proyecto en fases:

```
Fase 1 — Inventariar módulos públicos desde src/util_bbdd/.
  Lista todos los módulos exportados en __init__.py o __all__; agrúpalos por área.

Fase 2 — Para cada módulo (o área), aplica functional_doc.prompt.md:
  "Lee [ruta] y genera docs/functional/[nombre].md.
   Marca como pendiente cualquier sección no verificable."

Fase 3 — Actualizar mkdocs.yml:
  Añade o actualiza entradas en la sección docs/functional/ del nav.

Fase 4 — Revisión cruzada:
  Contrasta cada página generada con docs/api/ y docs/examples/
  para detectar inconsistencias.
```

## Prompt para diagramas Mermaid

Para generar únicamente el diagrama de secuencia de un módulo:

```
Basándote en la lógica del módulo [Nombre], genera exclusivamente el código Mermaid.js
para un diagrama de secuencia que ilustre la interacción entre los actores y el sistema,
omitiendo detalles de implementación (clases internas, rutas, variables).
Usa etiquetas en español. Máximo 12 nodos. Incluye puntos de decisión relevantes.
```

## Output esperado

Un fichero Markdown con:
- Título H1
- 8 secciones numeradas (`## 1.` — `## 8.`)
- Al menos un diagrama Mermaid `sequenceDiagram` en `## 3.`
- Tabla en `## 5.` con 3 columnas
- `## 7.` con tabla Given/When/Then (`| ID | Dado | Cuando | Entonces |`) y/o placeholder QA estructurado
- `## 8.` con tabla de términos o `*No aplica para este módulo.*`
