# Ejemplo: Comparación de Esquemas entre dos Bases de Datos

## 1. Contexto del Ejemplo

Detecta las diferencias estructurales entre dos bases de datos (tablas, columnas, índices, FKs, vistas) y genera reportes en todos los formatos disponibles: HTML, SQL de nivelación, Markdown, Excel y Word.

Resuelve la pregunta "¿qué ha cambiado entre producción y desarrollo?" de forma objetiva y reproducible, sin necesidad de comparar DDLs manualmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/schema_comparison.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`SchemaComparator.compare()`**: recibe dos `Inspector` de SQLAlchemy. Prefetch de columnas evita el problema N+1 (una sola query por esquema, no una por tabla).
- **`SchemaDiff` inmutable**: el resultado es frozen; no se puede modificar tras la comparación. Si se necesita actualizar, crear una nueva comparación.
- **`render_all()`**: genera todos los formatos en un solo paso. Usar `raise_on_error=True` si un fallo en un formato debe abortar el resto.
- **Script SQL de nivelación**: `SqlDiffReporter` genera sentencias `ALTER TABLE` para sincronizar el esquema destino con el origen. Revisar manualmente antes de ejecutar.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/schema_comparison.py

# Ejecución (requiere dos BDs accesibles)
python docs/examples/schema_comparison.py
```

Ver [Diff Reporters](diff_reporters.md) para detalles de cada formato de reporte.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Comparador de Esquemas](../functional/schema-comparison.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [Comparador y Reporters](../api/schema-comparator.md) — API completa de `SchemaComparator` y modelos `SchemaDiff`
- **Ejemplos relacionados**: [Diff Reporters](diff_reporters.md) — todos los formatos de reporte en detalle
