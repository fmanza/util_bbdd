# Plan: RCA Profundo de Errores MariaDB + Eliminación de Fallback
**Estado**: PLAN + AUDIT_PLAN (sin IMPLEMENT)  
**Fecha**: 2026-10-06  
**Problema**: `SystemError: fetchrows() returned a result with an exception set` en lectura de catálogo MariaDB  
**Objetivo**: Análisis profundo de causa raíz y propuesta de alternativas sin fallback

---

## 1. PROBLEMA ACTUAL

### Síntoma
```
SystemError: <method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set
Error leyendo el catálogo (retentado 3 veces + fallback latin1 + fallback pymysql)
```

### Contexto Técnico
- **Versión mariadb driver**: `mariadb>=1.1` (pyproject.toml)
- **Versión MariaDB server**: desconocida (no está documentada; puede variar por usuario)
- **Driver**: Connector/Python (extensión C, no pure Python)
- **Mitigation actual**: Retry + fallback latin1 + fallback pymysql (triado, tres capas de fallback)
- **Config UTF-8**: `charset='utf8mb4'` (default desde H-32, hotfix 2026-10-05)

### Hotfixes Anteriores
1. **H-32 (2026-10-05)**: Charset UTF-8mb4 por defecto en `MariaDBConnectionConfig.from_params()`
   - `charset = _opt_str(params, "charset") or "utf8mb4"`
   - Siempre incluye charset en `to_driver_kwargs()`
   - ✅ Resuelve: UnicodeDecodeError en conexión (no en fetch)

2. **H-41 (2026-10-06)**: Plan de CONVERT/CAST en queries (NO IMPLEMENTADO)
   - Propuesto: `CONVERT(CAST(field AS BINARY) USING utf8mb4)` en comentarios
   - Status: En memoria solo, no en código

3. **Fallback Actual**:
   - `ManagerCatalogExecutor.fetch_all()` (línea 232 en _catalog_executor.py)
   - Reintentos 3×: 100ms → 200ms → 400ms backoff
   - Fallback 1: `_fetch_all_latin1_fallback()` (línea 307)
   - Fallback 2: `_fetch_all_pymysql_fallback()` (línea 391)
   - ❌ Problema: Aun así falla

---

## 2. ROOT CAUSE ANALYSIS (Hipótesis)

### 2.1. Nivel del Driver (mariadb>=1.1)

**Hipótesis A1**: Versión mariadb driver tiene bug de encoding con C extension
- **Evidencia**: SystemError específico de `mariadb.cursor.fetchrows()`
- **Rango**: mariadb 1.0–1.2+ puede tener variaciones
- **Acción de investigación**:
  - [ ] Verificar release notes de mariadb driver 1.1, 1.2, 1.3 para charset/encoding fixes
  - [ ] Probar con versión más reciente (`mariadb>=1.2` o `>=1.3`)
  - [ ] Verificar si el error es conocido en repositorio oficial

**Hipótesis A2**: Interacción driver mariadb + SQLAlchemy pooling
- **Evidencia**: Error durante `fetchrows()`, no durante `connect()` o `execute()`
- **Mecanismo**: Pool de SQLAlchemy reutiliza conexiones; charset podría resetarse
- **Acción de investigación**:
  - [ ] Verificar si SQLAlchemy `pool_recycle` o `pool_pre_ping` afecta charset
  - [ ] Comprobar si usar conexión no-pooled también falla
  - [ ] Validar que `SET NAMES 'utf8mb4'` persiste en pool

**Hipótesis A3**: Parámetro `charset` en mariadb driver no es suficiente
- **Evidencia**: UTF-8 por defecto, pero sigue fallando
- **Mecanismo**: Algunos drivers requieren además `set_character_set()` o equivalente
- **Acción de investigación**:
  - [ ] Revisar documentación oficial de mariadb driver (mariadb.readthedocs.io)
  - [ ] Probar con `connection.set_charset()` post-conexión (si existe API)
  - [ ] Validar que `character_set_client`, `character_set_connection` son UTF-8 en sesión

---

### 2.2. Nivel del Servidor MariaDB

**Hipótesis B1**: Versión MariaDB server antigua (<10.5) o configuración deficiente
- **Evidencia**: Datos heredados de utf8mb3 en information_schema (H-41)
- **Escenario**: Servidor actualizado utf8mb3 → utf8mb4, pero metadatos no limpiados
- **Acción de investigación**:
  - [ ] Consultar `SELECT VERSION()` en servidor destino
  - [ ] Revisar `information_schema.SCHEMATA` → `DEFAULT_CHARACTER_SET_NAME`
  - [ ] Verificar si `character_set_server`, `character_set_connection` en MariaDB están en UTF-8
  - [ ] Ejecutar: `SELECT @@character_set_client, @@character_set_connection, @@character_set_database;`

**Hipótesis B2**: information_schema contiene datos realmente corruptos (no reconvertibles)
- **Evidencia**: Fallback latin1 + pymysql también fallan
- **Mecanismo**: Bytes inválidos incluso en latin1 (0x00–0xFF no cubren todo)
- **Acción de investigación**:
  - [ ] Ejecutar: `SELECT HEX(TABLE_COMMENT), TABLE_NAME FROM information_schema.TABLES WHERE CHAR_LENGTH(HEX(TABLE_COMMENT)) > LENGTH(TABLE_COMMENT)*2;`
  - [ ] Buscar bytes fuera de rango UTF-8 o latin1
  - [ ] Si existen, la única solución es limpieza en BD

**Hipótesis B3**: Collation mismatch entre servidor y cliente
- **Evidencia**: Algunos collations pueden causar conversion errors
- **Acción de investigación**:
  - [ ] Verificar collation_connection vs. collation_database
  - [ ] Probar con `SET collation_connection = 'utf8mb4_general_ci';`

---

### 2.3. Datos Corruptos en Information Schema

**Hipótesis C1**: Caracteres heredados utf8mb3 no convertibles a utf8mb4
- **Evidencia**: H-41 propone CONVERT/CAST, sugiere datos corruptos conocidos
- **Escenarios comunes**:
  - Comentarios con emojis o caracteres fuera de BMP (U+10000+)
  - Conversión incompleta utf8mb3 → utf8mb4
  - Migraciones de BD antigas sin validación
- **Acción de investigación**:
  - [ ] Ejecutar query con CAST/CONVERT para detectar filas problemáticas
  - [ ] Identificar qué campos contienen datos corruptos (COLUMN_COMMENT, TABLE_COMMENT, ROUTINE_DEFINITION)
  - [ ] Evaluar impacto: ¿cuántas tablas/columnas afectadas?

---

## 3. ALTERNATIVAS SIN FALLBACK (Propuestas por Motor)

### 3.1. MariaDB: Opción A – Forzar PyMySQL como Driver Principal

**Descripción**: Usar PyMySQL (pure Python) en lugar de mariadb connector
- **Ventaja**: Pure Python → sin problemas de extensiones C
- **Ventaja**: PyMySQL maneja encoding sin SystemError
- **Desventaja**: Más lento que extensión C (20–30% típico)
- **Compatibilidad**: PyMySQL es compatible 100% con MySQL/MariaDB

**Implementación**:
```python
# src/util_bbdd/connection/factory.py
class ConnectionFactory:
    def create_sync(self, db_type: str, pool_config: dict) -> Any:
        if db_type.lower() in ("mariadb", "mysql"):
            return self._create_pymysql_connection(pool_config)  # Always PyMySQL
        # ... otros motores
```

**Cambios Necesarios**:
- [ ] Registrar PyMySQL como driver por defecto para MariaDB
- [ ] Actualizar `MariaDBConnectionConfig` → usar PyMySQL kwargs
- [ ] Eliminar fallback pymysql (ya es driver principal)
- [ ] Simplificar retry logic (sin fallback C extension)

**Riesgo**: Performance para bulk operations

---

### 3.2. MariaDB: Opción B – Charset y Collation Explícitos en Sesión

**Descripción**: Garantizar UTF-8 a nivel de sesión sin depender del driver
- **Mecanismo**:
  1. Tras conectar: `SET NAMES 'utf8mb4';`
  2. Opcional: `SET collation_connection = 'utf8mb4_general_ci';`
  3. Validación: `SELECT @@character_set_client, @@character_set_connection;`
  4. Si no coincide UTF-8, lanzar error explícito (no fallback)

**Ventaja**: Garantiza sesión limpia incluso si config servidor difiere
**Ventaja**: Compatible con ambos drivers (mariadb + pymysql)
**Ventaja**: Detecta problemas de servidor temprano

**Implementación**:
```python
# src/util_bbdd/connection/factory.py
def _ensure_mariadb_charset(connection):
    cursor = connection.cursor()
    cursor.execute("SET NAMES 'utf8mb4'")
    cursor.execute("SELECT @@character_set_client, @@character_set_connection")
    client_cs, conn_cs = cursor.fetchone()
    cursor.close()
    if client_cs.lower() not in ("utf8", "utf8mb4") or conn_cs.lower() not in ("utf8", "utf8mb4"):
        raise MetadataError(
            f"Charset mismatch: client={client_cs}, connection={conn_cs}. "
            f"Expected UTF-8. Configure MariaDB with --character-set-server=utf8mb4"
        )
```

**Riesgo**: Costo overhead (validación extra por conexión)

---

### 3.3. MariaDB: Opción C – Limpiar Metadata en Queries (CONVERT/CAST)

**Descripción**: SQL-level cleanup en queries de catálogo (H-41 implementado)
- **Mecanismo**: `CONVERT(CAST(field AS BINARY) USING utf8mb4)` en campos problemáticos
- **Ventaja**: Resilencia a datos corruptos en BD
- **Ventaja**: Solución a nivel query, sin cambiar driver/conexión
- **Desventaja**: Solo limpia output, no resuelve problema de raíz

**Campos a proteger**:
- `information_schema.TABLES.TABLE_COMMENT`
- `information_schema.COLUMNS.COLUMN_COMMENT`
- `information_schema.COLUMNS.GENERATION_EXPRESSION`
- `information_schema.VIEWS.VIEW_DEFINITION`
- `information_schema.ROUTINES.ROUTINE_DEFINITION`

**Implementación**:
```python
# src/util_bbdd/metadata/mariadb/catalog.py
Kind.TABLES: (
    "SELECT TABLE_NAME, "
    "CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4) AS TABLE_COMMENT, "
    "TABLE_COLLATION FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = :schema ...",
    ...
)
```

**Riesgo**: No resuelve SystemError del driver (solo si error ocurre tras fetch)

---

### 3.4. MariaDB: Opción D – Leer Metadatos en Modo Binario

**Descripción**: Forzar lectura sin encoding (como binary), re-codificar en Python
- **Mecanismo**:
  1. Ejecutar query con `SET NAMES 'binary'` (sin interpretación)
  2. Recibir strings como bytes/latin1
  3. Re-codificar Python-side: try UTF-8, fallback con replace
  4. Aplicar a nivel driver (no afecta datos de usuario)

**Ventaja**: Control total en Python
**Ventaja**: Evita interpretación prematura del driver
**Desventaja**: Duplica logic de fallback actual (no es mejora sin fallback)

---

### 3.5. MariaDB: Opción E – Error Explícito + Guía de Remediación

**Descripción**: Detectar charset deficiente en servidor, lanzar error claro (no fallback)
- **Mecanismo**:
  1. En primera conexión: validar `@@character_set_server`
  2. Si no es UTF-8: lanzo `MetadataError` con instrucciones claras
  3. Sin reintentos, sin fallback

**Ventaja**: Falla rápido, transparencia completa
**Ventaja**: Obliga a usuario a configurar servidor correctamente
**Desventaja**: No tolera configuraciones "casi correctas"

**Mensajes de Error (claros, accionables)**:
```
❌ MariaDB charset mismatch:
- Servidor: @@character_set_server = '{actual}' (esperado 'utf8mb4')
- Cliente: @@character_set_client = '{actual}' (esperado 'utf8mb4' o 'utf8')

Solución (elegir una):
1. Alterar BD: ALTER DATABASE {db} CHARACTER SET utf8mb4;
2. Alterar servidor: SET GLOBAL character_set_server='utf8mb4'; (temporal)
3. my.cnf: [mysqld] character_set_server=utf8mb4 (permanente)
4. Comando de inicio: mysqld --character-set-server=utf8mb4

Docs: https://mariadb.com/kb/en/...
```

---

## 4. MATRIZ DE DECISIÓN

| Opción | Pro | Contra | Recomendación | Independencia Motor |
|---|---|---|---|---|
| **A: PyMySQL** | Pure Python, sin SystemError, simple | Overhead performance 20–30% | ⭐⭐ Medio (bulk peor) | Sí (MySQL compatible) |
| **B: Charset Validación** | Detecta problemas temprano, overhead bajo | Requiere `SET NAMES` en sesión | ⭐⭐⭐ Alto (combinar C) | Sí (ambos drivers) |
| **C: CONVERT/CAST** | SQL-level resilence, solo queries | No resuelve SystemError | ⭐ Bajo (para datos corruptos) | Sí (MySQL compatible) |
| **D: Binary Read** | Control Python | Duplica fallback, overhead | ❌ No recomendado | Sí (ambos drivers) |
| **E: Error Explícito** | Transparencia, falla rápido | User debe corregir servidor | ⭐⭐⭐⭐ Alto (correcto) | Sí (ambos drivers) |

---

## 5. ESTRATEGIA RECOMENDADA (SIN FALLBACK)

### Enfoque Combinado (B + C + E)

**Fase 1: Validación de Servidor (Opción E)**
```python
def _validate_mariadb_charset(connection: Any) -> None:
    """Falla explícitamente si servidor no tiene UTF-8."""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT @@character_set_server, @@character_set_client, @@character_set_connection"
    )
    server_cs, client_cs, conn_cs = cursor.fetchone()
    cursor.close()
    
    if server_cs.lower() not in ("utf8mb4", "utf8"):
        raise MetadataError(f"MariaDB: character_set_server='{server_cs}', "
                          f"esperado 'utf8mb4'. Ejecute: ALTER DATABASE CHARACTER SET utf8mb4;")
```

**Fase 2: Charset Sesión (Opción B)**
```python
def _ensure_session_charset(connection: Any) -> None:
    """Garantiza UTF-8 en sesión actual."""
    cursor = connection.cursor()
    cursor.execute("SET NAMES 'utf8mb4', @@collation_connection='utf8mb4_general_ci'")
    cursor.close()
```

**Fase 3: Retry Limitado (Simplicidad)**
```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    # Máximo 2 reintentos (no 3), sin fallback
    for attempt in range(2):
        try:
            return DbapiCatalogExecutor(...).fetch_all(sql, params)
        except SystemError as exc:
            if attempt == 0:
                logger.warning(f"Retry 1/2: {exc}")
                time.sleep(100 / 1000)
                continue
            # Segundo intento falló: error explícito
            raise MetadataError(
                f"MariaDB charset error después de {attempt+1} intentos. "
                f"Verifique: (1) character_set_server='utf8mb4', "
                f"(2) información_schema sin datos corruptos, "
                f"(3) versión mariadb driver >= 1.2"
            ) from exc
```

**Fase 4: Query-Level Cleanup (Opción C, selectiva)**
- Aplicar solo a campos problemáticos conocidos (comentarios, definiciones)
- No a todas las queries (overhead)
- Versión independiente por motor

---

## 6. ELIMINACIÓN DE FALLBACK

### Cambios Arquitectónicos

**Archivo**: `src/util_bbdd/managers/_catalog_executor.py`

1. [ ] **Eliminar métodos**:
   - `_fetch_all_latin1_fallback()` (línea 307)
   - `_fetch_all_pymysql_fallback()` (línea 391)
   - `_extract_mariadb_connection_params()` (línea ~190)

2. [ ] **Simplificar `fetch_all()`**:
   - Reducir a 2 reintentos (no 3)
   - Sin fallback a charset alternativo
   - Error explícito con diagnóstico

3. [ ] **Actualizar `AsyncManagerCatalogExecutor`**:
   - Mismo patrón (async version)
   - Eliminar fallbacks duplicados (línea ~543)

4. [ ] **Tests de Arquitectura**:
   - `tests/unit/test_architecture_metadata_rules.py` → actualizar conteos de fallback
   - `tests/integration/test_mariadb_charset.py` → validar nuevo comportamiento

### Impacto en Dependencias

**Antes**:
```
_catalog_executor.py → mariadb driver → si falla → pymysql fallback
```

**Después**:
```
_catalog_executor.py → mariadb driver → validación explícita → error o éxito
```

**Simplicidad**: Menos código, responsabilidades claras, fallos tempranos

---

## 7. INVESTIGACIÓN NECESARIA (Pre-Implementación)

### 7.1. Verificaciones Técnicas

- [ ] **MariaDB Driver Changelog**: Buscar charset/encoding fixes en 1.1–1.3
- [ ] **MariaDB Server Versions**: ¿Qué versiones usan los usuarios del proyecto?
- [ ] **PyMySQL vs mariadb**: Benchmark de performance (bulk operations)
- [ ] **SQLAlchemy Pool**: Impacto de `pool_recycle` en charset

### 7.2. Testing

- [ ] **Crear BD MariaDB con charset utf8mb3** (legacy scenario)
- [ ] **Probar error actual**: Reproducir SystemError
- [ ] **Validar cada alternativa**:
  - A: PyMySQL fallback → ¿es resilente?
  - B: SET NAMES + validación → ¿cubre el error?
  - C: CONVERT/CAST → ¿suficiente para metadata corrupta?
  - E: Error explícito + mensajes → ¿usable por usuarios?

### 7.3. Documentación

- [ ] **Guía de configuración**: MariaDB charset mínimo requerido
- [ ] **Troubleshooting**: Qué hacer si falla + soluciones
- [ ] **Performance**: Impacto de charset validation + CONVERT/CAST

---

## 8. ROADMAP (Fases)

### Fase 1: Investigación (1–2 sesiones)
- [ ] RCA completo de causa en versión actual
- [ ] Testing de hipótesis (A1, B1, C1)
- [ ] Benchmark alternativas

### Fase 2: Selección de Estrategia (1 sesión)
- [ ] Decidir: PyMySQL + Charset Validation, o solo Validation + CONVERT
- [ ] Validar con usuarios/stakeholders (performance vs. reliability)

### Fase 3: Implementación (2–3 sesiones)
- [ ] Actualizar `MariaDBConnectionConfig`
- [ ] Refactorizar `ManagerCatalogExecutor` (eliminar fallback)
- [ ] Tests completos

### Fase 4: Release & Monitoring (1 sesión)
- [ ] Version bump (0.32.3 o 0.33.0)
- [ ] CHANGELOG + guía de migración
- [ ] Monitoreo de issues en GitHub

---

## 9. DECISIÓN: Recomendación Final

**Estrategia Recomendada**: **Opción B (Charset Validation + Retry Simple) + Opción C (CONVERT Selectivo)**

**Razones**:
1. ✅ Falla explícita (error claro, no fallback oculto)
2. ✅ Independiente de driver (mariadb o pymysql)
3. ✅ Costo bajo (validación 1× por pool, no por query)
4. ✅ Escalable (solución por motor, no global)
5. ✅ Resilencia (CONVERT para datos heredados)

**No recomendar**:
- ❌ Opción A (PyMySQL full): Overhead performance sin garantía de fix
- ❌ Opción D (Binary Read): Duplica fallback sin mejora
- ❌ Fallback actual: Demasiado complejo, no resuelve raíz

---

## 10. Matriz de Verificación (AUDIT_PLAN)

| Aspecto | Verificación | Status |
|---|---|---|
| **RCA** | ¿Se identificó si es driver/server/datos? | ⬜ Pendiente (sesión investigación) |
| **Alternativas** | ¿Se evaluaron 5+ opciones con pro/contra? | ✅ DONE (este doc) |
| **Sin Fallback** | ¿Se propone eliminación de fallback? | ✅ DONE (sección 6) |
| **Independencia Motor** | ¿Solución funciona para MySQL también? | ✅ Sí (Charset Validation, CONVERT) |
| **Tests** | ¿Cobertura de casos edge (charset mismatch)? | ⬜ Pendiente (diseño + impl) |
| **Docs** | ¿Guía clara para usuarios (troubleshooting)? | ⬜ Pendiente (post-impl) |

---

**Próximos Pasos**: Ejecutar investigación de RCA (sección 7) para confirmar hipótesis. Luego, seleccionar entre estrategias y proceder a IMPLEMENT.
