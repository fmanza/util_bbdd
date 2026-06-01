## Solicitud Original

**Plataforma**: GitHub Copilot Chat
**Fecha**: 2026-06-01
**Usuario**: fmanza

### Prompt Inicial

> revisar el módulo src\util_bbdd\bulk y ver cual es la mejor estrategia para automatizar las siguientes variables... SHOW VARIABLES LIKE 'max_allowed_packet'; SET GLOBAL max_allowed_packet = 67108864; SHOW VARIABLES LIKE 'innodb_buffer_pool_size'; SET GLOBAL innodb_buffer_pool_size = 1073741824;

### Contexto Adicional Proporcionado

- Rama activa: `develop`
- Proyecto: util_bbdd (librería Python de utilidades de BD)
- Problema: Bulk operations en MySQL/MariaDB fallan con error 2013 cuando max_allowed_packet es insuficiente
- Objetivo: Automatizar lectura y recomendación de configuración crítica antes de cargas masivas

### Evolución de Requisitos

**Fase 1 (Inicial)**: Revisar módulo bulk, proponer estrategia para leer SHOW VARIABLES

**Fase 2 (PLAN)**: Propuesta aceptada para implementar 4 capas:
1. MySQLVariableValidator — lectura read-only
2. MySQLOptimalConfig — recomendaciones por workload
3. MySQLMultiRowInsertStrategy.get_min_max_allowed_packet() — cálculo de tamaño
4. BulkCrud.__validate_mysql_config() — integración + logging

**Fase 3 (Usuario aprobó con "Si")**: Proceder a IMPLEMENT

### Alcance Acordado

- **Módulos afectados**: `connection.mariadb`, `bulk`
- **Cambios**: 2 módulos nuevos + 2 métodos integrados + 26 tests nuevos
- **Backward compatibility**: 100% (no breaking changes)
- **Permisos requeridos**: Read-only (sin SUPER)
- **Impacto**: Logging-only (sin excepción de fallo)

### Restricciones

- Sin modificación de BD (read-only validation)
- Sin cambio de API pública existente
- Sin expansion de alcance fuera de MySQL/MariaDB
- Documentación obligatoria en docstrings y CHANGELOG

### Criterio de Éxito

✅ Lint pass (ruff)
✅ Type-check pass (mypy 336 files)
✅ Test pass (pytest 3700+ tests)
✅ Backward compatible (0 breaking changes)
✅ CHANGELOG actualizado
✅ PR creada y OPEN
