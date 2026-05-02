# Bulk Insert desde CSV

Ejemplo que muestra cómo cargar datos de un CSV con pandas, insertarlos masivamente y registrar auditoría de cambios.

**Cubre:**

- Cargar datos desde CSV con `pandas`
- Inserción masiva con `bulk_crud.bulk_insert_from_df()`
- Registro de auditoría en CSV con timestamps
- Manejo de `ValidationError` y `DatabaseException`

---

```python
--8<-- "examples/bulk_insert_csv.py"
```

---

!!! tip "Ver también"
    - [API Reference — Bulk Operations](../API_REFERENCE.md#bulk-operations)
    - [Manejo de Excepciones](exception_handling.md)
