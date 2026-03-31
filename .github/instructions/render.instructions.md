---
applyTo: "src/**/render/**/*.py"
---
# Renderizado de documentación

- La salida debe ser determinista: ordena alfabéticamente schemas/tablas/columnas.
- Formato Markdown con secciones consistentes: Resumen, Tablas, Columnas, PK, FK, Índices, Vistas.
- Incluye enlaces internos o anchors cuando el formato destino los soporte de forma estable y predecible.
- Para Excel, genera un formato propio y usa una librería específica (p.ej. openpyxl).
- Para Word, genera un formato propio y usa una librería específica (p.ej. python-docx).
- Para HTML, genera un formato propio y usa una librería específica (p.ej. Jinja2).
- Evita dependencias pesadas; prioriza soluciones ligeras y sin servicios externos.
- Mantén funciones de renderizado puras, recibiendo el modelo de metadatos y devolviendo el resultado sin efectos secundarios.
- Documenta claramente qué información se incluye en la documentación generada y cómo se estructura.
- Proporciona tests de integración que validen la salida generada contra un modelo de metadatos conocido.
- Si la generación de documentación no puede incluir cierta información (p.ej. comentarios de columnas en SQLite), documenta esta limitación y sugiere alternativas (p.ej. input manual o modelo intermedio).
