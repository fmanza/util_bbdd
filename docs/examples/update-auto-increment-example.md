# Ejemplo: Reajuste de AUTO_INCREMENT en MariaDB

## 1. Contexto del Ejemplo

Genera el script que devuelve el contador `AUTO_INCREMENT` de cada tabla de un esquema MariaDB/MySQL a `MAX + 1`, sin ejecutar ninguna sentencia de modificación en el servidor.

Resuelve el problema de una carga masiva con claves primarias explícitas que deja el contador por detrás del máximo real: el siguiente `INSERT` sin clave choca con una fila existente. El script permite revisar el cambio, versionarlo o ejecutarlo en una ventana de mantenimiento.

## 2. Implementación de Referencia

```python
--8<-- "examples/update-auto-increment-example.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`UpdateAutoIncrement(engine)`**: recibe un `Engine` de SQLAlchemy con dialecto `mysql` o `mariadb`. Con cualquier otro dialecto lanza `InvalidDatabaseType`.
- **`salida_sql()`**: recorre las tablas base, localiza su columna `AUTO_INCREMENT`, lee `MAX(columna)` y devuelve `ALTER TABLE ... AUTO_INCREMENT = MAX + 1;` por tabla, ordenado por nombre. Solo ejecuta `SELECT`.
- **Ciclo de vida del `Engine`**: la utilidad no lo cierra. Por eso el ejemplo llama a `engine.dispose()` en un `finally`.
- **Credenciales**: la URL sale de una variable de entorno; nunca se escribe en el código.
- **Instantánea**: el máximo se lee al generar el script. Con escrituras concurrentes puede quedar corto, así que conviene ejecutarlo en una ventana sin escrituras.
- **Puede bajar contadores**: si tras borrar filas el contador iba por delante del máximo, el script lo reduce y esos identificadores pueden reasignarse. Revísalo si otro sistema guarda ids de filas eliminadas.

Ejemplo de salida para un esquema con tres tablas (`clientes` con máximo 41, `pedidos` vacía y `notas` sin `AUTO_INCREMENT`):

```text
-- 2 sentencia(s); revísalas antes de ejecutarlas
ALTER TABLE `clientes` AUTO_INCREMENT = 42;
ALTER TABLE `pedidos` AUTO_INCREMENT = 1;
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/update-auto-increment-example.py

# Ejecución (requiere un servidor MariaDB/MySQL accesible)
export UTIL_BBDD_EXAMPLE_URL="mariadb+pymysql://usuario:clave@servidor/tienda"
python docs/examples/update-auto-increment-example.py
```

Sin `UTIL_BBDD_EXAMPLE_URL` el ejemplo imprime cómo configurarla y termina sin error.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk-operations.md) — carga masiva y contadores de clave primaria
- **Referencia técnica**: [UpdateAutoIncrement](../api/update-auto-increment.md) — API, contratos y errores
- **Ejemplos relacionados**: [Validación de Variables MySQL/MariaDB](mysql-variables-example.md) — otra utilidad MariaDB de `connection/mariadb/`
