# MySQL Variables Validator

Proporciona validación read-only de variables críticas MySQL/MariaDB antes de operaciones bulk de alto volumen, leyendo la configuración del servidor sin requerir privilegios SUPER y sin modificar nada.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A["BulkCrud.__init__()"] -->|una vez por engine| P["EngineReadinessAdvisor.report_once"]
    P -->|motor mysql/mariadb| B["MySQLVariableValidator"]
    B -->|SHOW VARIABLES WHERE Variable_name = …| C["MySQL/MariaDB"]
    C -->|max_allowed_packet\ninnodb_buffer_pool_size| B
    B -->|read_variables| D["dict de valores actuales"]
    B -->|validate required| E["dict variable → bool"]
    S["MySQLOptimalConfig.suggest(num_rows)"] -->|valores mínimos| E
    E --> F["Log INFO/WARNING"]
```

## 2. Modelo de Datos / Contratos

### API pública

Ambas clases se importan de `util_bbdd.connection.mariadb` (válidas para MariaDB y MySQL).

#### Clase `MySQLVariableValidator`

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `MySQLVariableValidator` | `(connection)` | Inicializa con una `Connection` de SQLAlchemy | `MySQLVariableValidator` |
| `read_variables` | `()` | Lee `max_allowed_packet` e `innodb_buffer_pool_size` | `dict[str, int]` (bytes) |
| `validate` | `(required: dict[str, int])` | Valida que valores actuales ≥ requeridos | `dict[str, bool]` |
| `log_summary` | `(required=None)` | INFO con los valores actuales y, con `required`, WARNING de los insuficientes | `None` |
| `format_bytes` | `(size_bytes)` | `"64.0 MB"`, `"1.0 GB"`… | `str` |

#### Dataclass `MySQLOptimalConfig`

| Método / Atributo | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `dev` | `()` *(estático)* | Config para desarrollo (< 50K filas) | `MySQLOptimalConfig` |
| `production` | `()` *(estático)* | Config para producción (100K–1M filas) | `MySQLOptimalConfig` |
| `high_volume` | `()` *(estático)* | Config para alto volumen (> 1M filas) | `MySQLOptimalConfig` |
| `suggest` | `(num_rows, avg_row_bytes=2000)` *(estático)* | Sugiere config óptima según tamaño de dataset | `MySQLOptimalConfig` |
| `innodb_buffer_pool_size` | `int` | Bytes recomendados de InnoDB buffer pool | — |
| `max_allowed_packet` | `int` | Bytes recomendados de max_allowed_packet | — |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `connection` | `Any` | Conexión SQLAlchemy activa | No puede ser `None`; `ValueError` si es `None` |
| `required` | `dict[str, int]` | Variables y valores mínimos en bytes | Claves deben ser nombres válidos de variables MySQL |
| `num_rows` | `int` | Número de filas a insertar | Para `suggest()`; determina el perfil recomendado |

### Contrato de salida

- **`read_variables`** — `dict[str, int]` con nombre de variable → valor en bytes.
- **`validate`** — `dict[str, bool]` con nombre de variable → `True` si válido, `False` si insuficiente.
- **`suggest`** — `MySQLOptimalConfig` frozen con `innodb_buffer_pool_size` y `max_allowed_packet` recomendados.

### Errores y casos especiales

| Error / Situación | Cuándo ocurre |
|---|---|
| `ValueError` | `connection=None` al crear el validador |
| Variable no encontrada | DEBUG log; se omite de `read_variables` sin error |
| Valor no entero, fila con forma inesperada o error de SQLAlchemy al leerla | WARNING log; se omite esa variable de `read_variables` y el resto se lee igual |
| Variable requerida que no se pudo leer | `validate` la da como `False` (WARNING) |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `MySQLVariableValidator` | Lectura y validación de variables del servidor MySQL/MariaDB |
| `MySQLOptimalConfig` | Perfiles predefinidos de configuración óptima por workload |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `sqlalchemy` | Conexión para ejecutar `SHOW VARIABLES` | Sí | Módulo no funciona |
| Ningún privilegio especial | `SHOW VARIABLES` lo puede ejecutar cualquier usuario conectado | — | — |

## 5. Ejemplos Relacionados

- [Ejemplo: Validación de Variables MySQL/MariaDB](../examples/mysql_variables_example.md) — Uso de `MySQLVariableValidator` y perfiles `MySQLOptimalConfig`
