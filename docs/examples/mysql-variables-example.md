# Ejemplo: Validación de Variables MySQL/MariaDB

## 1. Contexto del Ejemplo

Lee las variables críticas de configuración de un servidor MySQL/MariaDB (`max_allowed_packet`, `innodb_buffer_pool_size`) y verifica si son adecuadas para el volumen de datos previsto, sin requerir privilegios SUPER.

Resuelve el problema de descubrir en producción que la configuración del servidor es insuficiente para una carga masiva: `max_allowed_packet` demasiado bajo provoca `Lost connection` a mitad de inserción; `innodb_buffer_pool_size` insuficiente degrada la latencia exponencialmente.

## 2. Implementación de Referencia

```python
--8<-- "examples/mysql-variables-example.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`MySQLVariableValidator.read_variables()`**: ejecuta `SHOW VARIABLES LIKE ...` para cada variable crítica. Solo requiere acceso de lectura a `INFORMATION_SCHEMA`, no privilegios SUPER.
- **`MySQLOptimalConfig.suggest(num_rows)`**: heurística automática que retorna el perfil de configuración recomendado según el volumen: `dev()` para < 100K filas, `production()` para 100K–1M, `high_volume()` para > 1M.
- **Integración con `BulkCrud`**: al instanciar `BulkCrud` con un engine MySQL/MariaDB, la validación se ejecuta automáticamente y emite logs INFO/WARNING según el resultado.
- **Thread-safety**: `MySQLVariableValidator` no es thread-safe. Crear una instancia por hilo si se usa en contextos concurrentes.

Perfiles de configuración:

| Perfil | Filas objetivo | `max_allowed_packet` | `innodb_buffer_pool_size` |
|---|---|---|---|
| `dev()` | < 50K | 16 MB | 256 MB |
| `production()` | 100K–1M | 64 MB | 1 GB |
| `high_volume()` | > 1M | 128 MB | 4 GB |

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/mysql-variables-example.py

# Ejecución (requiere servidor MySQL/MariaDB accesible)
python docs/examples/mysql-variables-example.py
```

Si el servidor no está accesible, las variables se omiten del resultado con un WARNING en el log. No se lanza excepción.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk-operations.md) — sección de validación automática MySQL/MariaDB
- **Referencia técnica**: [MySQL Variables Validator](../api/mysql-variables.md) — API de `MySQLVariableValidator` y `MySQLOptimalConfig`
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — operación bulk que activa la validación automáticamente
