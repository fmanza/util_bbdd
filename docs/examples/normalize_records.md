# Ejemplo: Normalizar Registros para SQL

## 1. Contexto del Ejemplo

Los valores de un `DataFrame` de pandas no siempre los acepta un driver de base de datos: enteros de numpy, `NaT` y
`NaN` en lugar de `NULL`, o texto con espacios sobrantes. `normalize_records_for_sql` convierte los registros a tipos
nativos de Python antes de enviarlos, y `pandas_dtype_to_sqlalchemy` infiere el tipo de SQLAlchemy de cada columna.

`BulkCrud` aplica los dos pasos por su cuenta; el ejemplo los muestra aislados, sin base de datos, para ver qué llega
al driver.

## 2. Implementación de Referencia

```python
--8<-- "examples/normalize_records.py"
```

## 3. Explicación del Código

- **Nulos**: `NaT` (fecha vacía) y `NaN` (número vacío) pasan a `None`, que el driver envía como `NULL`.
- **Tipos nativos**: los enteros de numpy pasan a `int` y las fechas de pandas a `datetime.datetime`.
- **Texto recortado**: `" Ana "` llega como `"Ana"`.
- **Longitud de `String`**: se calcula sobre el valor sin recortar, más uno (`" Ana "` mide 5, de ahí
  `String(length=6)`).
- **Clase o instancia**: `pandas_dtype_to_sqlalchemy` devuelve la clase (`Integer`) cuando el tipo no lleva
  parámetros y una instancia cuando sí (`String(length=6)`). El ejemplo los muestra todos instanciados.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/normalize_records.py

# Ejecución (no usa base de datos)
python docs/examples/normalize_records.py
```

Resultado esperado:

```text
{'id': 1, 'alta': datetime.datetime(2026, 1, 1, 0, 0), 'nombre': 'Ana', 'saldo': 10.5}
{'id': 2, 'alta': None, 'nombre': 'Luis', 'saldo': None}
id: Integer()
alta: DateTime()
nombre: String(length=6)
saldo: Float()
```

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk_operations.md) — reglas de la carga masiva
- **Referencia técnica**: [Normalización de Datos](../api/normalize.md) — reglas de conversión y tipos inferidos
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — la normalización dentro de una carga real
