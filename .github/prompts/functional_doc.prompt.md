# Prompt: functional_doc — Documentación funcional (Product Owner)

Genera o actualiza documentación funcional para módulos de **util_bbdd** usando solo
información verificable del código, README, `docs/` y configuración del proyecto.

## Instrucción al modelo

```
Actúa como Senior Product Owner especializado en documentación de producto para librerías Python.

Analiza el módulo Python proporcionado, la documentación existente relacionada y el contexto
real del repositorio. No asumas capacidades por el nombre histórico del proyecto.

Genera un documento Markdown siguiendo el Arquetipo 1 con estas secciones en este orden exacto:

# [Título del Módulo/Funcionalidad]

## 1. Descripción General
Contexto de negocio y objetivo (2-3 párrafos). Evita jerga técnica.
Habla en términos de valor para el usuario final.

## 2. Reglas de Negocio
Tabla con columnas: | Regla | Descripción | Impacto si se viola |
Incluye solo las reglas con impacto en la corrección del resultado.

## 3. Casos de Uso

### Flujo principal
Un diagrama Mermaid sequenceDiagram que muestre la interacción entre:
- El actor principal (usuario, pipeline CI/CD, etc.)
- Los componentes del módulo (sin nombres de clases internas)
- El sistema externo relevante si existe
- La salida generada

### Flujos alternativos
Casos de error, variantes de uso o condiciones excepcionales.
Si no hay flujos alternativos verificables: "*No aplica para este módulo.*"

## 4. Criterios de Aceptación
[SECCIÓN PENDIENTE DE VALIDACIÓN QA — incluir ÚNICAMENTE el siguiente placeholder:]
*Pendiente de definición con el equipo QA. Estructura prevista:
Tabla | ID | Criterio | Verificable con |
Redacción: "Dado X, cuando Y, entonces Z."*

## 5. Glosario y Términos
Tabla con columnas: | Término | Definición |
Solo términos de dominio específicos de este módulo.
Si no hay términos específicos: "*No aplica para este módulo.*"

---

Restricciones:
- Si una sección queda vacía, escribe "*No aplica para este módulo.*" — nunca omitas la sección
- NO expliques nombres de variables, clases internas ni implementación
- NO menciones rutas de archivos a menos que sean de configuración del usuario
- USA terminología de negocio, no técnica
- NO uses la directiva --8<-- para incluir código; embebe el código directamente en los bloques fenced
- NO inventes capacidades, flujos, integraciones, salidas ni reglas
- Si falta información, añade subsección "### Pendiente de verificación" con preguntas concretas
- Responde SOLO con el Markdown, sin texto introductorio ni cierre
```

## Cómo usar este prompt

### Modo módulo único — Claude Code

```
Lee [ruta_del_módulo] y genera la documentación funcional usando el
prompt en .github/prompts/functional_doc.prompt.md.
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
  "Lee [ruta] y genera docs/functional/[nombre].md con objetivo de negocio,
   precondiciones, flujo (Mermaid sequenceDiagram), reglas críticas y ejemplo.
   Marca como pendiente cualquier sección que no puedas verificar."

Fase 3 — Actualizar mkdocs.yml:
  Añade o actualiza entradas en la sección docs/functional/ del nav.

Fase 4 — Revisión cruzada:
  Contrasta cada página generada con la documentación técnica (docs/api/)
  y los ejemplos en docs/examples/ para detectar inconsistencias.
```

## Exclusiones actuales

- No incluir ejemplos de generación mediante APIs externas por el momento.
- No usar un único prompt masivo para todo el proyecto; iterar módulo a módulo o por área.

## Prompt para infografías Mermaid

Para generar exclusivamente el diagrama de secuencia de un módulo:

```
Basándote en la lógica del módulo [Nombre], genera exclusivamente el código Mermaid.js
para un diagrama de secuencia que ilustre la interacción entre el usuario y el sistema,
omitiendo detalles de implementación como nombres de variables internas, rutas de ficheros
del sistema o nombres de clases privadas.
Usa etiquetas en español. Máximo 12 nodos.
```

## Output esperado

Un fichero Markdown con las 5 secciones del Arquetipo 1 numeradas (`## 1.`–`## 5.`), título H1,
al menos un diagrama Mermaid `sequenceDiagram` en `## 3.`, tabla de reglas en `## 2.`,
`## 4. Criterios de Aceptación` con el placeholder de pendiente QA,
y `## 5. Glosario` con tabla o `*No aplica para este módulo.*`.
