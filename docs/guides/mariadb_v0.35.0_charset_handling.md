# MariaDB v0.35.0: Manejo de Charset — `init_command` y `encoding_errors`

!!! warning "Corrección (v0.35.7)"
    Esta guía describe el diseño de v0.35.0. Comprobado contra el driver real: MariaDB Connector/Python 1.1.14 (la
    última versión) **no admite `encoding_errors` ni `charset`**, así que con ese driver `encoding_errors` nunca
    llegó a aplicarse; desde v0.35.7 es un parámetro sin efecto. Lo vigente está en
    la [Guía de conexión § 6](connection_guide.md#6-parametros-especiales-de-mariadb-init_command-y-encoding_errors).

## 1. Objetivo

Explicar los dos nuevos parámetros introducidos en v0.35.0 (`init_command` y `encoding_errors`) y cómo
resuelven problemas de encoding en entornos MariaDB con charset heredado (`latin1`).

## 2. El Problema: Por qué SQLAlchemy no fallaba pero la librería nativa sí

Cuando `util_bbdd` conecta a un servidor MariaDB configurado en `latin1` pero con bases de datos en
`utf8mb4`, ocurren fallos en lectura de metadatos:

```python
# v0.34.0 — error en info_schema
UnicodeDecodeError: 'latin1' codec can't decode byte 0xc3...
```

**¿Por qué SQLAlchemy funcionaba?** Porque SQLAlchemy usa PyMySQL como driver, y PyMySQL
**automáticamente** envía `SET NAMES utf8mb4` en cada conexión. Este comando crucial fija el charset
de **bidirección** entre cliente y servidor.

**¿Por qué nuestro driver nativo fallaba?** Porque `mariadb.connect(charset='utf8mb4')` solo fija
el handshake del cliente; **no fuerza el servidor a convertir datos antes de enviarlos**. Sin
`character_set_results=utf8mb4`, el servidor devuelve bytes en `latin1` aunque el cliente espere `utf8mb4`.

## 3. Solución v0.35.0: `init_command` + `encoding_errors`

### 3.1 — `init_command`: Replicar el comportamiento de PyMySQL

**Campo nuevo en `MariaDBConnectionConfig`:**

```python
class MariaDBConnectionConfig:
    init_command: str = "SET NAMES utf8mb4"
    # ^^^^^^^^^^^^^^^
    # ↓ Ejecutado en CADA conexión (sync y pool) en connectionOpen
```

**¿Qué hace?**

```sql
SET NAMES utf8mb4;
-- ↓ Equivalente a estos 3 comandos:
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;  ← ¡Lo importante!
```

**Impacto visible:**

| Antes (v0.34.0) | Después (v0.35.0) |
|---|---|
| `UnicodeDecodeError` al leer `information_schema` | Lectura limpia de metadatos |
| Servidor devuelve bytes en `latin1` | Servidor convierte a `utf8mb4` antes de enviar |
| PyMySQL + SQLAlchemy: OK; nativo: FAIL | Todas las combinaciones: OK |

### 3.2 — `encoding_errors`: Safety net para datos corruptos

**Campo existente, ahora activo desde v0.35.0:**

```python
class MariaDBConnectionConfig:
    encoding_errors: str = "replace"
    # ^^^^^^^^^^^^^^^
    # Activo en mariadb-connector-python >= 1.1.4
```

**¿Qué hace?**

Si hay bytes en `information_schema` que genuinamente no pueden decodificarse como UTF-8 (datos heredados
irrecuperables), este parámetro define el comportamiento:

- **`"replace"` (default)**: Bytes inválidos → `?`. Lectura parcial legible.
- **`"strict"** (antiguo): Bytes inválidos → `UnicodeDecodeError`. Lectura bloqueada.
- **`"ignore"`**: Bytes inválidos → descartados silenciosamente. Lectura incompleta.

**Cuándo ayuda:**

```python
# Servidor: charset=latin1, BD: charset=utf8mb4, algunos comentarios con datos corruptos
with SyncDatabaseManager("mariadb", conn_params) as db:
    # v0.34.0: UnicodeDecodeError → crash
    # v0.35.0 con encoding_errors='replace': lectura parcial con ? en lugar de crash
    docs = db.get_database_documentation()
```

## 4. Configuración

### Configuración por defecto (recomendada)

```python
from util_bbdd import SyncDatabaseManager

conn_params = {
    "host": "localhost",
    "port": 3306,
    "user": "app",
    "password": "secret",
    "database": "mydb",
    # Opcional en v0.35.0+: estos son los valores por defecto
    # "charset": "utf8mb4",
    # "init_command": "SET NAMES utf8mb4",
    # "encoding_errors": "replace",
}

with SyncDatabaseManager(db_type="mariadb", conn_params=conn_params) as db:
    docs = db.get_database_documentation()  # ✅ Funciona, sin errores
```

### Personalización

```python
conn_params = {
    "host": "localhost",
    "user": "app",
    "password": "secret",
    "database": "mydb",
    
    # Charset de conexión (replicado por init_command)
    "charset": "utf8mb4",  # Recomendado
    
    # SQL ejecutado en cada conexión (replicar PyMySQL)
    "init_command": "SET NAMES utf8mb4",
    
    # Manejo de bytes no-decodificables
    "encoding_errors": "replace",  # "strict" (antiguo) o "ignore"
}
```

## 5. Compatibilidad con versiones de driver

| Driver | `init_command` | `encoding_errors` | Comportamiento |
|---|---|---|---|
| mariadb >= 1.1.4 | ✅ Soportado | ✅ Soportado | Ambos activos; seguridad completa |
| mariadb 1.1.0–1.1.3 | ✅ Soportado | ❌ Rechazado | `init_command` activo; `encoding_errors` ignorado (fallback automático) |
| mariadb < 1.1.0 | ❌ Rechazado | ❌ Rechazado | Ambos ignorados; retry del pool los descarta |

**Nota:** La librería ejecuta retry automático si el driver rechaza estos parámetros. Ver
[`pool_connection_mariadb.py` §3.1](../../src/util_bbdd/connection/mariadb/pool_connection_mariadb.py#L23)
para detalles del mecanismo.

## 6. Diagnóstico de problemas

### Síntoma: `UnicodeDecodeError` en v0.35.0

```python
UnicodeDecodeError: 'utf8' codec can't decode byte 0xc3 in position 42
```

**Causas potenciales (en orden de probabilidad):**

1. **Driver mariadb < 1.1.4**: No soporta `encoding_errors`. Actualizar:
   ```bash
   pip install --upgrade "mariadb>=1.1.4"
   ```

2. **`init_command` ignorado silenciosamente**: Servidor no ejecuta comandos custom. Verificar:
   ```sql
   -- Conectar manualmente y ejecutar:
   SET NAMES utf8mb4;
   SELECT @@character_set_results;  -- Debe ser utf8mb4
   ```

3. **Servidor verdaderamente `latin1` con datos irrecuperables**: Usar `encoding_errors="ignore"` como último recurso:
   ```python
   conn_params = {
       ...
       "encoding_errors": "ignore",  # Bytes invalidos → descartados
   }
   ```

### Verificación: Consultar charset activo en conexión

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager("mariadb", conn_params) as db:
    # Ejecutar query diagnostica
    result = db.execute_custom_one(
        "SELECT @@character_set_client, @@character_set_connection, @@character_set_results"
    )
    print("character_set_client:", result[0])
    print("character_set_connection:", result[1])
    print("character_set_results:", result[2])
    # Esperado: ('utf8mb4', 'utf8mb4', 'utf8mb4')
```

## 7. Migración desde v0.34.x

### v0.34.0–0.34.1 → v0.35.0

**Cambio automático:**
- `init_command` se configura automáticamente al valor por defecto
- `encoding_errors` se activa automáticamente (si driver >= 1.1.4)
- **Sin cambios en tu código necesarios**; la librería maneja los parámetros internamente

**Opcional: Verificar y confirmar:**

```python
# Verificar que tu código simplemente funciona
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager("mariadb", conn_params) as db:
    docs = db.get_database_documentation()
    print("✅ Migrations successful, no UnicodeDecodeError")
```

### Rollback a v0.34.x (si necesario)

```bash
pip install "util-bbdd==0.34.1"
```

Los parámetros `init_command` y `encoding_errors` en `conn_params` serán ignorados en versiones < 0.35.0.

## 8. Roadmap y futuras mejoras

- **v0.36.0+**: Potencial optimización de `encoding_errors` con detección automática del estado
  de charset (usando `CharsetStateDetector` de v0.33.0+).
- **Monitoreo**: Logging de advertencia si `@@character_set_results != utf8mb4` al abrir conexión.

---

**Referencia rápida:** Ver [Guía de Conexión § 6](connection_guide.md#6-parametros-especiales-de-mariadb-init_command-y-encoding_errors)
para tabla de parámetros y ejemplos; [Troubleshooting](troubleshooting.md) para error handling.
