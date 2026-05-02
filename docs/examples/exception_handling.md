# Manejo de Excepciones

Ejemplo que muestra patrones de manejo de errores con la jerarquía de excepciones de `util_bbdd`.

**Cubre:**

- Capturar excepciones específicas (`DatabaseException`, `QueryTimeoutError`, `ValidationError`)
- Implementar una función de retry reutilizable
- Loguear errores apropiadamente
- Limpiar recursos con context manager

!!! warning "Jerarquía de excepciones"
    Todas las excepciones heredan de `DatabaseException`. Capturar `DatabaseException`
    como fallback garantiza que no escapen errores silenciosos.
    Ver [Guía de Excepciones](../EXCEPTIONS.md) para la jerarquía completa.

---

```python
--8<-- "examples/exception_handling.py"
```

---

!!! tip "Ver también"
    - [Excepciones](../EXCEPTIONS.md) — jerarquía completa y cuándo usar cada una
    - [API Reference](../API_REFERENCE.md#exceptions)
