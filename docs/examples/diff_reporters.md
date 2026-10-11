# Ejemplo: Diff Reporters — Todos los Formatos de Reporte

## 1. Contexto del Ejemplo

Genera reportes de comparación de esquemas en los cinco formatos disponibles: HTML interactivo, script SQL de nivelación, Markdown portátil, Excel y Word profesional.

Resuelve el caso de equipos que necesitan comunicar diferencias de esquema a diferentes audiencias: los desarrolladores usan el script SQL, los arquitectos el HTML, los gestores el Word.

## 2. Implementación de Referencia

```python
--8<-- "examples/diff_reporters.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`SchemaDiffReporter` como fachada**: coordina todos los reporters individuales desde un único punto de entrada. Internamente instancia `HtmlDiffReporter`, `ExcelDiffReporter`, etc.
- **Dependencias opcionales**: Excel requiere `openpyxl`, Word requiere `python-docx`, HTML requiere `Jinja2`. Si no están instaladas, el reporter correspondiente lanza error.
- **`render_all(formats=...)`**: permite seleccionar un subconjunto de formatos. Omitir `formats` genera todos los disponibles.
- **Script SQL dialect-específico**: `SqlDiffReporter` usa el dialecto configurado para emitir SQL compatible con el motor destino. SQLite emite comentarios `-- ⚠ no soportado` para operaciones sin equivalente.

## 4. Ejecución y Pruebas

```bash
# Las dependencias de los reportes (openpyxl, python-docx, jinja2) van en la instalación base de util_bbdd

# Validación sintáctica
python -m py_compile docs/examples/diff_reporters.py

# Ejecución (crea dos BDs SQLite de ejemplo; no requiere servidor externo)
python docs/examples/diff_reporters.py
```

Ver [Comparación de Esquemas](schema_comparison.md) para el ejemplo completo con introspección.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Comparador de Esquemas](../functional/schema_comparison.md) — objetivo de negocio y casos de uso
- **Referencia técnica**: [Comparador y Reporters](../api/schema_comparator.md) — API de `SchemaDiffReporter` y reporters individuales
- **Ejemplos relacionados**: [Comparación de Esquemas](schema_comparison.md) — ejemplo completo con introspección previa
