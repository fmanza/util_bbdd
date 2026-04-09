---
applyTo: "docs/**"
---
# Documentación

> **TL;DR** — Markdown con secciones estándar (Resumen, Instalación, Uso, Configuración, Ejemplos, FAQ). Sin credenciales reales. Ejemplos deterministas. Mantener actualizado con el código; no dejar secciones obsoletas. Tablas para comparar opciones.

- Escribe documentación clara, concisa y orientada a usuarios finales.
- Escribe docs en Markdown con secciones consistentes: Resumen, Instalación, Uso, Configuración, Ejemplos, FAQ.
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
