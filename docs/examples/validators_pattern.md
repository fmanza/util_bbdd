# Ejemplo: Patrón de Validadores

## 1. Contexto del Ejemplo

Muestra el patrón de validadores por motor de `util_bbdd`: la factory `get_type_validator()` devuelve el validador adecuado (`SQLiteValidator`, `MariaDBValidator`, etc.) y cada validador comprueba los parámetros de una `QueryDefinition` mediante `validate_parameters()`, devolviendo `(is_valid, warnings)` **sin lanzar excepciones**.

Resuelve el problema de validar parámetros de query de forma uniforme pero con reglas específicas por motor, antes de ejecutar SQL contra la base de datos.

## 2. Implementación de Referencia

```python
--8<-- "examples/validators_pattern.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **Factory con registro**: `get_type_validator(db_type)` resuelve el validador desde `_VALIDATOR_REGISTRY`. Un motor no soportado lanza `ValueError` con la lista de motores válidos.
- **Contrato sin excepciones**: `validate_parameters()` devuelve `(False, [mensaje])` ante un error de validación en lugar de lanzar, de modo que el llamante decide cómo reaccionar.
- **Requeridos vs. advertencias**: un parámetro requerido ausente o vacío invalida (`is_valid=False`); otras condiciones (p. ej. `database_file` vacío en SQLite) solo añaden un *warning* manteniendo `is_valid=True`.
- **Cacheo por motor**: la factory cachea la instancia por `db_type` normalizado, por lo que llamadas repetidas devuelven el mismo objeto.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/validators_pattern.py

# Ejecución (no requiere servidor de BD; valida en memoria)
python docs/examples/validators_pattern.py
```

Salida esperada (resumen): el caso válido devuelve `(True, [])`, los parámetros ausente y vacío devuelven `(False, [...])`, el `database_file` vacío devuelve `(True, ['database_file parameter should be a valid path'])`, el motor no soportado lanza `ValueError` y la factory devuelve la misma instancia cacheada.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Patrón de Validadores](../functional/validators-pattern.md) — objetivo de negocio y reglas
- **Referencia técnica**: [Sistema de Validadores](../api/validators-system.md) — API y contratos
