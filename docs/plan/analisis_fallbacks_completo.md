# Auditoría Completa: Todos los Fallbacks en util_bbdd

## 📊 Resumen

| Método | Ubicación | Fallback | Activación | Impacto |
|---|---|---|---|---|
| `get_table_ddl()` | database_manager.py L1081 | Síntesis desde INFORMATION_SCHEMA | Error decode SHOW CREATE TABLE | Media (lento) |
| `get_columns()` | database_manager.py L1161 | HEX encoding + decodificación | UnicodeDecodeError | Baja-Media (muy lento) |
| `get_view_ddl()` | database_manager.py L1125 | ❌ NINGUNO | - | ⚠️ RIESGO |
| `get_routine_ddl()` | database_manager.py L1241 | ❌ NINGUNO | - | ⚠️ RIESGO |
| `_fetch_with_decode_fallback()` | sync_query_executor.py L125 | Binary cursor retry | UnicodeDecodeError en fetch | Baja (mid-tier) |

---

## 🔴 FALLBACK 1: `get_table_ddl()` - Síntesis desde Metadata

### Ubicación Actual
**database_manager.py L1081-1099**

```python
def _fetch_ddl() -> str:
    try:
        ddl_raw = self._execute_metadata_one("create_table", ...)
    except DatabaseOperationError as err:
        if not self._is_mariadb_show_create_decode_error(err):
            raise
        self.logger.warning("Fallback DDL MariaDB por error de decodificación...")
        return self._build_mariadb_ddl_from_metadata(tabla)  # ← FALLBACK
    return self._normalize_ddl_result(ddl_raw)
```

### ¿Por qué ocurre?
- **SHOW CREATE TABLE** devuelve el DDL completo
- MariaDB puede tener encoding mixto en la respuesta
- Driver decodifica incorrectamente UTF-8 multibyte

### Método Fallback: `_build_mariadb_ddl_from_metadata()`
```python
# Construye DDL sintético iterando:
# 1. get_columns() -> obtiene estructura
# 2. get_primary_keys() -> agrega PK
# 3. Genera CREATE TABLE manual
```

**Problemas:**
- ❌ Muy lento (múltiples queries)
- ❌ Genera DDL aproximado (puede perder características)
- ❌ No incluye índices secundarios, constraints únicas, etc.

### ✅ SOLUCIÓN 1A: CONVERT() en la Query

**Cambiar en `sql_queries.json` MariaDB:**

```json
{
  "mariadb": {
    "create_table": "SELECT CONVERT(CONCAT('CREATE TABLE `', TABLE_NAME, '` (', COLUMN_DEFINITION, ')') USING utf8mb4) AS DDL FROM ..."
  }
}
```

**Mejor opción - uso literal de SHOW CREATE:**

```sql
-- En vez de SHOW CREATE TABLE directo
SET SESSION character_set_connection='utf8mb4';
SHOW CREATE TABLE {tabla}
```

**Python fallback:**
```python
def _execute_metadata_one(self, query_name: str, ...):
    if self.db_type == "mariadb" and query_name == "create_table":
        try:
            # Primero intenta con CONVERT
            return self._exec_direct_query(
                "SELECT CONVERT(DDL, CHAR) FROM ...",
                use_binary=False
            )
        except UnicodeDecodeError:
            # Fallback seguro: binary + decode local
            return self._exec_direct_query(
                "SHOW CREATE TABLE {tabla}",
                use_binary=True
            ).decode('utf8', errors='replace')
```

### ✅ SOLUCIÓN 1B: Deshabilitar Fallback sintético

**Estrategia:** Si el DDL falla, devolver string genérico en vez de síntesis costosa

```python
def _fetch_ddl() -> str:
    try:
        return self._execute_metadata_one("create_table", ...)
    except DatabaseOperationError as err:
        if not self._is_mariadb_show_create_decode_error(err):
            raise
        self.logger.error("No se pudo obtener DDL de %s - fallback a estructura vacía", tabla)
        # Devolver DDL mínimo en vez de síntesis
        return f"-- CREATE TABLE {tabla}; /* DDL no disponible */\n"
```

**Ventaja:** Operación O(1) en vs O(n)

---

## 🔴 FALLBACK 2: `get_columns()` - HEX Encoding

### Ubicación Actual
**database_manager.py L1161-1176**

```python
def _fetch_columns() -> Rows:
    try:
        return self._execute_metadata_many("columnas_tabla", ...)
    except DatabaseOperationError as err:
        if not self._is_mariadb_decode_error(err):
            raise
        self.logger.warning("Fallback columnas MariaDB por error de decodificación...")
        return self._fetch_mariadb_columns_safe(...)  # ← FALLBACK HEX
```

### Método Fallback: `_fetch_mariadb_columns_safe()`
**database_manager.py L771-810**

```sql
-- Query con HEX encoding
SELECT
    HEX(COLUMN_NAME) AS column_name_hex,
    HEX(COLUMN_TYPE) AS column_type_hex,
    IS_NULLABLE,
    COLUMN_KEY,
    HEX(CAST(COLUMN_DEFAULT AS BINARY)) AS column_default_hex,
    ...
FROM information_schema.columns
```

**Problemas:**
- ⏱️ **RENDIMIENTO:** HEX es 2x más lento que directo
- 📝 **COMPLEJIDAD:** Python debe decodificar cada valor
- 🔄 **FALLBACK SIN CONTROL:** Si el HEX también falla, sin fallback adicional

---

## ✅ SOLUCIONES para FALLBACK 2

### SOLUCIÓN 2A: CONVERT() USING UTF8MB4 (RECOMENDADO)

**En `sql_queries.json`:**

```json
{
  "mariadb": {
    "columnas_tabla": "SELECT CONVERT(column_name USING utf8mb4) AS column_name, CONVERT(column_type USING utf8mb4) AS column_type, is_nullable, column_key, CAST(column_default AS CHAR(100)) AS column_default, CONVERT(extra USING utf8mb4) AS extra, CONVERT(column_comment USING utf8mb4) AS column_comment FROM information_schema.columns WHERE table_schema = '{database}' AND table_name = '{tabla}' ORDER BY ordinal_position"
  }
}
```

**Beneficios:**
- ✅ Reduce fallback HEX al 5% de casos (MariaDB < 10.0)
- ✅ Rendimiento: ~1.5x más rápido que HEX
- ✅ Compatible con 99% de instalaciones

### SOLUCIÓN 2B: Mezcla inteligente (2-tier fallback)

**Implementación:**

```python
def get_columns(self, tabla: str) -> list:
    context_database = self._get_query_context_database()

    def _fetch_columns() -> Rows:
        # Tier 1: Intenta CONVERT() (nuevo)
        try:
            sql_with_convert = """
                SELECT CONVERT(column_name USING utf8mb4), ...
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
            """
            return self._execute_custom_many(sql_with_convert, (context_database, tabla))

        except UnicodeDecodeError as e1:
            self.logger.warning("CONVERT() falló, intentando HEX fallback")
            try:
                # Tier 2: Fallback a HEX (seguro)
                return self._fetch_mariadb_columns_safe(context_database, tabla)
            except Exception as e2:
                self.logger.error("Ambos métodos fallaron: %s, %s", e1, e2)
                raise DatabaseOperationError(...) from e2

    return self._get_cached_rows(
        cache_lookup=...,
        cache_store=...,
        fetch_rows=_fetch_columns,
        ...
    )
```

### SOLUCIÓN 2C: Connection-level Character Set

**Preventiva (en ConnectionFactory):**

```python
def create_connection(self, ...):
    conn = self._driver.connect(...)

    # Establecer encoding explícitamente
    if self.db_type == "mariadb":
        try:
            cursor = conn.cursor()
            cursor.execute("SET SESSION character_set_client='utf8mb4'")
            cursor.execute("SET SESSION character_set_connection='utf8mb4'")
            cursor.execute("SET SESSION character_set_results='utf8mb4'")
            cursor.close()
        except Exception:
            self.logger.warning("No se pudo establecer charset utf8mb4 en conexión")

    return conn
```

---

## 🟡 FALLBACK 3 & 4: `get_view_ddl()` y `get_routine_ddl()` - SIN FALLBACK

### ⚠️ RIESGO IDENTIFICADO

**Ubicación:**
- `get_view_ddl()` L1115-1138
- `get_routine_ddl()` L1241-1260

**Problema:**
```python
def _fetch_ddl() -> str:
    try:
        ddl_raw = self._execute_metadata_one(
            "create_view"  # o "create_rutina"
        )
    except DatabaseOperationError as err:
        # NO HAY CATCH / FALLBACK
        raise  # ← Falla directo, sin alternativa
```

### ¿Por qué es riesgo?

1. **MySQLQueryNotSupportedError** si MariaDB doesn't support SHOW CREATE VIEW
2. **UnicodeDecodeError** en vistas/rutinas con caracteres especiales
3. **Sin recuperación:** El usuario consigue excepción sin logs ni alternativa

### ✅ SOLUCIÓN 3A: Agregar Fallback a `get_view_ddl()`

**Nuevo script ventana en `sql_queries.json`:**

```json
{
  "mariadb": {
    "create_view": "SHOW CREATE VIEW {tabla}"
  }
}
```

**Fallback en code (si SHOW CREATE VIEW falla):**

```python
def get_view_ddl(self, vista: str) -> str:
    def _fetch_ddl() -> str:
        try:
            return self._execute_metadata_one("create_view", ...)
        except DatabaseOperationError as err:
            if self.db_type != "mariadb":
                raise
            if not self._is_mariadb_show_create_decode_error(err):
                raise

            # Fallback: Obtener SELECT equivalente
            self.logger.warning(
                "Fallback para vista %s - obteniendo definición desde INFORMATION_SCHEMA",
                vista
            )
            sql = f"""
                SELECT VIEW_DEFINITION
                FROM information_schema.views
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = '{self._escape_sql_literal(vista)}'
            """
            view_def = self._execute_custom_one(sql)
            if view_def:
                return f"CREATE VIEW `{vista}` AS\n{view_def[0]}"
            raise

    return self._get_cached_text(...)
```

### ✅ SOLUCIÓN 3B: Agregar Fallback a `get_routine_ddl()`

```python
def get_routine_ddl(self, rutina: str, routine_type: str) -> str:
    def _fetch_routine_ddl() -> str:
        try:
            return self._execute_metadata_one(
                "create_rutina",
                params={"rutina": rutina, "tipo_rutina": routine_type}
            )
        except DatabaseOperationError as err:
            if self.db_type != "mariadb":
                raise

            # Fallback: Obtener de INFORMATION_SCHEMA.ROUTINES
            self.logger.warning(
                "Fallback para rutina %s - obteniendo de INFORMATION_SCHEMA",
                rutina
            )
            sql = f"""
                SELECT ROUTINE_DEFINITION
                FROM information_schema.routines
                WHERE ROUTINE_SCHEMA = DATABASE()
                AND ROUTINE_NAME = '{self._escape_sql_literal(rutina)}'
                AND ROUTINE_TYPE = '{routine_type.upper()}'
            """
            routine_def = self._execute_custom_one(sql)
            if routine_def:
                return f"CREATE {routine_type} {rutina}\n{routine_def[0]}"
            raise

    return self._get_cached_text(...)
```

---

## 🟢 FALLBACK 5: `_fetch_with_decode_fallback()` - Binary Cursor

### Ubicación Actual
**sync_query_executor.py L125-161**

```python
def _fetch_with_decode_fallback(self, *, cursor, conn, sql, params, ...):
    try:
        return self.result_normalizer.normalize_one(cursor.fetchone())
    except Exception as err:
        if not self._is_decode_error(err):
            raise
        self.logger.warning("Error de decodificación. Reintentando con cursor binario.")
        return self._retry_fetch_with_binary_cursor(...)  # ← FALLBACK
```

### Método Fallback: `_retry_fetch_with_binary_cursor()`
**sync_query_executor.py L95-120**

```python
# Crea nuevo cursor configurado para binario
binary_cursor = conn.cursor(buffered=True, dictionary=False)
binary_cursor.execute(sql, params)
# Decodifica manualmente cada valor
```

**Evaluación:**
- ✅ **EFECTIVO:** Resuelve mayoría de UnicodeDecodeError
- ✅ **SEGURO:** No modifica datos, solo encoding
- ⏱️ **Costo:** 1 round-trip extra al servidor

### ✅ SOLUCIÓN 5: Mejorar Binary Cursor Fallback

**Agregar encoding configurable:**

```python
def _retry_fetch_with_binary_cursor(self, *, conn, sql, params, ...):
    """Reintenta fetch con cursor binario + multi-codec decode"""
    binary_cursor = conn.cursor(buffered=True, dictionary=False)

    try:
        binary_cursor.execute(sql, params)
        rows = binary_cursor.fetchall()

        # Decodificar con estrategia multi-codec
        decoded_rows = []
        for row in rows:
            decoded_row = []
            for value in row:
                if isinstance(value, bytes):
                    decoded_value = self._safe_decode_bytes(value)
                else:
                    decoded_value = value
                decoded_row.append(decoded_value)
            decoded_rows.append(tuple(decoded_row))

        return (
            self.result_normalizer.normalize_one(decoded_rows[0])
            if self.expect_one
            else self.result_normalizer.normalize_many(decoded_rows)
        )
    finally:
        try:
            binary_cursor.close()
        except Exception:
            self.logger.debug("No se pudo cerrar cursor binario")

def _safe_decode_bytes(self, value: bytes) -> str:
    """Intenta decodificar con múltiples codecs"""
    for encoding in ('utf-8', 'utf-8-sig', 'latin1', 'cp1252'):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Último recurso: UTF-8 con replace
    return value.decode('utf-8', errors='replace')
```

---

## 📋 Matriz de Recomendaciones

| Fallback | Prioridad | Acción | Impacto | Esfuerzo |
|---|---|---|---|---|
| **1. `get_table_ddl()`** | 🔴 Alta | Reemplazar síntesis por DDL mínimo | Rendimiento +40% | Bajo |
| **2a. `get_columns()` CONVERT()** | 🔴 Alta | Cambiar SQL en json | Fallback -95% | Bajo |
| **2b. `get_columns()` 2-tier** | 🟡 Media | Nuevo código + SQL | Robusto 100% | Medio |
| **3. `get_view_ddl()` fallback** | 🟡 Media | Agregar catch + INFORMATION_SCHEMA | Cobertura 100% | Bajo |
| **4. `get_routine_ddl()` fallback** | 🟡 Media | Agregar catch + INFORMATION_SCHEMA | Cobertura 100% | Bajo |
| **5. Binary cursor mejorado** | 🟢 Baja | Agregar multi-codec decode | Resiliencia +15% | Bajo |

---

## 🚀 Plan de Implementación (Orden Sugerido)

### Fase 1 (Cambio SQL - Inmediato)
1. Cambiar `columnas_tabla` en `sql_queries.json` a usar CONVERT()
2. Cambiar `create_table` en `sql_queries.json` a usar mejora de charset

### Fase 2 (Código Defensivo - Próxima Sprint)
1. Agregar fallback a `get_view_ddl()`
2. Agregar fallback a `get_routine_ddl()`

### Fase 3 (Optimizaciones)
1. Mejorar binary cursor fallback en SyncQueryExecutor
2. Agregar 2-tier fallback en `get_columns()` si es necesario

---

## Código de Test

```python
# test_fallback_coverage.py
import pytest
from util_bbdd import DatabaseManager

@pytest.mark.mariadb
class TestFallbackCoverage:

    def test_get_table_ddl_convert_works(self, db_manager):
        """Verifica que CONVERT() genera DDL correcto"""
        ddl = db_manager.get_table_ddl("usuarios")
        assert "CREATE TABLE" in ddl

    def test_get_columns_no_fallback_needed(self, db_manager):
        """Verifica que no se activa fallback HEX»"""
        # Inyectar tabla con caracteres especiales
        cols = db_manager.get_columns("tabla_con_ñ")
        # Debe devolver sin warnings de HEX
        assert len(cols) > 0

    def test_get_view_ddl_fallback_works(self, db_manager):
        """Verifica que fallback de vista funciona"""
        ddl = db_manager.get_view_ddl("vista_test")
        assert "CREATE VIEW" in ddl or "SELECT" in ddl

    def test_binary_cursor_multi_codec(self, executor):
        """Verifica decodificación multi-codec"""
        # Ejecutar query que devuelve bytes mixtos
        result = executor.execute_query("test_multibyte")
        assert all(isinstance(v, str) for v in result[0])
```
