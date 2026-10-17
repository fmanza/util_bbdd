# ADR-004: Resolución Perezosa de Versión para Selección de Dialecto de Oracle

## 1. Contexto y Problema

Las versiones de Oracle tienen diferencias significativas en sus APIs que requieren consultas de metadatos distintas:

- **Oracle 11g (11.2.x)**: Carece de vista `ALL_TAB_IDENTITY_COLS` (añadida en 12c); no hay introspeción de columnas identity
- **Oracle 12c y posterior**: Soporte completo de columnas IDENTITY mediante `ALL_TAB_IDENTITY_COLS`

La implementación anterior asumía que todas las conexiones de Oracle eran 12c+, causando que las consultas de metadatos fallaran en 11g con `ORA-00942: table or view does not exist` al intentar consultar `ALL_TAB_IDENTITY_COLS`.

Además, la inicialización de la conexión de Oracle tiene limitaciones de rendimiento y compatibilidad:
- **Thin mode** (predeterminado en python-oracledb): Python puro, solo asincrónico, solo Oracle 12c+
- **Thick mode** (requiere Instant Client): Solo sincrónico, soporta Oracle 11g a 23c, requiere inicialización global

La librería necesitaba una forma de:
1. Detectar automáticamente la versión del servidor Oracle y seleccionar el dialecto correcto (OracleCatalog vs Oracle11Catalog)
2. Soportar tanto thin mode (asincrónico) como thick mode (sincrónico con soporte de 11g)
3. Minimizar el costo de las consultas de metadatos y la inicialización de conexiones
4. Garantizar inicialización segura para hilos y asincrónica

## 2. Decisión

### 2.1 Resolución Perezosa de Versión

Implementar **resolución perezosa de versión** en `CatalogSource` y `AsyncCatalogSource`:

1. **En la primera consulta de metadatos** (`current_schema()` o `_load(kind, schema, tables)`), verificar si el dialecto implementa el protocolo opcional `VersionedCatalogDialect`:
   - `server_version_sql()` → Devuelve una consulta SQL para obtener la versión del servidor
   - `for_server_version(version_tuple)` → Devuelve la variante de dialecto apropiada basada en la versión

2. **Ejecutar la consulta de versión** si el protocolo está implementado:
   ```python
   version_sql = dialect.server_version_sql()  # "SELECT version FROM product_component_version..."
   rows = executor.fetch_all(version_sql, {})
   version_tuple = tuple(int(x) for x in str(rows[0][0]).split("."))  # (11, 2, 0, 4, 0)
   ```

3. **Resolver la variante de dialecto** llamando a `for_server_version()`:
   ```python
   resolved_dialect = dialect.for_server_version(version_tuple)
   self.dialect = resolved_dialect
   ```

4. **Cachear la resolución** usando la bandera `_version_resolved` para prevenir consultas repetidas

**Justificación:**
- Difiere la introspeción del servidor hasta el primer uso real de metadatos, no en el establecimiento de conexión
- Una única consulta de base de datos por conexión (amortizada sobre la duración del esquema)
- Sin cambios a la API pública para detección de versión (automática y transparente)
- Mantiene compatibilidad con dialectos que no implementan `VersionedCatalogDialect`

### 2.2 Variantes de Dialecto de Oracle

Definir dos implementaciones de OracleCatalog:

- **OracleCatalog** (12c+): Suite SQL completa en `_SQL` incluyendo `Kind.IDENTITY`
- **Oracle11Catalog** (11g): Suite SQL en `_SQL_11G` omitiendo `Kind.IDENTITY` y consultas asociadas

Detección de versión: `for_server_version((11, 2, 0, 4, 0)) → Oracle11Catalog()` ; `for_server_version((19, 0, 0, 0, 0)) → OracleCatalog()`

### 2.3 Arquitectura de Thick Mode

Separar la inicialización de thick mode del establecimiento de conexión para soportar patrones tanto sincrónico como asincrónico:

1. **Módulo central** (`src/util_bbdd/connection/oracle/_thick_mode.py`):
   - Garantía de llamada única mediante bandera global `ORACLE_THICK_MODE_INITIALIZED`
   - Inicialización segura para hilos mediante `threading.Lock`
   - Función: `init_oracle_thick_mode(client_path: str) → None`

2. **Flujo de conexión sincrónica**:
   - Usuario establece `oracle_thick_mode=True, oracle_client_path="/ruta/a/instant/client"`
   - ConnectionFactory llama a `init_oracle_thick_mode()` antes de la creación del motor
   - Todas las conexiones subsiguientes usan thick mode

3. **Flujo de conexión asincrónica**:
   - Protección: `AsyncConnectionFactory` lanza `ConnectionError` si `oracle_thick_mode=True`
   - Justificación: Async usa solo thin mode; thick mode es inherentemente sincrónico

4. **Detección de versión con thick mode**:
   - Thick mode se inicializa antes de la creación del motor
   - La consulta de versión se ejecuta mediante flujo de conexión normal
   - La resolución de dialecto es perezosa y no se ve afectada por la elección de thick mode

**Seguridad para Hilos:**
- `_THICK_MODE_LOCK` (threading.Lock) protege la inicialización
- El primer hilo que llama a `init_oracle_thick_mode()` inicializa; otros omiten
- Sin condiciones de carrera; inicialización idempotente

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| **Ventaja** | Detección automática de versión: no se requiere selección manual de dialecto |
| **Ventaja** | Una única consulta de metadatos por conexión para detección de versión; cacheada después del primer uso |
| **Ventaja** | Latencia mínima: consulta de versión diferida al primer uso de metadatos (no en inicio de conexión) |
| **Ventaja** | Soporte de Oracle 11g mediante thick mode con Instant Client 19 |
| **Ventaja** | Transparente para código existente: resolución de versión es automática, perezosa y cacheada |
| **Ventaja** | Seguro para hilos y asincrónico: inicialización de thick mode no puede tener carreras ni bloquear async |
| **Compensación** | Pequeña latencia en primera consulta de metadatos (un viaje redondo adicional de base de datos para detección de versión) |
| **Compensación** | Thick mode requiere configuración explícita; usuario debe proporcionar `oracle_client_path` |
| **Cambio Importante** (Menor) | Aplicaciones asincrónicas no pueden usar thick mode; deben usar thin mode (solo 12c+). Lanza `ConnectionError` claro al intentar. |

## 4. Enfoques Alternativos Considerados

| Alternativa | Ventajas | Desventajas | Razón Rechazada |
|---|---|---|---|
| **Detección de versión ansiosa** (en tiempo de conexión) | Detecta versión temprano; falla rápido en 11g+ sin Instant Client | Bloquea inicio de conexión para todas las aplicaciones; gastos generales para usuarios no-Oracle; sin beneficio para async (falla temprano en lugar de perezoso) | Inicialización ansiosa derrota beneficios async; gastos generales inaceptables |
| **Selección manual de dialecto** (usuario especifica) | No requiere consulta de versión; transparente para librería | Carga API en usuarios; fácil seleccionar dialecto incorrecto; requiere conciencia de versión de aplicación | No determinista; propenso a error de usuario |
| **Número de versión integrado** (basado en configuración) | Fuente única de verdad | Duplica documentación de Oracle; requiere actualización por versión; sin detección automática | Mantenimiento manual; no es autodocumentado |
| **Reinicialización en cada consulta** (sin caching) | Simplifica código; sin bandera necesaria | N consultas por conexión; degradación de rendimiento significativa en esquemas grandes | Inaceptable para esquemas grandes (100+ tablas × 10+ consultas de metadatos cada una) |
| **Registro global de versiones** (basado en semáforo) | Previene cualquier reinicialización de thick mode | Bloqueo complejo; sin beneficio sobre bandera de inicialización única | Complejidad innecesaria |

## 5. Detalles de Implementación

### 5.1 Cambios a CatalogSource (src/util_bbdd/metadata/source.py)

```python
class CatalogSource:
    def __init__(self, dialect, executor, source_id=None, cache=None, default_schema=None):
        self.dialect = dialect
        self.executor = executor
        self._version_resolved = False  # Bandera: versión detectada y dialecto resuelto
        self._default_schema = default_schema
        ...

    def _resolve_dialect(self) -> None:
        """Resolver variante de dialecto basada en versión del servidor (p.ej., Oracle 11g vs 12c+)."""
        if self._version_resolved:
            return  # Ya resuelto; omitir
        self._version_resolved = True

        # Verificar si dialecto implementa protocolo VersionedCatalogDialect
        if not hasattr(self.dialect, "server_version_sql") or not hasattr(self.dialect, "for_server_version"):
            return  # No versionado; usar tal cual

        # Consultar versión del servidor
        version_sql = self.dialect.server_version_sql()
        rows = self.executor.fetch_all(version_sql, {})
        if not rows or not rows[0]:
            return  # Versión no disponible; mantener predeterminado

        # Analizar versión: "11.2.0.4.0" → (11, 2, 0, 4, 0)
        version_str = str(rows[0][0]).strip()
        try:
            version_tuple = tuple(int(x) for x in version_str.split("."))
        except (ValueError, AttributeError):
            return  # Versión malformada; mantener predeterminado

        # Resolver variante
        resolved_dialect = self.dialect.for_server_version(version_tuple)
        self.dialect = resolved_dialect

    def current_schema(self) -> str:
        self._resolve_dialect()  # Resolución perezosa en primera llamada
        ...
```

### 5.2 Cambios a OracleCatalog (src/util_bbdd/metadata/oracle/catalog.py)

```python
class OracleCatalog(CatalogDialect):
    @staticmethod
    def server_version_sql() -> str:
        """SQL para consultar versión de Oracle."""
        return "SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%' AND ROWNUM = 1"

    @staticmethod
    def for_server_version(version_tuple: tuple[int, ...]) -> 'OracleCatalog':
        """Devolver variante de catálogo apropiada basada en versión de Oracle."""
        if version_tuple and version_tuple[0] < 12:
            return Oracle11Catalog()
        return OracleCatalog()

class Oracle11Catalog(OracleCatalog):
    """Catálogo para Oracle 11g (omite consultas de columnas IDENTITY)."""
    _sql = _SQL_11G  # Excluye Kind.IDENTITY
```

### 5.3 Inicialización de Thick Mode (src/util_bbdd/connection/oracle/_thick_mode.py)

```python
import threading

_THICK_MODE_LOCK = threading.Lock()
ORACLE_THICK_MODE_INITIALIZED = False

def init_oracle_thick_mode(client_path: str) -> None:
    """Inicializar thick mode de Oracle (seguro para hilos, llamada única)."""
    global ORACLE_THICK_MODE_INITIALIZED
    
    with _THICK_MODE_LOCK:
        if ORACLE_THICK_MODE_INITIALIZED:
            return  # Ya inicializado
        
        oracledb.init_oracle_client(lib_dir=client_path)
        ORACLE_THICK_MODE_INITIALIZED = True
```

### 5.4 Integración con ConnectionFactory

**Sincrónico (connection_oracle.py):**
```python
if oracle_thick_mode:
    if not oracle_client_path:
        raise ValueError("oracle_client_path requerido cuando oracle_thick_mode=True")
    init_oracle_thick_mode(oracle_client_path)
```

**Asincrónico (async_connection_oracle.py):**
```python
if ORACLE_THICK_MODE_INITIALIZED:
    raise ConnectionError("Modo asincrónico incompatible con thick mode de Oracle; usar thin mode (solo 12c+)")
```

## 6. Estrategia de Prueba

### 6.1 Pruebas Unitarias

- **test_oracle_11_catalog_detection.py**: Detección de versión de OracleCatalog (método for_server_version)
- **test_catalog_source_oracle_version.py**: Resolución perezosa de CatalogSource con executor simulado

### 6.2 Pruebas de Integración

- Contenedor Oracle 11g (docker-compose.bench.yml) con validación de detección de versión
- Inicialización de thick mode en múltiples hilos (creación de conexión concurrente)
- Protección asincrónica contra thick mode (ConnectionError lanzado)

### 6.3 Validación de Recuento de Consultas

- Verificar consulta de versión única por conexión (test_query_counts.py existente extendido para Oracle)
- Sin consultas de versión redundantes en acceso de metadatos repetido

## 7. Estado y Revisión

**Estado:** ACEPTADO E IMPLEMENTADO (2026-10-05, commit `dca734ed`, versión 0.32.0; fases 1-8)

**Commits Clave:**
- Fases 1-6: Implementación principal (resolución de versión, thick mode, infraestructura de prueba)
- Fase 7: Pruebas de integración (22 pruebas para detección de versión y resolución perezosa)
- Fase 8: Documentación (actualizaciones de drivers.md, ADR-004, runtime.md, CHANGELOG.md)

**Resultados de Prueba:**
- 5108 pruebas pasando (5086 línea base + 22 nuevas pruebas de Oracle 11g)
- 496 pruebas saltadas
- 0 fallos

**Fecha de Última Revisión:** 2026-10-16 (unificación en un solo fichero en español; referencias verificadas contra el
código)

---

## Referencias

- **Implementación de CatalogSource**: `src/util_bbdd/metadata/source.py`
- **Variantes de OracleCatalog**: `src/util_bbdd/metadata/oracle/catalog.py`
- **Thick Mode**: `src/util_bbdd/connection/oracle/_thick_mode.py`
- **Guía de Drivers**: [docs/guides/drivers.md](../guides/drivers.md)
- **Suite de Pruebas**: `tests/unit/metadata/test_oracle_11_catalog_detection.py`, `tests/unit/metadata/test_catalog_source_oracle_version.py`
