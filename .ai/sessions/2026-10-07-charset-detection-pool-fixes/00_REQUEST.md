# Solicitud de Versión 0.35.4

## Objetivo
Cerrar versión 0.35.4 con refactorización de pool connection mariadb.

## Cambios Implementados
1. Extraer `init_command` ANTES de crear mariadb.ConnectionPool() (mariadb v1.1.14 ejecuta init_command durante instantiación, no después)
2. Simplificar init_command de `"SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"` a `"SET NAMES utf8mb4"`
3. Ejecutar init_command manualmente en get_connection() después de obtener conexión
4. Verificar H1-H5 fixes funcionando en production log

## Archivos Modificados
- src/util_bbdd/connection/config.py (lines 71, 78)
- src/util_bbdd/connection/mariadb/pool_connection_mariadb.py (lines 69, 108-110, 152-161)
- src/util_bbdd/data/database_types.json (line 79)
- tests/unit/connection/mariadb/test_mariadb_driver_connection.py (line 37)
- docs/api/connection_factory.md (line 80)
- docs/guides/connection_guide.md (lines 106, 133)
- docs/guides/mariadb_v0.35.0_charset_handling.md (lines 34, 42, 102, 123, 162)
- CHANGELOG.md

## Validaciones Ejecutadas
- ✅ mypy: passed on config.py, pool_connection_mariadb.py
- ✅ ruff: passed on all modified files
- ✅ pytest: 18/18 mariadb connection tests passed
- ✅ Production log: H1-H5 fixes verified working
