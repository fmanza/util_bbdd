# Prompt: functional_doc — Documentación funcional (Product Owner)

Genera o actualiza documentación funcional para módulos de **util_bbdd** usando solo
información verificable del código, README, `docs/` y configuración del proyecto.

## Instrucción al modelo

```
Actúa como Senior Product Owner especializado en documentación de producto para librerías Python.

Analiza el módulo Python proporcionado, la documentación existente relacionada y el contexto
real del repositorio. No asumas capacidades por el nombre histórico del proyecto.

Genera un documento Markdown con estas secciones en este orden exacto:

## Objetivo de negocio
Qué problema de negocio resuelve este módulo específico (1-2 párrafos).
Evita jerga técnica. Habla en términos de valor para el usuario final.

## Precondiciones
Lista de requisitos que deben cumplirse antes de usar este módulo.
Incluye: datos de entrada, configuraciones previas, dependencias externas.

## Flujo principal del usuario
Un diagrama Mermaid sequenceDiagram que muestre la interacción entre:
- El actor principal (usuario, pipeline CI/CD, etc.)
- Los componentes del módulo (sin nombres de clases internas)
- El sistema externo relevante si existe
- La salida generada

## Reglas de negocio críticas
Tabla con columnas: | Regla | Descripción | Impacto si se viola |
Incluye solo las reglas con impacto en la corrección del resultado.

## Ejemplo de funcionamiento
Incluye un ejemplo genérico y verificable de uso cuando el módulo lo permita.
No uses credenciales reales ni servicios externos obligatorios. Si no hay ejemplo seguro,
indica qué falta para construirlo.

## Límites y exclusiones
Qué NO hace este módulo. Máximo 5 ítems en lista.

---

Restricciones:
- NO expliques nombres de variables, clases internas ni implementación
- NO menciones rutas de archivos a menos que sean de configuración del usuario
- USA terminología de negocio, no técnica
- NO inventes capacidades, flujos, integraciones, salidas ni reglas
- Si falta información, crea una sección breve "Pendiente de verificación" con preguntas concretas
- Responde SOLO con el Markdown, sin texto introductorio ni cierre
```

## Cómo usar este prompt

### En Claude Code

```
Lee el archivo [ruta_del_módulo] y genera la documentación funcional usando el
prompt en .github/prompts/functional_doc.prompt.md.
Actualiza docs/functional/[nombre_módulo].md si existe o crea la página si no hay una equivalente.
Actualiza también mkdocs.yml si se crea o mueve una página.
```

### En Copilot Chat

```
#file:.github/prompts/functional_doc.prompt.md
#file:[ruta_del_módulo]

Genera la documentación funcional del módulo indicado.
```

## Exclusiones actuales

- No incluir por ahora ejemplos de generación mediante APIs externas.
- No usar un único prompt masivo para documentar todo el proyecto; dividir por módulo o capacidad.

## Output esperado

Un fichero Markdown con las secciones funcionales, al menos un diagrama Mermaid `sequenceDiagram`
cuando el flujo sea inferible, una tabla de reglas de negocio y un ejemplo de funcionamiento si
puede verificarse sin inventar datos.
