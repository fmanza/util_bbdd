---
applyTo: "**/*.py"
---
# Python – Estándares para esta librería

## Estilo
- Python 3.12+ o la versión definida en `pyproject.toml`; mantén consistencia con la configuración real del proyecto.
- Docstrings estilo Google o NumPy (elige uno y mantén consistencia).
- Usa `pathlib.Path` para rutas.
- Prefiere dataclasses para estructuras de metadatos.

## Diseño de API
- Expón modelos de metadatos (Schema, Table, Column, Relationship).
- Separa: extracción (introspección) vs render (generación de docs).
- Mantén funciones puras para renderizado siempre que sea posible.

## Errores
- Define excepciones propias (p.ej., `IntrospectionError`, `RenderError`).
- Mensajes de error accionables (qué falló y cómo corregir).
