# Ejemplo: Validación de Variables MySQL/MariaDB

## 1. Contexto del Ejemplo

Lee las variables críticas de configuración de un servidor MySQL/MariaDB (`max_allowed_packet`, `innodb_buffer_pool_size`) y verifica si son adecuadas para el volumen de datos previsto, sin requerir privilegios SUPER.

Resuelve el problema de descubrir en producción que la configuración del servidor es insuficiente para una carga masiva: `max_allowed_packet` demasiado bajo provoca `Lost connection` a mitad de inserción; `innodb_buffer_pool_size` insuficiente obliga a leer de disco y degrada la carga.

## 2. Implementación de Referencia

```python
--8<-- "examples/mysql_variables_example.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`MySQLVariableValidator.read_variables()`**: ejecuta `SHOW VARIABLES LIKE ...` para cada variable crítica; no requiere privilegios especiales. Se importa de `util_bbdd.connection.mariadb` (sirve para MySQL y MariaDB).
- **Conexión simulada**: los ejemplos 1, 2 y 5 usan un mock que responde a `SHOW VARIABLES LIKE '<nombre>'`; en uso real se pasa una `Connection` de SQLAlchemy.
- **`MySQLOptimalConfig.suggest(num_rows)`**: heurística que retorna el perfil recomendado según el volumen: `dev()` hasta 100K filas, `production()` hasta 1M, `high_volume()` por encima.
- **Integración con `BulkCrud`**: al crear una `BulkCrud` con un engine MySQL/MariaDB, la primera vez por engine se registra un «ENGINE READINESS REPORT» con estas variables (OK, o WARN con el `SET GLOBAL` recomendado). El ejemplo 6 lo muestra con `UTIL_BBDD_EXAMPLE_URL`.
- **Thread-safety**: `MySQLVariableValidator` no es thread-safe. Crear una instancia por hilo si se usa en contextos concurrentes.

Perfiles de configuración:

| Perfil | Filas objetivo | `max_allowed_packet` | `innodb_buffer_pool_size` |
|---|---|---|---|
| `dev()` | ≤ 100K | 16 MB | 256 MB |
| `production()` | ≤ 1M | 64 MB | 1 GB |
| `high_volume()` | > 1M | 128 MB | 4 GB |

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/mysql_variables_example.py

# Ejecución sin servidor (conexiones simuladas)
python docs/examples/mysql_variables_example.py

# Con el informe real de BulkCrud (ejemplo 6) contra un MySQL/MariaDB de pruebas
UTIL_BBDD_EXAMPLE_URL="mysql+pymysql://usuario:clave@servidor/bd" python docs/examples/mysql_variables_example.py
```

Si una variable no se puede leer (error de SQLAlchemy), se omite de `read_variables()` con un WARNING en el log y `validate()` la da como `False`. No se lanza excepción.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk_operations.md) — sección de validación automática MySQL/MariaDB
- **Referencia técnica**: [MySQL Variables Validator](../api/mysql_variables.md) — API de `MySQLVariableValidator` y `MySQLOptimalConfig`
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — operación bulk que activa la validación automáticamente
