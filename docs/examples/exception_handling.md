# Ejemplo: Manejo de Excepciones

## 1. Contexto del Ejemplo

Muestra patrones de manejo de errores con la jerarquía de excepciones de `util_bbdd`: capturar excepciones específicas, implementar una función de retry reutilizable, loguear correctamente y limpiar recursos con context manager.

Resuelve el problema de silenciar o malinterpretar errores de BD en producción, donde la distinción entre un timeout de query y un error de configuración tiene impacto operativo distinto.

## 2. Implementación de Referencia

```python
--8<-- "examples/exception_handling.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **Jerarquía de excepciones**: todas heredan de `DatabaseException`. Capturar `DatabaseException` como fallback garantiza que no escapen errores silenciosos. Capturar `QueryTimeoutError` antes que `DatabaseException` asegura que el timeout tenga tratamiento específico.
- **Context manager para limpieza**: usar `with SyncDatabaseManager(...) as manager:` garantiza `close()` incluso si se lanza excepción, evitando conexiones huérfanas.
- **Función de retry**: el patrón `for attempt in range(max_retries)` con `time.sleep(delay)` creciente es el estándar para errores transitorios de red o pool agotado.
- **Logging, no print**: usar `logging` en lugar de `print` permite filtrar por nivel y redirigir a sistemas de observabilidad.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/exception_handling.py

# Ejecución (usa SQLite en memoria; no requiere servidor externo)
python docs/examples/exception_handling.py
```

Ver [Guía de Excepciones](../guides/exceptions.md) para la jerarquía completa de errores.

## 5. Referencias Relacionadas

- **Documentación funcional**: *No aplica para este módulo.* Las excepciones son transversales a todos los módulos.
- **Referencia técnica**: [Excepciones](../api/exceptions.md) — jerarquía completa y autodoc de la clase base
- **Guía**: [Guía de Excepciones](../guides/exceptions.md) — patrones de manejo y jerarquía completa
