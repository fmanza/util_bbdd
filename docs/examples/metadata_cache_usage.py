"""
Ejemplo: Usar DatabaseMetadataCache para consultas rápidas de metadatos.

Este ejemplo demuestra cómo:
1. Usar DatabaseMetadataCache para almacenar metadatos en memoria
2. Consultar metadatos sin queries repetidas a BD
3. Mejorar performance en operaciones que requieren metadatos
4. Sincronizar cache cuando schema cambia
"""

import logging

from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache

# Configurar logging para ver el caché en acción
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ============================================================================
# 1. CREAR MANAGER Y CACHE
# ============================================================================

print("=" * 70)
print("1️⃣  Crear DatabaseManager y Cache")
print("=" * 70)

# Conectar a BD (SQLite como ejemplo portátil)
db_url = "sqlite:///example.db"
db_manager = SyncDatabaseManager.create(
    connection_string=db_url,
    log_queries=False,
)

# Crear instancia de cache (inicialmente vacío)
metadata_cache = DatabaseMetadataCache()
print("✅ Cache inicializado (vacío)\n")

# ============================================================================
# 2. PRIMERA VEZ: QUERY A BD + GUARDAR EN CACHE
# ============================================================================

print("=" * 70)
print("2️⃣  Obtener metadatos de BD (1ª vez: query, luego guardar en cache)")
print("=" * 70)

# Obtener columnas de tabla (query a BD)
print("📌 Obteniendo columnas de tabla 'products' desde BD...")
columns = db_manager.get_table_columns(schema="main", table="products")
print(f"✅ Obtenidas {len(columns)} columnas\n")

# Guardar en cache con clave (schema, tabla)
table_key = ("main", "products")
metadata_cache.set_columns(table_key, columns)
print(f"💾 Guardadas en cache con clave: {table_key}\n")

# ============================================================================
# 3. SEGUNDA VEZ: LEER DEL CACHE (MÁS RÁPIDO)
# ============================================================================

print("=" * 70)
print("3️⃣  Consultar mismo metadato desde CACHE (sin query a BD)")
print("=" * 70)

# Leer del cache (instantáneo, sin query BD)
cached_columns = metadata_cache.get_columns(table_key)

if cached_columns:
    print(f"✅ Columnas desde CACHE ({len(cached_columns)} items):")
    for col in cached_columns[:3]:  # Mostrar primeras 3
        print(f"   - {col}")
    print(f"   ... y {len(cached_columns) - 3} más\n")
else:
    print("❌ No encontrado en cache\n")

# ============================================================================
# 4. CASO DE USO: CONSTRUIR ÍNDICE DE METADATOS
# ============================================================================

print("=" * 70)
print("4️⃣  Pre-cargar cache con metadatos de todas las tablas")
print("=" * 70)

# Obtener lista de tablas
tables = db_manager.get_tables()
print(f"📌 Tablas en BD: {len(tables)} encontradas\n")

# Pre-cargar cache para cada tabla
for table_info in tables[:3]:  # Primeras 3 para demo
    schema = table_info.get("table_schema", "main")
    table_name = table_info.get("table_name")

    print(f"   Pre-cargando: {schema}.{table_name}")

    # Obtener y cachear columnas
    cols = db_manager.get_table_columns(schema=schema, table=table_name)
    metadata_cache.set_columns((schema, table_name), cols)

    # Obtener y cachear PKs
    pks = db_manager.get_table_primary_keys(schema=schema, table=table_name)
    metadata_cache.set_primary_keys((schema, table_name), pks)

    # Obtener y cachear FKs
    fks = db_manager.get_table_foreign_keys(schema=schema, table=table_name)
    metadata_cache.set_foreign_keys((schema, table_name), fks)

print(f"✅ Cache pre-cargado para {min(3, len(tables))} tablas\n")

# ============================================================================
# 5. USAR CACHE EN LÓGICA DE APLICACIÓN
# ============================================================================

print("=" * 70)
print("5️⃣  Usar cache en lógica de aplicación")
print("=" * 70)


def validate_columns_fast(schema: str, table: str, required_cols: list[str], cache: DatabaseMetadataCache) -> bool:
    """Validar que columnas existen (usando cache)."""

    # Intentar obtener del cache primero
    table_key = (schema, table)
    cached_cols = cache.get_columns(table_key)

    if cached_cols is None:
        # No en cache, obtener de BD y cachear
        print(f"   Cache MISS para {schema}.{table}, obteniendo de BD...")
        cached_cols = db_manager.get_table_columns(schema=schema, table=table)
        cache.set_columns(table_key, cached_cols)
    else:
        print(f"   Cache HIT para {schema}.{table} ✅")

    # Validar
    available = {col.get("column_name") for col in cached_cols}
    missing = set(required_cols) - available

    if missing:
        print(f"   ❌ Columnas faltantes: {missing}")
        return False

    print("   ✅ Todas las columnas presentes")
    return True


# Test: Validar columnas (1ª vez: BD, 2ª vez: cache)
print("1ª validación (BD):")
validate_columns_fast("main", "products", ["id", "name"], metadata_cache)

print("\n2ª validación (CACHE):")
validate_columns_fast("main", "products", ["id", "name"], metadata_cache)

# ============================================================================
# 6. INVALIDAR CACHE CUANDO SCHEMA CAMBIA
# ============================================================================

print("\n" + "=" * 70)
print("6️⃣  Invalidar cache cuando schema cambia")
print("=" * 70)

print("📌 Simulando: Agregar columna a tabla...")

# Limpiar cache específico
table_key = ("main", "products")

print(f"🗑️  Invalidando cache para {table_key}...")
metadata_cache.set_columns(table_key, None)  # Ó simplemente no usarlo más

print("✅ Próxima consulta obtendrá metadatos frescos de BD\n")

# ============================================================================
# 7. MONITORING: ESTADÍSTICAS DEL CACHE
# ============================================================================

print("=" * 70)
print("7️⃣  Estadísticas del cache (cuántos items cachéados)")
print("=" * 70)

# El cache no expone estadísticas públicamente, pero podemos inspeccionarlo
if hasattr(metadata_cache, "_columns_cache"):
    cached_tables = len(metadata_cache._columns_cache)
    print(f"📊 Tablas con columnas cachéadas: {cached_tables}")

    if hasattr(metadata_cache, "_primary_keys_cache"):
        cached_pks = len(metadata_cache._primary_keys_cache)
        print(f"📊 Tablas con PKs cachéadas: {cached_pks}")

print("\n✨ Ejemplo completado.\n")

# ============================================================================
# 8. CASOS DE USO ADICIONALES (Comentados)
# ============================================================================

# --- Caso 1: Cache global reutilizable ---
# cache = DatabaseMetadataCache()  # Crear una sola vez
#
# async def get_schema_info(manager, schema, table):
#     key = (schema, table)
#
#     # Intentar cache
#     cols = cache.get_columns(key)
#     if cols is None:
#         cols = manager.get_table_columns(schema=schema, table=table)
#         cache.set_columns(key, cols)
#
#     return cols

# --- Caso 2: Invalidación inteligente ---
# def update_schema_and_invalidate(manager, schema, table, ddl):
#     """Actualizar schema e invalidar cache."""
#     manager.execute_custom(ddl)
#
#     key = (schema, table)
#     cache.set_columns(key, None)  # Invalidar
#     cache.set_primary_keys(key, None)
#     cache.set_foreign_keys(key, None)

# --- Caso 3: Pre-carga en startup ---
# async def preload_cache_on_startup(manager, cache):
#     """Pre-cargar cache al iniciar app."""
#     tables = manager.get_tables()
#     for table in tables:
#         schema = table["table_schema"]
#         name = table["table_name"]
#
#         cols = manager.get_table_columns(schema=schema, table=name)
#         pks = manager.get_table_primary_keys(schema=schema, table=name)
#
#         key = (schema, name)
#         cache.set_columns(key, cols)
#         cache.set_primary_keys(key, pks)
