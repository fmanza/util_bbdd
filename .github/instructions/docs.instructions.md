---
applyTo: "docs/**"
---
# Documentación

> **TL;DR** — Documentación Markdown para MkDocs Material, basada solo en código y ficheros reales. Separar claramente documentación funcional, técnica y ejemplos. Actualizar `mkdocs.yml` cuando se añadan, muevan o retiren páginas. No inventar capacidades, módulos, APIs, flujos ni salidas.

- Escribe documentación clara, concisa y orientada a la audiencia de cada página.
- Usa MkDocs con Material for MkDocs como generador estático de referencia.
- Usa Mermaid.js para diagramas cuando mejore la comprensión; el diagrama debe ser texto plano renderizable.
- Unifica creación y actualización: antes de crear una página, busca si ya existe documentación relacionada y actualízala si es el punto de entrada correcto.
- Para actualizaciones de proyecto completo, revisa README, `docs/`, `docs/examples/`, docstrings públicos, `.github/prompts/`, `.github/agents/` y `mkdocs.yml`.
- Diferencia siempre, con apartados claros, el contenido funcional del contenido técnico.
- Incluye ejemplos de funcionamiento cuando el código real permita verificarlos.
- Escribe docs en Markdown con secciones consistentes según propósito:
  - Funcional: Resumen funcional, Objetivo de negocio, Precondiciones, Flujo principal, Reglas de negocio, Límites.
  - Técnica: Responsabilidad, Arquitectura/flujo, API pública, Contratos de entrada/salida, Errores, Consideraciones operativas.
  - Ejemplos: Objetivo, Requisitos, Código, Ejecución esperada, Notas de seguridad.
- Incluye ejemplos que no requieran credenciales reales.
- Si generas ejemplos de salida, mantenlos deterministas (orden estable).
- Usa tablas para comparar opciones o mostrar configuraciones.
- Evita jerga técnica sin explicación.
- Si el proyecto tiene una CLI, documenta comandos con ejemplos de uso y salida esperada.
- Para cambios de seguridad, añade una sección de "Consideraciones de seguridad" que explique riesgos y mitigaciones.
- Si el proyecto tiene una API, documenta endpoints con ejemplos de request/response.
- Mantén la documentación actualizada con los cambios de código; no dejes secciones obsoletas.
- Si el proyecto es open source, enlaza la guía de contribución y explica el flujo mínimo para colaborar.
- Para proyectos con múltiples módulos o componentes, considera añadir un índice o tabla de contenidos para facilitar la navegación.
- Si el proyecto tiene dependencias externas, documenta claramente las versiones compatibles y cómo instalarlas.
- Si el proyecto tiene una sección de "Configuración", incluye ejemplos de archivos de configuración con valores comunes y explicaciones de cada opción.
- Para proyectos con una curva de aprendizaje, considera añadir una sección de "Primeros pasos" con un tutorial básico.
- Si el proyecto tiene casos de uso comunes, documenta cada caso con ejemplos específicos.
- Si el proyecto tiene una sección de "FAQ", actualízala regularmente con preguntas reales de usuarios o colaboradores.
- Si el proyecto tiene una sección de "Changelog", mantenla actualizada con cada versión y cambios relevantes.
- Si el proyecto tiene una sección de "Licencia", asegúrate de que esté clara y actualizada.
- Si el proyecto tiene una sección de "Contacto" o "Soporte", incluye información clara sobre cómo los usuarios pueden obtener ayuda o reportar problemas.
- Si el proyecto tiene una sección de "Créditos", reconoce a los colaboradores y contribuyentes de manera adecuada.
- Si el proyecto tiene una sección de "Roadmap", actualízala regularmente con planes futuros y objetivos a largo plazo.
- Si el proyecto tiene una sección de "Referencias", incluye enlaces a recursos externos relevantes, como documentación de dependencias, artículos relacionados o tutoriales.
- No utilices un solo prompt masivo para documentar todo el proyecto. Divide el trabajo en mapeo funcional, documentación técnica, ejemplos, diagramas y revisión final.
- No incluyas generación de documentación mediante APIs externas por el momento; documenta flujos manuales, locales o asistidos por agentes/prompts del repositorio.
- No reutilices nombres, rutas o clases de otros proyectos en ejemplos. Antes de escribir ejemplos, valida que las rutas existen en este repositorio y usa siempre `util_bbdd` como contexto del proyecto.

## Flujo estándar de creación o actualización

1. Inventariar fuentes reales: código, README, `docs/`, ejemplos, configuración, workflows y `mkdocs.yml`.
2. Mapear capacidades existentes sin asumir módulos por nombre histórico.
3. Decidir si se actualiza una página existente o se crea una nueva.
4. Generar primero el mapeo funcional, después la documentación técnica y finalmente los ejemplos.
5. Añadir o corregir la entrada correspondiente en `mkdocs.yml`.
6. Ejecutar o recomendar `mkdocs build` para validar navegación, Markdown y Mermaid.

## Prompt base para mapeo funcional

```text
Actúa como Senior Product Owner. Analiza el siguiente bloque de código Python y la documentación existente relacionada. No expliques variables ni clases internas. Genera Markdown con: 1. Objetivo de negocio. 2. Precondiciones necesarias. 3. Flujo principal del usuario. 4. Reglas de negocio críticas aplicadas. No inventes capacidades; si falta información, declárala como pendiente verificable.
```

## Prompt base para infografías Mermaid

```text
Basándote únicamente en la lógica verificable del servicio [Nombre], genera exclusivamente código Mermaid.js para un diagrama que ilustre la interacción entre el usuario, el componente principal y sus salidas. Omite detalles de implementación como variables internas, nombres de bases de datos, credenciales, puertos y rutas locales. Si el flujo no se puede inferir con seguridad, indica qué información falta en lugar de inventarla.
```


## Reglas Markdown (CRÍTICAS)
- Genera Markdown portable y legible.
- Prioriza CommonMark cuando sea suficiente.
- Se permiten extensiones Markdown ligeras y ampliamente soportadas por el repositorio o el renderer objetivo cuando aporten valor claro.
- No uses macros, directivas ni shortcodes propietarios.
- Evita HTML embebido salvo que no exista alternativa razonable y el uso quede justificado en la documentación o en la instrucción específica del módulo.
- Usa preferentemente:
  - `#`–`####` para títulos
  - listas `-` o `*`
  - tablas Markdown estándar
  - bloques de código ``` ```
  - enlaces relativos `[texto](ruta.md)`
- Si una visualización mejora sustancialmente la comprensión, puedes usar Mermaid en bloques de código fenced.
- No incluyas TOC automáticos.
