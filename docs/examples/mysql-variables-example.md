# Ejemplos: Validación de Variables MySQL/MariaDB

## Ejemplo 1: Lectura Standalone (sin BulkCrud)

Leer variables MySQL actuales y obtener recomendaciones:

```python
from sqlalchemy import create_engine
from util_bbdd.connection.mariadb._variables import MySQLVariableValidator
from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

# Conectar a MySQL
engine = create_engine("mysql+pymysql://root:password@localhost/test_db")

with engine.connect() as conn:
    # Crear validador
    validator = MySQLVariableValidator(conn)

    # Leer variables actuales
    actual_vars = validator.read_variables()
    print("Variables actuales (en bytes):")
    for name, value in actual_vars.items():
        mb = value / 1_048_576
        print(f"  {name}: {mb:.1f} MB")

    # Obtener config recomendada para 500K filas
    recommended = MySQLOptimalConfig.suggest(num_rows=500_000)
    print("\nConfiguracion recomendada (para 500K filas):")
    print(f"  max_allowed_packet: {recommended.max_allowed_packet / 1_048_576:.1f} MB")
    print(f"  innodb_buffer_pool_size: {recommended.innodb_buffer_pool_size / 1_048_576:.1f} MB")

    # Validar
    is_valid = validator.validate({
        'max_allowed_packet': recommended.max_allowed_packet,
        'innodb_buffer_pool_size': recommended.innodb_buffer_pool_size
    })
    print("\nValidación:")
    for var, valid in is_valid.items():
        status = "✓ OK" if valid else "✗ Necesita ajuste"
        print(f"  {var}: {status}")
```

**Salida esperada (con config insuficiente):**
```
Variables actuales (en bytes):
  max_allowed_packet: 16.0 MB
  innodb_buffer_pool_size: 256.0 MB

Configuracion recomendada (para 500K filas):
  max_allowed_packet: 64.0 MB
  innodb_buffer_pool_size: 1024.0 MB

Validación:
  max_allowed_packet: ✗ Necesita ajuste
  innodb_buffer_pool_size: ✗ Necesita ajuste
```

## Ejemplo 2: Validación con BulkCrud (automática)

Cuando usas `BulkCrud`, la validación se ejecuta automáticamente al instanciar:

```python
from sqlalchemy import create_engine
import pandas as pd
from util_bbdd.connection.bulk import BulkCrud

engine = create_engine("mysql+pymysql://root:password@localhost/test_db")

# Instanciar BulkCrud con MySQL
# Internamente: __init__ → detecta mysql → MySQLVariableValidator.read_variables()
# → emite logs INFO/WARNING
bulk = BulkCrud(engine=engine)

# En stdout/logs verás:
# INFO: util_bbdd.connection.bulk: MySQL variables: max_allowed_packet=16 MB, innodb_buffer_pool_size=256 MB
# WARNING: max_allowed_packet por debajo de lo recomendado para bulk operations
# WARNING: Considera: SET GLOBAL max_allowed_packet=67108864; (requiere SUPER)

# Ahora puedes insertar datos
df = pd.DataFrame({
    'id': [1, 2, 3],
    'name': ['Alice', 'Bob', 'Charlie'],
    'email': ['alice@ex.com', 'bob@ex.com', 'charlie@ex.com']
})

# BulkCrud respeta max_allowed_packet automáticamente
# y ajusta max_rows_per_statement en MySQLMultiRowInsertStrategy
result = bulk.bulk_insert(
    table_name='users',
    data=df,
    chunk_size=1000
)

print(f"Insertadas {result.rows_processed} filas")
```

## Ejemplo 3: Perfiles de Configuración

Diferentes perfiles según el volumen de datos:

```python
from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

# Perfil Desarrollo (< 50K filas)
config_dev = MySQLOptimalConfig.dev()
print(f"Dev: max_allowed_packet={config_dev.max_allowed_packet / 1_048_576:.1f} MB")
# Output: Dev: max_allowed_packet=16.0 MB

# Perfil Producción (100K–1M filas)
config_prod = MySQLOptimalConfig.production()
print(f"Producción: max_allowed_packet={config_prod.max_allowed_packet / 1_048_576:.1f} MB")
# Output: Producción: max_allowed_packet=64.0 MB

# Perfil Alto Volumen (> 1M filas)
config_hv = MySQLOptimalConfig.high_volume()
print(f"Alto volumen: max_allowed_packet={config_hv.max_allowed_packet / 1_048_576:.1f} MB")
# Output: Alto volumen: max_allowed_packet=128.0 MB

# Heurística automática
config_auto = MySQLOptimalConfig.suggest(num_rows=2_000_000)
print(f"Auto (2M filas): {config_auto.max_allowed_packet / 1_048_576:.1f} MB")
# Output: Auto (2M filas): 128.0 MB
```

## Ejemplo 4: Mocking para Tests

Cómo mockear el validador en tests unitarios:

```python
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from util_bbdd.connection.mariadb._variables import MySQLVariableValidator
from util_bbdd.connection.bulk import BulkCrud

class TestMySQLValidation(unittest.TestCase):

    def test_bulk_crud_validates_mysql_vars(self):
        """Verificar que BulkCrud lee variables MySQL automáticamente."""

        # Crear mock de engine
        mock_engine = MagicMock()
        mock_engine.dialect.name = 'mysql'

        # Crear mock de conexión
        mock_connection = MagicMock()

        # Mock de SHOW VARIABLES: retorna Iterator con tuplas (nombre, valor_string)
        # ⚠️ Importante: execute() debe retornar un objeto que tenga fetchall()
        # que retorne una lista de tuplas
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ('max_allowed_packet', '67108864'),  # 64 MB en string
            ('innodb_buffer_pool_size', '1073741824')  # 1 GB en string
        ]
        mock_connection.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_connection

        # Instanciar BulkCrud con engine mockeado
        bulk = BulkCrud(engine=mock_engine)

        # Verificar que execute() fue llamado (lectura de variables)
        # Debería haber 2 calls: uno por cada variable crítica
        self.assertGreater(mock_connection.execute.call_count, 0)

    def test_validator_detects_low_packet_size(self):
        """Verificar que el validador detecta valores insuficientes."""

        # Mock de conexión con valores bajos
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ('max_allowed_packet', '16777216'),  # 16 MB (por debajo de recomendado)
        ]
        mock_connection.execute.return_value = mock_result

        # Crear validador
        validator = MySQLVariableValidator(mock_connection)
        actual = validator.read_variables()

        # Validar contra 64 MB (recomendado)
        is_valid = validator.validate({
            'max_allowed_packet': 64 * 1_048_576
        })

        # Debe fallar validación
        self.assertFalse(is_valid['max_allowed_packet'])
```

## Ejemplo 5: Ajuste de max_rows_per_statement

Cómo el sistema ajusta automáticamente el número de filas por statement según `max_allowed_packet`:

```python
from util_bbdd.connection.bulk import MySQLMultiRowInsertStrategy
import pandas as pd

# Simular lectura de max_allowed_packet del servidor
max_packet_bytes = 16 * 1_048_576  # 16 MB

# Calcular min_max_allowed_packet heurístico
strategy = MySQLMultiRowInsertStrategy()

# El método calcula power-of-2 más cercano
suggested_packet = strategy.get_min_max_allowed_packet(
    avg_row_bytes=2000,
    default_rows_per_stmt=1000
)

print(f"Paquete sugerido: {suggested_packet / 1_048_576:.0f} MB")
# Output: Paquete sugerido: 64 MB (power-of-2 más cercano >= al requerido)

# Si el servidor solo permite 16 MB, max_rows_per_statement se ajusta automáticamente
if max_packet_bytes < suggested_packet:
    # Recalcular rows_per_statement con constraint de 16 MB
    rows_per_stmt = max_packet_bytes // 2000  # Simplificado
    print(f"Ajustado a {rows_per_stmt} filas por statement (limitado por max_allowed_packet=16 MB)")
```

## Ejemplo 6: Decisiones de Configuración

Tabla de decisión para elegir perfil de configuración:

```python
from util_bbdd.connection.mariadb._config import MySQLOptimalConfig

def choose_config_for_scenario(scenario: str) -> MySQLOptimalConfig:
    """Elige config óptima según escenario."""

    scenarios = {
        'local_dev': {
            'num_rows': 50_000,
            'description': 'Desarrollo local con datos de prueba'
        },
        'staging': {
            'num_rows': 500_000,
            'description': 'Ambiente staging con datos realistas'
        },
        'production_daily': {
            'num_rows': 2_000_000,
            'description': 'Producción, carga diaria'
        },
        'production_bulk_migrate': {
            'num_rows': 50_000_000,
            'description': 'Migración de datos masivos (una vez)'
        }
    }

    if scenario not in scenarios:
        raise ValueError(f"Escenario desconocido: {scenario}")

    num_rows = scenarios[scenario]['num_rows']
    config = MySQLOptimalConfig.suggest(num_rows=num_rows)

    print(f"Escenario: {scenario}")
    print(f"  Filas: {num_rows:,}")
    print(f"  Descripción: {scenarios[scenario]['description']}")
    print(f"  max_allowed_packet: {config.max_allowed_packet / 1_048_576:.0f} MB")
    print(f"  innodb_buffer_pool_size: {config.innodb_buffer_pool_size / 1_048_576:.0f} MB")

    return config

# Usar
config = choose_config_for_scenario('production_daily')
```

**Salida:**
```
Escenario: production_daily
  Filas: 2,000,000
  Descripción: Producción, carga diaria
  max_allowed_packet: 128 MB
  innodb_buffer_pool_size: 4 GB
```
