# Ejemplo: Ejecución de Consultas con SyncQueryExecutor

## 1. Contexto del Ejemplo

Ejecuta consultas SQL libres y registradas por nombre sobre SQLite en memoria usando `SyncQueryExecutor`, demostrando los tipos de resultado `Row`, `Rows` y `RowOrNone`.

Resuelve la necesidad de ejecutar queries de forma desacoplada del gestor de BD: el executor recibe un proveedor y un liberador de conexión como callables, independizándose del tipo de manager subyacente.

## 2. Implementación de Referencia

```python
--8<-- "examples/query_execution_example.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`execute_custom_many` vs `execute_custom_one`**: el primero retorna siempre `list[tuple]` (vacío si no hay filas, nunca `None`); el segundo retorna `tuple | None`.
- **`execute_query_*`**: requiere que la query esté registrada en `QueryRegistry`. Si no está, lanza `QueryNotFoundError`. Útil para centralizar el SQL y evitar duplicación.
- **`connection_provider` y `connection_releaser`**: callables que el executor invoca para obtener y liberar conexiones. Permite usar cualquier tipo de conexión (pool, directa, mock en tests).
- **Parámetros nombrados**: usar siempre `:nombre` como placeholders. El executor pasa los parámetros al driver como bind params (no interpolación de strings), previniendo inyección SQL.

Para el ejecutor async (`AsyncQueryExecutor`), la única diferencia es que todos los métodos son corrutinas y el parámetro de timeout se llama `deadline_seconds`:

```python
filas = await executor.execute_custom_many(
    "SELECT id FROM tabla WHERE activo = :activo",
    params={"activo": 1},
    deadline_seconds=5.0,
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/query_execution_example.py

# Ejecución (usa SQLite en memoria; no requiere servidor externo)
python docs/examples/query_execution_example.py
```

Resultado esperado:

```
Activos: [(1, 'Ana'), (2, 'Luis')]
Usuario 3: ('Eva',)
Query registrada: (1, 'Ana')
```

## 5. Referencias Relacionadas

- **Documentación funcional**: [Ejecución de Consultas](../functional/query-execution.md) — objetivo de negocio y reglas de negocio
- **Referencia técnica**: [Ejecución de Consultas](../api/query-execution.md) — API de `SyncQueryExecutor`, `AsyncQueryExecutor` y `ResultNormalizer`
- **Referencia técnica**: [Registry y Resolver](../api/query-system.md) — API de `QueryRegistry` y `QueryResolver`
- **Ejemplos relacionados**: [Conectar e Introspeccionar Base de Datos](example-connect-introspect.md) — uso de `execute_custom_many` directamente desde el manager
