# Checklist de Investigación RCA MariaDB Charset
**Versión**: 1.0 | **Fecha**: 2026-10-06 | **Referencia**: MARIADB_CHARSET_RCA_PLAN_v1.md (Sección 7)

---

## A. Verificaciones Técnicas (Driver + Server)

### A1. Versión mariadb driver
- [ ] Ejecutar: `pip show mariadb` → anotar versión exacta
- [ ] Descargar release notes de GitHub: https://github.com/mariadb-corporation/mariadb-connector-python/releases
- [ ] Buscar en release notes: palabras clave = "encoding", "charset", "UnicodeDecodeError", "SystemError"
- [ ] Anotar fixes conocidos en versiones > 1.1
- **Decisión**: ¿Upgrade a versión más reciente? (1.2, 1.3)

### A2. Versión de servidor MariaDB destino
**Ejecutar en BD destino**:
```sql
SELECT VERSION();
SELECT @@character_set_server, @@character_set_client, @@character_set_connection, @@character_set_database;
SELECT @@collation_server, @@collation_connection;
```
- [ ] Anotar versiones servidor (10.5, 10.6, 11.x, etc.)
- [ ] Anotar charset y collation de cada nivel
- [ ] ¿Hay mismatch entre levels? (p.ej. server=latin1, connection=utf8mb4)
- **Decisión**: ¿Es problema de servidor?

### A3. Información_schema charset
**Ejecutar en BD destino**:
```sql
SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME 
FROM information_schema.SCHEMATA 
WHERE SCHEMA_NAME = 'information_schema';

-- Ver qué es la tabla problemática
SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_COLLATION 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'information_schema' 
LIMIT 5;
```
- [ ] ¿information_schema tiene charset diferente al usuario?
- [ ] ¿Está en utf8mb3 o utf8mb4?
- **Decisión**: ¿Necesita limpieza?

### A4. Datos corruptos en information_schema
**Ejecutar en BD destino** (detectar bytes inválidos):
```sql
-- Buscar comentarios con problemas
SELECT TABLE_NAME, HEX(TABLE_COMMENT), TABLE_COMMENT 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'SCHEMA_DESTINO'
AND LENGTH(HEX(TABLE_COMMENT)) > LENGTH(TABLE_COMMENT) * 2;

-- Buscar comentarios de columnas con problemas
SELECT TABLE_NAME, COLUMN_NAME, HEX(COLUMN_COMMENT), COLUMN_COMMENT 
FROM information_schema.COLUMNS 
WHERE TABLE_SCHEMA = 'SCHEMA_DESTINO'
AND LENGTH(HEX(COLUMN_COMMENT)) > LENGTH(COLUMN_COMMENT) * 2;
```
- [ ] ¿Existen bytes inválidos?
- [ ] ¿Cuántas tablas/columnas afectadas?
- **Decisión**: ¿Es problema de datos?

---

## B. Reproducción del Error

### B1. Crear BD de prueba con charset deficiente
```bash
# En MariaDB/MySQL
CREATE DATABASE util_bbdd_test_utf8mb3 CHARACTER SET 'utf8mb3';
USE util_bbdd_test_utf8mb3;

-- Crear tabla con comentario
CREATE TABLE test_table (
    id INT PRIMARY KEY,
    name VARCHAR(100) COMMENT 'Nombre con acentuación: café, naïve, 中文'
) COMMENT 'Tabla de prueba con caracteres UTF-8';

-- Verificar
SELECT TABLE_COMMENT FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'util_bbdd_test_utf8mb3' AND TABLE_NAME = 'test_table';
```

### B2. Intentar leer con mariadb driver (reproducir error)
```python
import mariadb

conn = mariadb.connect(
    host='localhost',
    user='root',
    password='password',
    database='util_bbdd_test_utf8mb3',
    charset='utf8mb4'  # Intentar forzar UTF-8
)

cursor = conn.cursor()
try:
    cursor.execute("""
        SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'util_bbdd_test_utf8mb3'
    """)
    rows = cursor.fetchall()
    print("✅ SUCCESS:", rows)
except SystemError as e:
    print("❌ ERROR (esperado):", e)
finally:
    cursor.close()
    conn.close()
```

- [ ] ¿Se reproduce el SystemError?
- [ ] ¿Mensaje es idéntico al reportado?
- **Decisión**: ¿Confirma hipótesis B1 o C1?

### B3. Probar alternativas una por una
**Alternativa A: PyMySQL fallback**
```python
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='password',
    database='util_bbdd_test_utf8mb3',
    charset='utf8mb4'
)

cursor = conn.cursor()
try:
    cursor.execute("""
        SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'util_bbdd_test_utf8mb3'
    """)
    rows = cursor.fetchall()
    print("✅ PyMySQL SUCCESS:", rows)
except Exception as e:
    print("❌ PyMySQL ERROR:", e)
finally:
    cursor.close()
    conn.close()
```
- [ ] ¿PyMySQL funciona donde mariadb falla?
- **Decisión**: ¿Opción A es viable?

**Alternativa B: SET NAMES + Validación**
```python
import mariadb

conn = mariadb.connect(
    host='localhost',
    user='root',
    password='password',
    database='util_bbdd_test_utf8mb3'
    # Sin charset especificado, permitir default
)

cursor = conn.cursor()
try:
    # Validar charset
    cursor.execute("SELECT @@character_set_server, @@character_set_client, @@character_set_connection")
    server_cs, client_cs, conn_cs = cursor.fetchone()
    print(f"Charset: server={server_cs}, client={client_cs}, connection={conn_cs}")
    
    # Garantizar UTF-8
    cursor.execute("SET NAMES 'utf8mb4'")
    
    # Intentar query nuevamente
    cursor.execute("""
        SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'util_bbdd_test_utf8mb3'
    """)
    rows = cursor.fetchall()
    print("✅ SET NAMES + mariadb SUCCESS:", rows)
except SystemError as e:
    print("❌ SET NAMES + mariadb ERROR:", e)
finally:
    cursor.close()
    conn.close()
```
- [ ] ¿SET NAMES evita el error?
- **Decisión**: ¿Opción B es suficiente?

**Alternativa C: CONVERT/CAST**
```python
import mariadb

conn = mariadb.connect(
    host='localhost',
    user='root',
    password='password',
    database='util_bbdd_test_utf8mb3',
    charset='utf8mb4'
)

cursor = conn.cursor()
try:
    cursor.execute("""
        SELECT TABLE_NAME, 
               CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4) AS TABLE_COMMENT 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'util_bbdd_test_utf8mb3'
    """)
    rows = cursor.fetchall()
    print("✅ CONVERT + mariadb SUCCESS:", rows)
except SystemError as e:
    print("❌ CONVERT + mariadb ERROR:", e)
finally:
    cursor.close()
    conn.close()
```
- [ ] ¿CONVERT limpia caracteres sin SystemError?
- **Decisión**: ¿Opción C complementa B?

---

## C. Benchmark: Performance (PyMySQL vs mariadb)

### C1. Setup de prueba
```python
import time
import mariadb
import pymysql

# BD con 1000+ tablas (o usar util_bbdd_test_utf8mb3)
test_db = 'util_bbdd_test_big'

def benchmark_driver(driver_name, conn_factory, iterations=10):
    times = []
    for i in range(iterations):
        conn = conn_factory()
        cursor = conn.cursor()
        
        start = time.perf_counter()
        cursor.execute("""
            SELECT COUNT(*), TABLE_SCHEMA 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema')
            GROUP BY TABLE_SCHEMA
        """)
        rows = cursor.fetchall()
        end = time.perf_counter()
        
        times.append(end - start)
        cursor.close()
        conn.close()
    
    avg = sum(times) / len(times)
    min_t = min(times)
    max_t = max(times)
    print(f"{driver_name:20} avg={avg*1000:6.2f}ms min={min_t*1000:6.2f}ms max={max_t*1000:6.2f}ms")
    return avg
```

### C2. Ejecutar benchmark
```python
# mariadb driver
mariadb_avg = benchmark_driver(
    "mariadb",
    lambda: mariadb.connect(host='localhost', user='root', password='password', database=test_db),
    iterations=10
)

# PyMySQL
pymysql_avg = benchmark_driver(
    "pymysql",
    lambda: pymysql.connect(host='localhost', user='root', password='password', database=test_db),
    iterations=10
)

# Cálculo de overhead
overhead = ((pymysql_avg / mariadb_avg) - 1) * 100
print(f"\nOverhead PyMySQL: {overhead:.1f}%")
```

- [ ] ¿Cuál es el overhead de PyMySQL?
- [ ] ¿Es aceptable para el proyecto (< 30%)?
- **Decisión**: ¿Opción A es viable?

---

## D. Testing de Alternativas Integradas

### D1. Crear test en util_bbdd
**Ubicación**: `tests/integration/test_mariadb_charset_fix.py`

```python
import pytest
from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.managers import SyncDatabaseManager

@pytest.fixture
def mariadb_conn():
    """Conexión a MariaDB de prueba (util_bbdd_test_utf8mb3)."""
    return ConnectionFactory().create_sync('mariadb', {
        'host': 'localhost',
        'user': 'root',
        'password': 'password',
        'database': 'util_bbdd_test_utf8mb3'
    })

def test_charset_server_validation(mariadb_conn):
    """Test: Validar charset de servidor."""
    cursor = mariadb_conn.cursor()
    cursor.execute("SELECT @@character_set_server")
    server_cs = cursor.fetchone()[0]
    assert server_cs.lower() in ("utf8", "utf8mb4"), f"Charset server: {server_cs}"
    cursor.close()

def test_fetch_information_schema_no_fallback(mariadb_conn):
    """Test: Leer information_schema SIN fallback."""
    manager = SyncDatabaseManager(mariadb_conn)
    # Esta llamada no debe usar fallback
    metadata = manager.get_schema_metadata()
    assert metadata is not None
    # Verificar que no hay fallback en logs
    # (si implementamos logging de fallback)

def test_convert_cast_metadata_cleanup():
    """Test: CONVERT/CAST limpia datos corruptos."""
    # Pseudotest: si CONVERT se aplica, debe retornar strings válidos
    pass
```

- [ ] Crear y ejecutar tests
- [ ] Verificar coverage de casos edge

---

## E. Documentación de Resultados

### E1. Resumen de Hallazgos
Completar este template tras investigación:

```markdown
## RCA Completo - Hallazgos

### Hipótesis Confirmada
- [ ] A1: mariadb driver 1.1 bug → Upgrade a 1.2+
- [ ] B1: charset_server deficiente → Validar/corregir servidor
- [ ] C1: datos corruptos → Aplicar CONVERT/CAST

### Performance
- PyMySQL overhead: ___%
- CONVERT/CAST overhead: ___%

### Recomendación Final
- Driver principal: [ ] mariadb [ ] pymysql
- Validación charset: [ ] Sí [ ] No
- CONVERT/CAST: [ ] Todos los campos [ ] Selectivo [ ] No
- Error explícito: [ ] Sí [ ] No

### Próximos Pasos
1. [ ] IMPLEMENT alternativa elegida
2. [ ] Update docs (troubleshooting guide)
3. [ ] Release v0.32.3 o v0.33.0
```

---

## F. Notas de Ejecución

**Ejecutado por**: __________ | **Fecha**: __________ | **Resultado**: __________

### Cambios/Aprendizajes
- [ ] Hipótesis confirmada/rechazada: __________
- [ ] Benchmark resultado: __________
- [ ] Bloqueadores encontrados: __________

### Próxima Sesión
- [ ] Iniciar IMPLEMENT con alternativa elegida
- [ ] Consultar: __________ (referencia a sección si hay pendientes)

---

**Uso**: Imprimir este checklist y marcar conforme se ejecuten los tests. Guardar como evidencia en `.ai/` para futuras referencias.
