# Comparación de Esquemas

Ejemplo completo que muestra cómo detectar diferencias estructurales entre dos bases de datos y generar reportes en todos los formatos disponibles.

**Cubre:**

- Conectar a dos BDs (o schemas)
- Comparar estructura con `SchemaComparator`
- Generar reportes con `SchemaDiffReporter` (HTML, SQL, Markdown, Excel, Word)
- Exportar resultados a JSON

---

```python
--8<-- "examples/schema_comparison.py"
```

---

!!! tip "Ver también"
    - [Comparador de Esquemas](../COMPARATOR.md) — documentación completa de la API
    - [Diff Reporters](diff_reporters.md) — todos los formatos de reporte en detalle
