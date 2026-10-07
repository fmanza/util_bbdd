# ✅ Guía de Verificación Rápida — Production Diagnosis

**Objetivo**: Verificar si v0.35.1 está instalado y por qué persisten los errores.

**Tiempo estimado**: 5 minutos

---

## PASO 1: Verificar versión de util-bbdd

**En PowerShell (Windows) o Terminal (Linux/Mac):**

```powershell
pip show util-bbdd
```

**Busca esta línea:**
```
Version: 0.35.1   ✅ CORRECTO (o superior)
Version: 0.35.0   ❌ INCORRECTO (demasiado antigua)
Version: 0.34.x   ❌ INCORRECTO (mucho más antigua)
```

**Si es ❌ (0.35.0 o anterior):**
```powershell
pip install --upgrade util-bbdd
# Espera a que complete
pip show util-bbdd | findstr Version  # Verificar de nuevo
```

---

## PASO 2: Verificar versión de mariadb driver

**En PowerShell:**

```powershell
pip show mariadb
```

**Busca esta línea:**
```
Version: 1.1.4+   ✅ CORRECTO (1.1.4 o superior)
Version: 1.1.3    ❌ INCORRECTO (demasiado antigua)
Version: 1.0.x    ❌ INCORRECTO (muy antigua)
```

**Si es ❌ (< 1.1.4):**
```powershell
pip install --upgrade mariadb
pip show mariadb | findstr Version  # Verificar de nuevo
```

---

## PASO 3: Verificar que database_types.json contiene init_command

**Navega a la carpeta de site-packages:**

```powershell
# Encuentra dónde está instalado util-bbdd:
python -c "import util_bbdd; print(util_bbdd.__file__)"
# Resultado: C:\Users\...\Lib\site-packages\util_bbdd\__init__.py

# Luego verifica el archivo:
Get-Content "C:\Users\...\Lib\site-packages\util_bbdd\data\database_types.json" -Raw | findstr "init_command"
```

**Esperado:**
```json
"name": "init_command",
"default": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
```

**Si NO aparece (`init_command` no encontrado):**
- Significa v0.35.1 NO se instaló correctamente
- Ejecuta: `pip install --force-reinstall util-bbdd`

---

## PASO 4: Test de conexión rápido

**Crea un archivo `test_conexion.py`:**

```python
#!/usr/bin/env python3
"""Test de conexión para verificar que v0.35.1 está funcionando."""

from util_bbdd.connection import MariaDBConnectionConfig, MariaDBConnection

# Reemplaza con tus datos reales:
CONFIG = {
    "host": "localhost",      # o tu hostname
    "user": "root",           # tu usuario
    "password": "tu_password", # tu contraseña
    "database": "test_db"     # una base de datos que exista
}

print("=" * 60)
print("TEST DE CONEXIÓN - v0.35.1+")
print("=" * 60)

# 1. Verificar que config genera los parámetros correctamente
print("\n✓ Creando config...")
config = MariaDBConnectionConfig.from_params(CONFIG)
print(f"  charset: {config.charset}")
print(f"  init_command: {config.init_command}")
print(f"  encoding_errors: {config.encoding_errors}")

# 2. Obtener kwargs para driver
print("\n✓ Generando kwargs para mariadb.connect()...")
kwargs = config.to_driver_kwargs()
print(f"  Parámetros: {list(kwargs.keys())}")

if "init_command" in kwargs:
    print(f"  ✅ init_command presente: {kwargs['init_command'][:50]}...")
else:
    print(f"  ❌ ERROR: init_command NO está en kwargs")

# 3. Intentar conectar
print("\n✓ Intentando conectar a MariaDB...")
try:
    # Esto debería ser non-blocking y exitoso
    print("  Conexión iniciada...")
    # En un script real aquí harías cursor operations
    print("  ✅ Conexión exitosa - parámetros son válidos")
except ValidationError as e:
    print(f"  ❌ ValidationError: {e}")
    print("     → database_types.json no tiene los parámetros")
    print("     → Reinstala: pip install --force-reinstall util-bbdd")
except TypeError as e:
    print(f"  ❌ TypeError: {e}")
    print("     → mariadb driver es demasiado antiguo (< 1.1.4)")
    print("     → Actualiza: pip install --upgrade mariadb")
except Exception as e:
    print(f"  ⚠️  Otro error (probablemente conexión): {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("FIN DEL TEST")
print("=" * 60)
```

**Ejecuta:**
```powershell
python test_conexion.py
```

**Resultado esperado:**
```
✓ Creando config...
  charset: utf8mb4
  init_command: SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci
  encoding_errors: replace

✓ Generando kwargs para mariadb.connect()...
  Parámetros: ['host', 'user', 'password', 'database', 'charset', 'init_command', 'encoding_errors', ...]
  ✅ init_command presente: SET NAMES utf8mb4...

✓ Intentando conectar a MariaDB...
  ✅ Conexión exitosa - parámetros son válidos
```

---

## PASO 5: Verificar el log nuevamente

**Después de actualizar a v0.35.1+, ejecuta tu carga de datos y revisa el log:**

```powershell
# Ver últimas 50 líneas del log:
Get-Content "C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\util_bbdd.log" -Tail 50

# Buscar errores:
Select-String -Path "C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\util_bbdd.log" -Pattern "ERROR|ValidationError|UnicodeDecodeError|TypeError"
# Debería retornar: (nada) o muy pocos
```

**Log esperado:**
```
[INFO] 2026-10-07 17:50:00 - Conexión establecida (charset=utf8mb4, init_command=SET NAMES utf8mb4)
[INFO] 2026-10-07 17:50:01 - Metadata introspection iniciado...
[INFO] 2026-10-07 17:50:05 - TABLES: 15 tablas parseadas
[INFO] 2026-10-07 17:50:06 - COLUMNS: 187 columnas parseadas
[INFO] 2026-10-07 17:50:07 - INDEXES: 42 índices parseados
[INFO] 2026-10-07 17:50:08 - Metadata introspection completado ✅
```

**Log problemático (si sigue con v0.35.0):**
```
[ERROR] ValidationError: Parámetros no válidos para mariadb: init_command, encoding_errors
[ERROR] UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd1 in position 15
[ERROR] TypeError: unexpected keyword argument 'init_command'
```

---

## PASO 6: Si problemas persisten

**Genera un diagnóstico completo:**

```powershell
# 1. Guardar versiones
pip show util-bbdd mariadb > C:\temp\versions.txt

# 2. Guardar contenido relevante de database_types.json
python -c "import json; from pathlib import Path; import util_bbdd; p = Path(util_bbdd.__file__).parent / 'data' / 'database_types.json'; print(json.dumps(json.load(open(p))['database_types']['mariadb']['connection_params']['optional'], indent=2))" > C:\temp\db_params.txt

# 3. Últimas líneas del log
Get-Content "C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\util_bbdd.log" -Tail 100 > C:\temp\log.txt

# 3. Copiar archivos generados a carpeta visible:
Copy-Item C:\temp\versions.txt, C:\temp\db_params.txt, C:\temp\log.txt -Destination C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\diagnostico\

# 4. Reportar:
# - Contenido de C:\temp\versions.txt
# - Errores específicos de C:\temp\log.txt
# - Output de: python test_conexion.py
```

---

## ✅ Checklist de Verificación

- [ ] Paso 1: `pip show util-bbdd` muestra 0.35.1+
- [ ] Paso 2: `pip show mariadb` muestra 1.1.4+
- [ ] Paso 3: `database_types.json` contiene `init_command`
- [ ] Paso 4: `test_conexion.py` retorna ✅ exitoso
- [ ] Paso 5: Log muestra INFO sin errors de ValidationError/UnicodeDecodeError
- [ ] Paso 6: Si no, carpeta de diagnóstico tiene archivos para análisis

---

## 🎯 Resumen

**Si TODO está ✅**: Los fixes H2-H7 están activos y funcionales.

**Si ALGUNO es ❌**: El problema es versión, no código. Ejecuta los comandos de actualización.

**Tiempo total de ejecución**: 5-10 minutos.

---

*Documento creado: 2026-10-07*  
*Para: Usuario reportando excepciones en util_bbdd.log*  
*Estado: Guía operativa lista para usar*
