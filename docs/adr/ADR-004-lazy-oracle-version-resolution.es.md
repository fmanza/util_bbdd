# ADR-004: Resoluci\u00f3n Perezosa de Versi\u00f3n para Selecci\u00f3n de Dialecto de Oracle

## 1. Contexto y Problema

Las versiones de Oracle tienen diferencias significativas en sus APIs que requieren consultas de metadatos distintas:

- **Oracle 11g (11.2.x)**: Carece de vista `ALL_TAB_IDENTITY_COLS` (a\u00f1adida en 12c); no hay introspeci\u00f3n de columnas identity
- **Oracle 12c y posterior**: Soporte completo de columnas IDENTITY mediante `ALL_TAB_IDENTITY_COLS`

La implementaci\u00f3n anterior asumía que todas las conexiones de Oracle eran 12c+, causando que las consultas de metadatos fallaran en 11g con `ORA-00942: table or view does not exist` al intentar consultar `ALL_TAB_IDENTITY_COLS`.

Además, la inicializaci\u00f3n de la conexi\u00f3n de Oracle tiene limitaciones de rendimiento y compatibilidad:
- **Thin mode** (predeterminado en python-oracledb): Python puro, solo asincr\u00f3nico, solo Oracle 12c+
- **Thick mode** (requiere Instant Client): Solo sincr\u00f3nico, soporta Oracle 11g a 23c, requiere inicializaci\u00f3n global

La librer\u00eda necesitaba una forma de:
1. Detectar autom\u00e1ticamente la versi\u00f3n del servidor Oracle y seleccionar el dialecto correcto (OracleCatalog vs Oracle11Catalog)
2. Soportar tanto thin mode (asincr\u00f3nico) como thick mode (sincr\u00f3nico con soporte de 11g)
3. Minimizar el costo de las consultas de metadatos y la inicializaci\u00f3n de conexiones
4. Garantizar inicializaci\u00f3n segura para hilos y asincr\u00f3nica

## 2. Decisi\u00f3n

### 2.1 Resoluci\u00f3n Perezosa de Versi\u00f3n

Implementar **resoluci\u00f3n perezosa de versi\u00f3n** en `CatalogSource` y `AsyncCatalogSource`:

1. **En la primera consulta de metadatos** (`current_schema()` o `_load(kind, schema, tables)`), verificar si el dialecto implementa el protocolo opcional `VersionedCatalogDialect`:
   - `server_version_sql()` → Devuelve una consulta SQL para obtener la versi\u00f3n del servidor
   - `for_server_version(version_tuple)` → Devuelve la variante de dialecto apropiada basada en la versi\u00f3n

2. **Ejecutar la consulta de versi\u00f3n** si el protocolo est\u00e1 implementado:
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

4. **Cachear la resoluci\u00f3n** usando la bandera `_version_resolved` para prevenir consultas repetidas

**Justificaci\u00f3n:**
- Difiere la introspeci\u00f3n del servidor hasta el primer uso real de metadatos, no en el establecimiento de conexi\u00f3n
- Una \u00fanica consulta de base de datos por conexi\u00f3n (amortizada sobre la duraci\u00f3n del esquema)
- Sin cambios a la API p\u00fablica para detecci\u00f3n de versi\u00f3n (autom\u00e1tica y transparente)
- Mantiene compatibilidad con dialectos que no implementan `VersionedCatalogDialect`

### 2.2 Variantes de Dialecto de Oracle

Definir dos implementaciones de OracleCatalog:

- **OracleCatalog** (12c+): Suite SQL completa en `_SQL` incluyendo `Kind.IDENTITY`
- **Oracle11Catalog** (11g): Suite SQL en `_SQL_11G` omitiendo `Kind.IDENTITY` y consultas asociadas

Detecci\u00f3n de versi\u00f3n: `for_server_version((11, 2, 0, 4, 0)) → Oracle11Catalog()` ; `for_server_version((19, 0, 0, 0, 0)) → OracleCatalog()`

### 2.3 Arquitectura de Thick Mode

Separar la inicializaci\u00f3n de thick mode del establecimiento de conexi\u00f3n para soportar patrones tanto sincr\u00f3nico como asincr\u00f3nico:

1. **M\u00f3dulo central** (`src/util_bbdd/connection/oracle/_thick_mode.py`):
   - Garant\u00eda de llamada \u00fanica mediante bandera global `ORACLE_THICK_MODE_INITIALIZED`
   - Inicializaci\u00f3n segura para hilos mediante `threading.Lock`
   - Funci\u00f3n: `init_oracle_thick_mode(client_path: str) → None`

2. **Flujo de conexi\u00f3n sincr\u00f3nica**:
   - Usuario establece `oracle_thick_mode=True, oracle_client_path="/ruta/a/instant/client"`
   - ConnectionFactory llama a `init_oracle_thick_mode()` antes de la creaci\u00f3n del motor
   - Todas las conexiones subsiguientes usan thick mode

3. **Flujo de conexi\u00f3n asincr\u00f3nica**:
   - Protecci\u00f3n: `AsyncConnectionFactory` lanza `ConnectionError` si `oracle_thick_mode=True`
   - Justificaci\u00f3n: Async usa solo thin mode; thick mode es inherentemente sincr\u00f3nico

4. **Detecci\u00f3n de versi\u00f3n con thick mode**:
   - Thick mode se inicializa antes de la creaci\u00f3n del motor
   - La consulta de versi\u00f3n se ejecuta mediante flujo de conexi\u00f3n normal
   - La resoluci\u00f3n de dialecto es perezosa y no se ve afectada por la elecci\u00f3n de thick mode

**Seguridad para Hilos:**
- `_THICK_MODE_LOCK` (threading.Lock) protege la inicializaci\u00f3n
- El primer hilo que llama a `init_oracle_thick_mode()` inicializa; otros omiten
- Sin condiciones de carrera; inicializaci\u00f3n idempotente

## 3. Consecuencias

| Tipo | Descripci\u00f3n |
|---|---|
| **Ventaja** | Detecci\u00f3n autom\u00e1tica de versi\u00f3n: no se requiere selecci\u00f3n manual de dialecto |
| **Ventaja** | Una \u00fanica consulta de metadatos por conexi\u00f3n para detecci\u00f3n de versi\u00f3n; cacheada despu\u00e9s del primer uso |
| **Ventaja** | Latencia m\u00ednima: consulta de versi\u00f3n diferida al primer uso de metadatos (no en inicio de conexi\u00f3n) |
| **Ventaja** | Soporte de Oracle 11g mediante thick mode con Instant Client 19 |
| **Ventaja** | Transparente para c\u00f3digo existente: resoluci\u00f3n de versi\u00f3n es autom\u00e1tica, perezosa y cacheada |
| **Ventaja** | Seguro para hilos y asincr\u00f3nico: inicializaci\u00f3n de thick mode no puede tener carreras ni bloquear async |
| **Compensaci\u00f3n** | Peque\u00f1a latencia en primera consulta de metadatos (un viaje redondo adicional de base de datos para detecci\u00f3n de versi\u00f3n) |
| **Compensaci\u00f3n** | Thick mode requiere configuraci\u00f3n expl\u00edcita; usuario debe proporcionar `oracle_client_path` |
| **Cambio Importante** (Menor) | Aplicaciones asincr\u00f3nicas no pueden usar thick mode; deben usar thin mode (solo 12c+). Lanza `ConnectionError` claro al intentar. |

## 4. Enfoques Alternativos Considerados

| Alternativa | Ventajas | Desventajas | Raz\u00f3n Rechazada |
|---|---|---|---|
| **Detecci\u00f3n de versi\u00f3n ansiosa** (en tiempo de conexi\u00f3n) | Detecta versi\u00f3n temprano; falla r\u00e1pido en 11g+ sin Instant Client | Bloquea inicio de conexi\u00f3n para todas las aplicaciones; gastos generales para usuarios no-Oracle; sin beneficio para async (falla temprano en lugar de perezoso) | Inicializaci\u00f3n ansiosa derrota beneficios async; gastos generales inaceptables |
| **Selecci\u00f3n manual de dialecto** (usuario especifica) | No requiere consulta de versi\u00f3n; transparente para librer\u00eda | Carga API en usuarios; f\u00e1cil seleccionar dialecto incorrecto; requiere conciencia de versi\u00f3n de aplicaci\u00f3n | No determinista; propenso a error de usuario |
| **N\u00famero de versi\u00f3n integrado** (basado en configuraci\u00f3n) | Fuente \u00fanica de verdad | Duplica documentaci\u00f3n de Oracle; requiere actualizaci\u00f3n por versi\u00f3n; sin detecci\u00f3n autom\u00e1tica | Mantenimiento manual; no es autodocumentado |
| **Reinicializaci\u00f3n en cada consulta** (sin caching) | Simplifica c\u00f3digo; sin bandera necesaria | N consultas por conexi\u00f3n; degradaci\u00f3n de rendimiento significativa en esquemas grandes | Inaceptable para esquemas grandes (100+ tablas × 10+ consultas de metadatos cada una) |
| **Registro global de versiones** (basado en sem\u00e1foro) | Previene cualquier reinicializaci\u00f3n de thick mode | Bloqueo complejo; sin beneficio sobre bandera de inicializaci\u00f3n \u00fanica | Complejidad innecesaria |

## 5. Detalles de Implementaci\u00f3n

### 5.1 Cambios a CatalogSource (src/util_bbdd/metadata/source.py)

```python
class CatalogSource:
    def __init__(self, dialect, executor, source_id=None, cache=None, default_schema=None):
        self.dialect = dialect
        self.executor = executor
        self._version_resolved = False  # Bandera: versi\u00f3n detectada y dialecto resuelto
        self._default_schema = default_schema
        ...

    def _resolve_dialect(self) -> None:
        """Resolver variante de dialecto basada en versi\u00f3n del servidor (p.ej., Oracle 11g vs 12c+)."""
        if self._version_resolved:
            return  # Ya resuelto; omitir
        self._version_resolved = True

        # Verificar si dialecto implementa protocolo VersionedCatalogDialect
        if not hasattr(self.dialect, "server_version_sql") or not hasattr(self.dialect, "for_server_version"):
            return  # No versionado; usar tal cual

        # Consultar versi\u00f3n del servidor
        version_sql = self.dialect.server_version_sql()
        rows = self.executor.fetch_all(version_sql, {})
        if not rows or not rows[0]:
            return  # Versi\u00f3n no disponible; mantener predeterminado

        # Analizar versi\u00f3n: "11.2.0.4.0" → (11, 2, 0, 4, 0)
        version_str = str(rows[0][0]).strip()
        try:
            version_tuple = tuple(int(x) for x in version_str.split("."))
        except (ValueError, AttributeError):
            return  # Versi\u00f3n malformada; mantener predeterminado

        # Resolver variante
        resolved_dialect = self.dialect.for_server_version(version_tuple)
        self.dialect = resolved_dialect

    def current_schema(self) -> str:
        self._resolve_dialect()  # Resoluci\u00f3n perezosa en primera llamada
        ...
```

### 5.2 Cambios a OracleCatalog (src/util_bbdd/metadata/oracle/catalog.py)

```python
class OracleCatalog(CatalogDialect):
    @staticmethod
    def server_version_sql() -> str:
        """SQL para consultar versi\u00f3n de Oracle."""
        return "SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%' AND ROWNUM = 1"

    @staticmethod
    def for_server_version(version_tuple: tuple[int, ...]) -> 'OracleCatalog':
        """Devolver variante de cat\u00e1logo apropiada basada en versi\u00f3n de Oracle."""
        if version_tuple and version_tuple[0] < 12:
            return Oracle11Catalog()
        return OracleCatalog()

class Oracle11Catalog(OracleCatalog):
    """Cat\u00e1logo para Oracle 11g (omite consultas de columnas IDENTITY)."""
    _sql = _SQL_11G  # Excluye Kind.IDENTITY
```

### 5.3 Inicializaci\u00f3n de Thick Mode (src/util_bbdd/connection/oracle/_thick_mode.py)

```python
import threading

_THICK_MODE_LOCK = threading.Lock()
ORACLE_THICK_MODE_INITIALIZED = False

def init_oracle_thick_mode(client_path: str) -> None:
    """Inicializar thick mode de Oracle (seguro para hilos, llamada \u00fanica)."""
    global ORACLE_THICK_MODE_INITIALIZED
    
    with _THICK_MODE_LOCK:
        if ORACLE_THICK_MODE_INITIALIZED:
            return  # Ya inicializado
        
        oracledb.init_oracle_client(lib_dir=client_path)
        ORACLE_THICK_MODE_INITIALIZED = True
```

### 5.4 Integraci\u00f3n con ConnectionFactory

**Sincr\u00f3nico (connection_oracle.py):**
```python
if oracle_thick_mode:
    if not oracle_client_path:
        raise ValueError("oracle_client_path requerido cuando oracle_thick_mode=True")
    init_oracle_thick_mode(oracle_client_path)
```

**Asincr\u00f3nico (async_connection_oracle.py):**
```python
if ORACLE_THICK_MODE_INITIALIZED:
    raise ConnectionError("Modo asincr\u00f3nico incompatible con thick mode de Oracle; usar thin mode (solo 12c+)")
```

## 6. Estrategia de Prueba

### 6.1 Pruebas Unitarias

- **test_oracle_11_catalog_detection.py**: Detecci\u00f3n de versi\u00f3n de OracleCatalog (m\u00e9todo for_server_version)
- **test_catalog_source_oracle_version.py**: Resoluci\u00f3n perezosa de CatalogSource con executor simulado

### 6.2 Pruebas de Integraci\u00f3n

- Contenedor Oracle 11g (docker-compose.bench.yml) con validaci\u00f3n de detecci\u00f3n de versi\u00f3n
- Inicializaci\u00f3n de thick mode en m\u00faltiples hilos (creaci\u00f3n de conexi\u00f3n concurrente)
- Protecci\u00f3n asincr\u00f3nica contra thick mode (ConnectionError lanzado)

### 6.3 Validaci\u00f3n de Recuento de Consultas

- Verificar consulta de versi\u00f3n \u00fanica por conexi\u00f3n (test_query_counts.py existente extendido para Oracle)
- Sin consultas de versi\u00f3n redundantes en acceso de metadatos repetido

## 7. Estado y Revisi\u00f3n

**Estado:** ACEPTADO E IMPLEMENTADO (sesi\u00f3n 2025-01-15, fases 1-8)

**Commits Clave:**
- Fases 1-6: Implementaci\u00f3n principal (resoluci\u00f3n de versi\u00f3n, thick mode, infraestructura de prueba)
- Fase 7: Pruebas de integraci\u00f3n (22 pruebas para detecci\u00f3n de versi\u00f3n y resoluci\u00f3n perezosa)
- Fase 8: Documentaci\u00f3n (actualizaciones de drivers.md, ADR-004, runtime.md, CHANGELOG.md)

**Resultados de Prueba:**
- 5108 pruebas pasando (5086 l\u00ednea base + 22 nuevas pruebas de Oracle 11g)
- 496 pruebas saltadas
- 0 fallos

**Fecha de \u00daltima Revisi\u00f3n:** 2025-01-15

---

## Referencias

- **Implementaci\u00f3n de CatalogSource**: [src/util_bbdd/metadata/source.py](../../src/util_bbdd/metadata/source.py)
- **Variantes de OracleCatalog**: [src/util_bbdd/metadata/oracle/catalog.py](../../src/util_bbdd/metadata/oracle/catalog.py)
- **Thick Mode**: [src/util_bbdd/connection/oracle/_thick_mode.py](../../src/util_bbdd/connection/oracle/_thick_mode.py)
- **Gu\u00eda de Drivers**: [docs/guides/drivers.md](../guides/drivers.md)
- **Suite de Pruebas**: [tests/unit/metadata/test_oracle_11_catalog_detection.py](../../tests/unit/metadata/test_oracle_11_catalog_detection.py), [tests/unit/metadata/test_catalog_source_oracle_version.py](../../tests/unit/metadata/test_catalog_source_oracle_version.py)
