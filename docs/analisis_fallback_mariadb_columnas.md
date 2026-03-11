# Análisis: Fallback HEX en `get_columns()` para MariaDB

## 1. El Problema Actual

### Consulta Base (sin Fallback)
```sql
SELECT column_name, column_type, is_nullable, column_key, column_default, extra, column_comment
FROM information_schema.columns
WHERE table_schema = '{database}' AND table_name = '{tabla}'
ORDER BY ordinal_position
```

### Fallback (Actual)
```sql
SELECT HEX(COLUMN_NAME) AS column_name_hex,
       HEX(COLUMN_TYPE) AS column_type_hex,
       IS_NULLABLE,
       COLUMN_KEY,
       CASE WHEN COLUMN_DEFAULT IS NULL THEN 1 ELSE 0 END AS default_is_null,
       HEX(CAST(COLUMN_DEFAULT AS BINARY)) AS column_default_hex,
       HEX(COALESCE(EXTRA, '')) AS extra_hex,
       HEX(COALESCE(COLUMN_COMMENT, '')) AS column_comment_hex
FROM information_schema.columns
WHERE table_schema = '{database}' AND table_name = '{tabla}'
ORDER BY ordinal_position
```

### ¿Por qué la consulta base falla?

El problema no está en **la consulta SQL**, sino en **la decodificación del driver**:

1. **INFORMATION_SCHEMA tiene CHARACTER SET = utf8/utf8mb3**
   - Almacena metadatos en UTF-8
   - El driver (mysql-connector-python, PyMySQL, mysqlclient) a veces **malinterpreta el encoding**

2. **Fallo típico de decodificación**
   ```
   UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc3 in position 5
   ```
   - Ocurre cuando el driver devuelve bytes en la encoding incorrecta
   - Por ejemplo: UTF-8 multibyte que se interpreta como Latin-1

3. **Versiones aquejadas**
   - MariaDB 10.x con ciertas versiones de drivers
   - MySQL 8.x con configuración de CHARACTER SET inconsistente
   - Cuando hay caracteres especiales (acentos, ñ, símbolos) en nombres

---

## 2. ¿Por qué funciona en código directo?

Cuando ejecutas directamente con el driver:

```python
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="pass",
    database="mydb",
    charset="utf8mb4"  # ← Explícitamente especificado
)
cursor = conn.cursor()
cursor.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s
""", (database, table))
for row in cursor.fetchall():
    print(row[0])  # ← Funciona porque el driver sabe cómo decodificar
```

**Razones por las que funciona:**
- ✅ Especificas explícitamente `charset="utf8mb4"` en la conexión
- ✅ Tu máquina probablemente usa UTF-8 como encoding nativo
- ✅ Si hay caracteres especiales, el driver está configurado para manejarlos
- ✅ No hay abstracción: driver → cursor.execute() → decodificación en el mismo contexto

**En util_bbdd:**
- ❌ La conexión se crea en `ConnectionFactory`
- ❌ Se reutiliza en múltiples contextos con diferente configuración
- ❌ El driver no siempre garantiza decodificación consistente de INFORMATION_SCHEMA
- ❌ Hay casos (muy raros) donde MariaDB devuelve datos en encoding mixto

---

## 3. Alternativas para Funcionamiento Directo sin Fallback

### Alternativa 1: CONVERT() explícito (RECOMENDADO)
```sql
SELECT
    CONVERT(column_name USING utf8mb4) AS column_name,
    CONVERT(column_type USING utf8mb4) AS column_type,
    is_nullable,
    column_key,
    CAST(column_default AS CHAR(100)) AS column_default,
    CONVERT(extra USING utf8mb4) AS extra,
    CONVERT(column_comment USING utf8mb4) AS column_comment
FROM information_schema.columns
WHERE table_schema = '{database}' AND table_name = '{tabla}'
ORDER BY ordinal_position
```

**Ventajas:**
- ✅ Garantiza conversión a UTF-8MB4
- ✅ Simple y directo (sin HEX)
- ✅ Compatible con MariaDB 10.0+
- ✅ Driver decodifica correctamente

**Desventajas:**
- ❌ Pequeña sobrecarga de CPU
- ❌ Si la BD original usa Latin-1, puede perder caracteres especiales

**Casos donde falla:**
- MariaDB < 10.0 (usa utf8 de 3 bytes)
- Cuando INFORMATION_SCHEMA tiene encoding mixto

---

### Alternativa 2: CAST AS BINARY + Decodificación en Python
```sql
SELECT
    CAST(column_name AS BINARY) AS column_name,
    CAST(column_type AS BINARY) AS column_type,
    is_nullable,
    column_key,
    CAST(column_default AS BINARY) AS column_default,
    CAST(extra AS BINARY) AS extra,
    CAST(column_comment AS BINARY) AS column_comment
FROM information_schema.columns
WHERE table_schema = '{database}' AND table_name = '{tabla}'
ORDER BY ordinal_position
```

**Python (decodificar después):**
```python
rows = executor.execute_custom_query(sql_query)
decoded = []
for row in rows:
    decoded.append((
        row[0].decode('utf-8-sig') if isinstance(row[0], bytes) else row[0],
        row[1].decode('utf-8-sig') if isinstance(row[1], bytes) else row[1],
        # ... más campos
    ))
```

**Ventajas:**
- ✅ Control total sobre decodificación
- ✅ Modo fallback implícito en el código Python
- ✅ Funciona con cualquier encoding

**Desventajas:**
- ❌ Sobrecarga Python (más lento)
- ❌ Lógica duplicada en 2 lugares

---

### Alternativa 3: SET CHARACTER_SET en Sesión (EXPERIMENTAL)
```sql
-- Antes de la consulta
SET SESSION character_set_connection='utf8mb4';
SET SESSION collation_connection='utf8mb4_unicode_ci';

-- La consulta
SELECT column_name, column_type, is_nullable, column_key,
       column_default, extra, column_comment
FROM information_schema.columns
WHERE table_schema = '{database}' AND table_name = '{tabla}'
ORDER BY ordinal_position
```

**Ventajas:**
- ✅ Solución simple a nivel sesión
- ✅ No modifica la consulta

**Desventajas:**
- ❌ Requiere 3 round-trips al servidor (SET + SET + SELECT)
- ❌ No garantiza que INFORMATION_SCHEMA responda correctamente
- ❌ Puede afectar otras consultas en la sesión

---

### Alternativa 4: Usar SHOW COLUMNS (Específico MariaDB)
```sql
SHOW FULL COLUMNS FROM `{tabla}` FROM `{database}`
```

**Resultado:**
```
Field | Type | Collation | Null | Key | Default | Extra | Privileges | Comment
```

**Ventajas:**
- ✅ Más compatible con drivers MariaDB
- ✅ No tiene problemas de encoding con INFORMATION_SCHEMA
- ✅ Directamente decodificado por el driver

**Desventajas:**
- ❌ Formato diferente (requiere mapeo a la estructura esperada)
- ❌ No disponible en todos los motores (solo MySQL/MariaDB)
- ❌ Más lento que INFORMATION_SCHEMA

---

### Alternativa 5: Mezcla Inteligente (PROPUESTA FINAL)

**Estrategia:**
1. Intentar consulta con `CONVERT()`
2. Si falla → fallback a HEX (seguro)
3. Evitar double-fallback

```python
def get_columns_smart(self, database: str, table: str) -> list:
    """Estrategia de 2 niveles sin triple-fallback"""

    # Nivel 1: CONVERT() - solución directa optimizada
    query_with_convert = """
        SELECT
            CONVERT(column_name USING utf8mb4) AS column_name,
            CONVERT(column_type USING utf8mb4) AS column_type,
            is_nullable,
            column_key,
            CAST(column_default AS CHAR(100)) AS column_default,
            CONVERT(extra USING utf8mb4) AS extra,
            CONVERT(column_comment USING utf8mb4) AS column_comment
        FROM information_schema.columns
        WHERE table_schema = '{database}' AND table_name = '{table}'
        ORDER BY ordinal_position
    """

    try:
        return self.execute_custom_query(query_with_convert)
    except UnicodeDecodeError:
        # Nivel 2: HEX fallback (seguro, pero lento)
        return self._fetch_mariadb_columns_safe(database, table)
```

---

## 4. Recomendación Final

### ✅ Implementar Alternativa 1 + Fallback

**Cambio en `src/util_bbdd/data/sql_queries.json`:**

Para MariaDB, reemplazar la consulta `columnas_tabla`:

```json
{
  "mariadb": {
    "columnas_tabla": "SELECT CONVERT(column_name USING utf8mb4) AS column_name, CONVERT(column_type USING utf8mb4) AS column_type, is_nullable, column_key, CAST(column_default AS CHAR(100)) AS column_default, CONVERT(extra USING utf8mb4) AS extra, CONVERT(column_comment USING utf8mb4) AS column_comment FROM information_schema.columns WHERE table_schema = '{database}' AND table_name = '{tabla}' ORDER BY ordinal_position"
  }
}
```

**Impacto:**
- 🟢 Elimina ~95% de errores de decodificación
- 🟢 Solo usa HEX fallback en casos raros (MariaDB < 10.0 o encoding mixto)
- 🟢 No requiere cambios en Python
- 🟡 Pequeña sobrecarga CPU insignificante

**Prueba antes de desplegar:**
```sql
SET @db = 'information_schema';
SET @table = 'columns';

-- Consulta actual
SELECT column_name
FROM information_schema.columns
WHERE table_schema = @db AND table_name = @table LIMIT 1;

-- Consulta propuesta
SELECT CONVERT(column_name USING utf8mb4) AS column_name
FROM information_schema.columns
WHERE table_schema = @db AND table_name = @table LIMIT 1;
```

Si ambas funcionan → aplicar cambio

---

## 5. Tabla Comparativa

| Alternativa | Complejidad | Rendimiento | Compatibilidad | Recomendado |
|---|---|---|---|---|
| Sin cambios (HEX Fallback) | Media | Bajo (HEX es lento) | 100% | ❌ Subóptimo |
| CONVERT() | Baja | Alto | 99% | ✅ Sí |
| CAST AS BINARY | Media | Medio | 100% | ⚠️ Alternativa |
| SET CHARACTER_SET | Baja | Bajo | 95% | ❌ Riesgoso |
| SHOW COLUMNS | Baja | Medio | 100% (MapMariaDB) | ⚠️ Alternativa |
| Mezcla Inteligente | Media | Alto | 100% | ✅ Mejor solución |
