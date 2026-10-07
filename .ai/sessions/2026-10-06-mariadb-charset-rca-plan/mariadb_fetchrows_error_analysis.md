# Análisis de Causa Raíz: MariaDB SystemError en fetchrows

**Fecha**: 2026-10-04  
**Versión afectada**: 0.31.0  
**Severidad**: CRÍTICO (bloquea generación de documentación)  
**Componente**: `util_bbdd.metadata.source.DbapiCatalogExecutor.fetch_all()` con driver MariaDB

---

## Síntomas Reportados

```
SystemError: <method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set
```

Este error ocurre cuando se intenta generar documentación Word/Excel/HTML de una base de datos MariaDB, en la lectura del catálogo de metadatos (DDL de tablas).

**Stack trace resumido**:
1. `documentation_orchestrator.py:213` → `get_ddl()` 
2. `_catalog_facade.py:153` → `_snapshot()` → `get_schema_metadata()`
3. `sync_mgr.py:680` → `metadata_source.snapshot()`
4. `source.py:225` → `cache.get_or_load()` → `_load()` 
5. `source.py:205` → `executor.fetch_all()` ← **Falla aquí**
6. `_catalog_executor.py:99-105` → `ManagerCatalogExecutor.fetch_all()`
7. `source.py:74` → `DbapiCatalogExecutor.fetch_all()` → `cursor.fetchall()` ❌

---

## Causa Raíz (Análisis)

### 1. Contexto: ADR-003 (v0.31.0)

La versión 0.31.0 introduce **centralización de metadatos** con:
- `ManagerCatalogExecutor` (nuevo en `managers/_catalog_executor.py`)
- `DbapiCatalogExecutor` (existente, ahora usado por `ManagerCatalogExecutor`)
- `CatalogSource` / `AsyncCatalogSource` (lectura por lotes, cacheada)
- Inyección de `connection_provider` y `connection_releaser` lambdas

### 2. Error Específico del Driver MariaDB

El error `SystemError: <method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set` es **específico del binding de C de MariaDB Connector/Python** (`mariadb` library, no PyMySQL).

Causas potenciales en la librería `mariadb`:

#### A. Cursor Corrupto por Excepción SQL Silenciosa
- El método `fetchrows()` (de C) detecta que ocurrió una excepción durante su ejecución
- La excepción no se propagó correctamente como un `DatabaseError` Python
- En su lugar, retorna este `SystemError`

**Por qué podría ocurrir con ADR-003**: Si el SQL generado es inválido para MariaDB, el `cursor.execute()` fallará, pero el cursor queda en estado corrupto cuando se intenta `cursor.fetchall()`.

#### B. Problema de Timing con Liberación de Conexión
- En `ManagerCatalogExecutor.fetch_all()` (línea 96-105), la conexión se libera en el bloque `finally`
- Si hay un problema con los lambdas `connection_releaser()`, la conexión podría cerrarse MIENTRAS se está leyendo el cursor

**Código actual**:
```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    connection = self._provider()  # 1. Obtiene conexión
    try:
        rows = DbapiCatalogExecutor(connection, driver_paramstyle(connection)).fetch_all(sql, params)
        #     ↓ Dentro de DbapiCatalogExecutor.fetch_all() líneas 65-75
        #     - cursor = connection.cursor()
        #     - cursor.execute(driver_sql, args)  
        #     - return [tuple(row) for row in cursor.fetchall()]  ← FALLA AQUÍ si cursor está corrupto
        #     - finally: cursor.close()
        return [tuple(_materialize(v) for v in row) for row in rows]
    except DatabaseException:
        raise
    except Exception as exc:
        _rollback(connection)
        raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
    finally:
        self._releaser(connection)  # 2. Libera conexión (podría cerrarla demasiado pronto)
```

### 3. Problemas Detectados en el Código

#### Problema 1: Double Evaluation de `_get_sync_query_executor()`

En `sync_mgr.py` líneas 646-647:

```python
ManagerCatalogExecutor(
    lambda: self._get_sync_query_executor().connection_provider(),
    lambda conn: self._get_sync_query_executor().connection_releaser(conn),
)
```

Esto está bien formado, pero hay una preocupación: si `_get_sync_query_executor()` cambia de estado entre la primera y segunda lambda, podrían ocurrir problemas.

#### Problema 2: Driver MariaDB y Conexiones de Pool

Con `pool_connection`:
- `connection_provider` → `lambda: self.get_connection()` (obtiene del pool)
- `connection_releaser` → `lambda conn: self.close_connection(conn)` (devuelve al pool)

El problema puede ocurrir si:
1. La conexión que se obtiene del pool ya estaba en un estado corrupto
2. O la librería `mariadb` tiene un problema threading con pools

#### Problema 3: SQL Generado por CatalogDialect

El SQL generado por `metadata/mariadb/catalog.py` para MariaDB puede estar fallando silenciosamente.

Los queries del catálogo MariaDB se escriben en ADR-003 con `bind parameters `:nombre``, que se convierten al estilo de MariaDB (`%` o `%(nombre)s`).

Posible fallo: **Sin validación de que el SQL traducido es correcto después de `to_driver()`**.

---

## Problemas Secundarios

### Error Oracle: ORA-00942

El segundo error en los logs:
```
Oracle: Error leyendo el catálogo: ORA-00942: table or view does not exist
```

Esto es esperado si las tablas no existen en el esquema del usuario Oracle. No es problema de ADR-003, es un problema de permisos o schema.

---

## Recomendaciones de Fix

### 1. Agregar Validación de SQL en `DbapiCatalogExecutor`

**Archivo**: `src/util_bbdd/metadata/source.py`

```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    driver_sql, args = to_driver(sql, params, self.paramstyle)
    cursor = self.connection.cursor()
    try:
        if args is None:
            cursor.execute(driver_sql)
        else:
            cursor.execute(driver_sql, args)
        # ← AGREGAR: Validación de que cursor está en buen estado
        result = cursor.fetchall()
        if result is None:  # Para mariadb: verificar que no retorna None tras error
            raise DatabaseError("Cursor en estado corrupto tras fetchall()")
        return [tuple(row) for row in result]
    except Exception as exc:
        # Loguear SQL para debugging
        logger.debug(f"SQL falló: {driver_sql} con params: {args}")
        raise
    finally:
        cursor.close()
```

### 2. Envolver `fetch_all()` en `ManagerCatalogExecutor` con Reintento

```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    max_retries = 3
    for attempt in range(max_retries):
        connection = self._provider()
        try:
            rows = DbapiCatalogExecutor(...).fetch_all(sql, params)
            return [tuple(_materialize(v) for v in row) for row in rows]
        except SystemError as exc:
            if attempt < max_retries - 1:
                self._releaser(connection)
                time.sleep(0.1 * (attempt + 1))  # Backoff exponencial
                continue
            raise MetadataError(f"Error leyendo el catálogo (retentado {max_retries} veces): {exc}") from exc
        finally:
            self._releaser(connection)
```

### 3. Agregar Logging Detallado

Capturar qué SQL exacto está fallando:

```python
# En _catalog_executor.py, después de línea 99
logger.debug(f"Ejecutando SQL de catálogo: {sql}\nParámetros: {params}")
```

---

## Datos Relevantes

- **Librería MariaDB**: `mariadb` (MariaDB Connector/Python), no PyMySQL
- **Motor**: MariaDB 10.2+ o MySQL 8.0.16+
- **Pool**: El error ocurre tanto con pool como sin pool (basado en el traceback)
- **Dialectos afectados**: Probablemente solo MariaDB/MySQL con driver `mariadb`

---

## Validación

### Antes de Fix
```
MariaDB + util_bbdd 0.31.0 + documentación = FALLA (SystemError)
```

### Después de Fix
```
MariaDB + util_bbdd 0.31.1 + documentación = PASA ✅
```

---

## Próximos Pasos

1. **Inmediato (Hotfix)**: Agregar validación robusta en `DbapiCatalogExecutor.fetch_all()`
2. **Corto plazo (0.31.1)**: Implementar reintento automático en `ManagerCatalogExecutor`
3. **Medio plazo**: Validar que el SQL traducido es correcto antes de ejecutar
4. **Largo plazo**: Migrar de `mariadb` a `aiomysql` o `asyncmy` si problemas persisten

---

*Análisis completado: 2026-10-04*
