# Diff Reporters

Ejemplo que demuestra todos los formatos disponibles para exportar comparativas de esquemas.

**Formatos cubiertos:**

| Reporter | Formato | Caso de uso |
|---|---|---|
| `HtmlDiffReporter` | `.html` | Exploración interactiva con filtrado y búsqueda |
| `SqlDiffReporter` | `.sql` | Script de nivelación dialect-específico |
| `MarkdownDiffReporter` | `.md` | Documentación portátil en repositorios |
| `ExcelDiffReporter` | `.xlsx` | Análisis en hojas de cálculo |
| `WordDiffReporter` | `.docx` | Reporte profesional |
| `SchemaDiffReporter` | todos | Fachada que coordina todos los reportes |

---

```python
--8<-- "examples/diff_reporters.py"
```

---

!!! tip "Ver también"
    - [Comparador de Esquemas](../COMPARATOR.md) — documentación de `SchemaComparator`
    - [Comparación de Esquemas](schema_comparison.md) — ejemplo completo con introspección
