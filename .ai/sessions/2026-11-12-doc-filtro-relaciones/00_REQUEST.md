# Petición — 2026-11-12 · Filtro de tablas, relaciones y README de la documentación Markdown

Comentarios recibidos de util_bbdd_web y mejoras propuestas para util_bbdd. Fases pedidas: PLAN y AUDIT_PLAN; después
«IMPLEMENT - Pregunta lo que necesites» y «Hazlo todo» (VERSION incluida).

```text
util_bbdd_web
La ficha Markdown y HTML, ampliar el espacio hacia la derecha
Los enlaces en Markdown no funcionan
La exportación de Markdown tiene que tener instrucciones de cómo ejecutarlos
Se solicita un nivel de profundidad en Markdown y saca 2
Excluir tablas mediante un patrón y tener ayuda sobre ello
Qué alternativas me puedes ofrecer para tener una ayuda interactiva
Mejoras para util_bbdd
1. Exportar datos de referencia opcionales: catálogos, menús, roles (fichas como COB-DATOS-007)
2. Filtrar por prefijo o módulo al generar, para exportar solo MVG_* y su frontera
3. Exportar también el entorno Oracle y comparar entornos con SchemaComparator: deriva entre Calidad y producción
4. Publicar la 5.4.0 (o su especificación de formato) para que el contrato quede versionado
```

## Decisiones del usuario (IMPLEMENT)

| Pregunta | Respuesta |
|---|---|
| Alcance de 5.5.0 | L1 (filtro con frontera) + L2 (Referenciada por) + L3 (README) + L5 (texto de niveles). L4 (datos de referencia) a 5.6.0; L6 (especificación + JSON Schema) aparte |
| Frontera | Solo listado, sin ficha propia |
| Ámbito del filtro | Tablas y vistas (rutinas sin filtrar) |
| Comparación sin conexión entre dos `catalog.json` | Aplazada; solo receta en la guía |
