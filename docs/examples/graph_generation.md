# Generación de Grafos de Relaciones

Ejemplo que muestra cómo introspeccionar metadatos y generar grafos de relaciones entre tablas.

**Cubre:**

- Introspeccionar metadatos de BD
- Generar grafo de relaciones con `GraphvizRelationshipGraphExt`
- Exportar a SVG/PNG
- Configurar profundidad y dirección del grafo

!!! note "Dependencia opcional"
    Requiere el extra `analysis`: `pip install util_bbdd[analysis]`
    El extra instala `graphviz` (Python wrapper). Adicionalmente necesitas
    [Graphviz binarios](https://graphviz.org/download/) instalados en el sistema.

---

```python
--8<-- "examples/graph_generation.py"
```

---

!!! tip "Ver también"
    - [API Reference — Analysis & Graphs](../API_REFERENCE.md#analysis--graphs)
    - [Instalación](../INSTALLATION.md) — extras disponibles
