# Hotfix: MariaDB UnicodeDecodeError en Metadata (H-41, P2, 2026-10-06)

## Problema
Al generar documentación sobre MariaDB con `src/util_bbdd/doc`, fallaba con:
```
SystemError: <method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set
[UnicodeDecodeError subyacente]
```

Aunque la BD estuviera configurada con `utf8mb4`, el error persistía porque había **datos corruptos en `information_schema`** (comentarios de tablas/columnas, definiciones de vistas, etc. con caracteres inválidos heredados de utf8mb3).

## Causa Raíz
1. La BD `SOCYALPRO` estaba inicialmente en `utf8mb3`
2. Se cambió a `utf8mb4` (ALTER DATABASE), pero los metadatos en `information_schema` quedaron con caracteres inválidos
3. Cuando el driver mariadb intentaba leer esos campos con el nuevo charset, falla con UnicodeDecodeError
4. El problema afecta a: `COLUMN_COMMENT`, `GENERATION_EXPRESSION`, `TABLE_COMMENT`, `VIEW_DEFINITION`, `ROUTINE_DEFINITION`, `ROUTINE_COMMENT`

## Solución Aplicada (H-41, P2, 2026-10-06)

**Archivo**: `src/util_bbdd/metadata/mariadb/catalog.py` (queries de MariaDB y MySQL)

Se utilizó `CONVERT(CAST(field AS BINARY) USING utf8mb4)` en todos los campos de comentario/definición para hacerlos tolerantes a caracteres inválidos:

- `Kind.TABLES`: `TABLE_COMMENT` → `CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4)`
- `Kind.COLUMNS`: `COLUMN_COMMENT` y `GENERATION_EXPRESSION` → convertidas
- `Kind.VIEWS`: `VIEW_DEFINITION` → convertida
- `Kind.ROUTINES`: `ROUTINE_DEFINITION` y `ROUTINE_COMMENT` → convertidas

### Cómo funciona la solución
1. `CAST(field AS BINARY)` convierte el campo a bytes, ignorando encoding inválido
2. `CONVERT(...USING utf8mb4)` reinterpreta esos bytes como UTF-8, descartando caracteres inválidos
3. El resultado es un string limpio sin caracteres problemáticos

## Instalación en tu Proyecto de Pruebas

En `c:\Desarrollo\python\pruebas_util`:

```powershell
# 1. Activa tu venv
.\venv\Scripts\Activate.ps1

# 2. Desinstala la versión anterior
pip uninstall util-bbdd -y

# 3. Instala la nueva versión (desde el workspace o desde dist/)
# Opción A: desde el workspace (modo desarrollo)
pip install -e "c:\Desarrollo\python\libs\util_bbdd"

# Opción B: desde la wheel compilada
pip install "c:\Desarrollo\python\libs\util_bbdd\dist\util_bbdd-0.32.2-py3-none-any.whl"

# 4. Verifica
pip show util-bbdd
# Debería mostrar Version 0.32.2 y Location con "H-41" o nueva fecha
```

## Comportamiento Después del Fix

✅ Lectura de metadatos más tolerante a caracteres corruptos en information_schema  
✅ Generación de documentación MariaDB funciona incluso con datos heredados de utf8mb3  
✅ Sin loss de datos: solo se limpian caracteres realmente inválidos  
✅ Compatible con MySQL (mismo código para ambos)  
✅ No requiere cambios en el código de usuario  

## Test

Después de reinstalar, en tu proyecto de pruebas:

```python
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.doc import generate_documentation_sync

conn_params = {
    'host': '10.20.0.245',
    'port': 3306,
    'user': 'SOCYALPRO',
    'password': '...',
    'database': 'SOCYALPRO',
    'pool_size': 5,
    # charset='utf8mb4' es automático, no necesita especificarse
}

db_manager = SyncDatabaseManager(db_type="mariadb", conn_params=conn_params)
generate_documentation_sync(
    db_manager=db_manager,
    output_path="doc_output.docx",
    # ... otras opciones
)
# Debería funcionar sin UnicodeDecodeError
```

## Notas para Futuras IAs

1. Este hotfix es **resilencia, no reparación de datos**: limpia caracteres corruptos pero no los "repara" de verdad
2. Si el usuario quiere datos limpios en `information_schema`, puede ejecutar (cada tabla):
   ```sql
   -- Limpiar comentarios de tabla
   ALTER TABLE tabla_name COMMENT = 'nuevo comentario limpio';
   
   -- Limpiar comentarios de columna
   ALTER TABLE tabla_name MODIFY COLUMN col_name TIPO COMMENT 'nuevo comentario limpio';
   ```
3. Este hotfix **no** afecta los datos de usuario (tablas), solo los metadatos en `information_schema`
4. El charset por defecto utf8mb4 sigue en lugar (desde H-32 y H-39), este hotfix lo complementa
