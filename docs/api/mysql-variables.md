# MySQL Variables Validator

## Responsabilidad

Proporciona validación **read-only** de variables críticas MySQL/MariaDB antes de ejecutar operaciones bulk de alto volumen. Lee configuración del servidor (`max_allowed_packet`, `innodb_buffer_pool_size`) y sugiere ajustes sin requerer privilegios SUPER.

**Módulos:**
- `MySQLVariableValidator` — Lector y validador de variables (acceso a INFORMACIÓN_SCHEMA)
- `MySQLOptimalConfig` — Perfiles predefinidos de configuración óptima por workload

**Integración:**
- Invocado automáticamente en `BulkCrud.__validate_mysql_config()` cuando se detecta MySQL/MariaDB
- Genera logs INFO/WARNING con recomendaciones
- No modifica configuración del servidor

## Arquitectura

```mermaid
flowchart TD
    A["BulkCrud.__init__()"] -->|motor mysql/mariadb?| B["MySQLVariableValidator"]
    B -->|SHOW VARIABLES| C["MySQL/MariaDB\nSERVER"]
    C -->|max_allowed_packet\ninnodb_buffer_pool_size| B
    B -->|read_variables| D["dict de valores\nactuales"]
    B -->|validate| E["MySQLOptimalConfig\n.suggest"]
    E -->|RECOMENDADO| F["Log INFO/WARNING"]
    F -->|stdout/logs| G["Aplicación"]
```

## Contrato de API

### `MySQLVariableValidator`

```python
class MySQLVariableValidator:
    """Validador de variables MySQL/MariaDB (read-only)."""

    def __init__(self, connection: Any) -> None:
        """Inicializa con conexión SQLAlchemy.

        Raises:
            ValueError: Si connection es None
        """

    def read_variables(self) -> dict[str, int]:
        """Lee variables críticas del servidor.

        Ejecuta `SHOW VARIABLES LIKE 'variable_name'` para cada variable.

        Returns:
            dict con variable_name → valor_en_bytes
            Ej: {'max_allowed_packet': 67108864, 'innodb_buffer_pool_size': 1073741824}

        Examples:
            >>> validator = MySQLVariableValidator(connection)
            >>> vars = validator.read_variables()
            >>> print(vars['max_allowed_packet'] / 1_048_576, 'MB')
            64 MB
        """

    def validate(self, required: dict[str, int]) -> dict[str, bool]:
        """Valida que valores actuales >= valores requeridos.

        Args:
            required: dict con variable_name → valor_mínimo (bytes)

        Returns:
            dict con variable_name → bool (True=válido, False=insuficiente)

        Examples:
            >>> required = {'max_allowed_packet': 67108864}  # 64 MB
            >>> result = validator.validate(required)
            >>> print(result)  # {'max_allowed_packet': True}
        """
```

### `MySQLOptimalConfig`

```python
@dataclass(frozen=True, slots=True)
class MySQLOptimalConfig:
    """Configuración recomendada de MySQL/MariaDB para bulk operations."""

    innodb_buffer_pool_size: int  # bytes
    max_allowed_packet: int  # bytes

    @staticmethod
    def dev() -> MySQLOptimalConfig:
        """Config para desarrollo (< 50K filas).

        - innodb_buffer_pool_size: 256 MB
        - max_allowed_packet: 16 MB (default)
        """

    @staticmethod
    def production() -> MySQLOptimalConfig:
        """Config para producción (100K–1M filas).

        - innodb_buffer_pool_size: 1 GB
        - max_allowed_packet: 64 MB (~1000 filas por INSERT multi-fila)
        """

    @staticmethod
    def high_volume() -> MySQLOptimalConfig:
        """Config para alto volumen (> 1M filas, 4+ GB RAM).

        - innodb_buffer_pool_size: 4 GB
        - max_allowed_packet: 128 MB (~5000 filas por INSERT multi-fila)
        """

    @staticmethod
    def suggest(num_rows: int, avg_row_bytes: int = 2000) -> MySQLOptimalConfig:
        """Sugiere config óptima según tamaño de dataset.

        Heurística:
        - num_rows ≤ 100K → dev()
        - 100K < num_rows ≤ 1M → production()
        - num_rows > 1M → high_volume()

        Args:
            num_rows: Número de filas a insertar
            avg_row_bytes: Bytes promedio por fila (default 2000)

        Returns:
            MySQLOptimalConfig recomendada

        Examples:
            >>> config = MySQLOptimalConfig.suggest(num_rows=500_000)
            >>> print(config.max_allowed_packet / 1_048_576, 'MB')
            64 MB
        """

    def format_bytes(self, value: int) -> str:
        """Formatea bytes a unidad legible (KB, MB, GB).

        Returns:
            str con unidad legible, ej "64 MB"
        """
```

## Contratos y Garantías

| Aspecto | Garantía | Excepción |
|---|---|---|
| **Permisos** | Solo lectura (INFORMACIÓN_SCHEMA). No requiere SUPER. | Si usuario no tiene acceso a INFORMACIÓN_SCHEMA, retorna dict vacío con warnings en logs. |
| **Performance** | 2 queries SHOW VARIABLES (muy rápido, <10ms). | Ninguna. |
| **Idempotencia** | Cada `read_variables()` ejecuta las queries nuevamente (no cachea). | Ninguna. |
| **Thread-safety** | Instancia validator NO es thread-safe (conexión de SQLAlchemy es). | Crear un validador por thread si es necesario. |
| **Backward compatibility** | API pública estable desde v0.10.0. | v0.9.x no tiene estos módulos. |

## Errores y Casos Especiales

### ValueError: connection no puede ser None
```python
>>> MySQLVariableValidator(None)
ValueError: connection no puede ser None
```

**Causa:** Conexión no inicializada.

**Solución:** Asegurar que `connection` es válido antes de crear el validador.

### Variable no encontrada en SHOW VARIABLES
```
DEBUG: Variable 'max_allowed_packet' no encontrada en SHOW VARIABLES
```

**Causa:** Variable no existe (ej. typo en nombre o versión muy antigua de MySQL).

**Solución:** Verificar nombre de variable y versión de MySQL con `SELECT VERSION()`.

### No se pudo parsear variable como int
```
WARNING: No se pudo parsear variable 'max_allowed_packet' como int: 16M
```

**Causa:** Valor retornado no es un número puro (ej. include suffix como "16M").

**Solución:** MySQL siempre retorna valores numéricos; si ves esto, contactar soporte.

### Error leyendo variable (permisos insuficientes)
```
WARNING: Error leyendo variable 'max_allowed_packet': Access denied for user 'app'@'localhost'
```

**Causa:** Usuario sin acceso a INFORMACIÓN_SCHEMA.

**Solución:** Ejecutar: `GRANT USAGE ON *.* TO 'app'@'localhost';` (USAGE da acceso a INFORMACIÓN_SCHEMA).

## Ejemplo Técnico Mínimo

```python
from sqlalchemy import create_engine
from util_bbdd.connection.mariadb._variables import MySQLVariableValidator
from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

# Conectar
engine = create_engine("mysql+pymysql://user:pass@localhost/db")

with engine.connect() as conn:
    # Leer variables actuales
    validator = MySQLVariableValidator(conn)
    actual = validator.read_variables()
    print(f"Actual: {actual}")

    # Sugerir configuración para 1M filas
    recommended = MySQLOptimalConfig.suggest(num_rows=1_000_000)
    print(f"Recomendado: innodb_buffer_pool_size={recommended.innodb_buffer_pool_size / 1_048_576:.0f} MB")

    # Validar
    is_valid = validator.validate({
        'max_allowed_packet': recommended.max_allowed_packet
    })
    print(f"Válido: {is_valid}")
```

## Integración en BulkCrud

Cuando instancias `BulkCrud` con MySQL/MariaDB:

```python
from util_bbdd.connection.managers import SyncDatabaseManager
from util_bbdd.connection.bulk import BulkCrud

manager = SyncDatabaseManager.get_sync_manager(
    engine_key="mysql_prod",
    use_pool=True
)
engine = manager.get_sqlalchemy_engine()

# BulkCrud.__init__ automáticamente:
# 1. Detecta que engine.dialect.name == 'mysql'
# 2. Crea MySQLVariableValidator(connection)
# 3. Lee variables y valida
# 4. Emite logs INFO/WARNING
bulk = BulkCrud(engine=engine, audit_manager=None)

# En stdout/logs:
# INFO: util_bbdd.connection.bulk: MySQL variables: max_allowed_packet=64 MB, innodb_buffer_pool_size=1 GB
# INFO: util_bbdd.connection.bulk: Configuración óptima para ~1M filas: max_allowed_packet=64 MB, innodb_buffer_pool_size=1 GB
```

## Referencias

- **CHANGELOG.md** → Sección [Unreleased] con detalles de implementación
- **src/util_bbdd/connection/mariadb/_variables.py** → Código fuente
- **src/util_bbdd/connection/mariadb/_config.py** → Configuraciones predefinidas
- **docs/functional/bulk-operations.md** → Guía de negocio
- **docs/examples/mysql-variables-example.md** → Ejemplos prácticos
