# GitHub Commit Message — MySQL/MariaDB Variables Automation

## Conventional Commits Format

### Título Principal (Headline)

```
feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations
```

**Componente**: `connection/bulk` (afecta dos módulos: connection.mariadb + bulk)
**Tipo**: `feat` (nueva funcionalidad sin breaking changes)
**Alcance**: MySQL/MariaDB — validación read-only de configuración crítica

---

## Mensaje de Commit Completo (Squashed)

```
feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations

Agrega validación automática de configuración crítica MySQL/MariaDB (max_allowed_packet,
innodb_buffer_pool_size) para prevenir fallos en bulk operations masivas (error 2013:
packet size exceeded) y degradación exponencial de rendimiento.

## Cambios Principales

### 1. MySQLVariableValidator (src/util_bbdd/connection/mariadb/_variables.py)
- Lectura read-only de SHOW VARIABLES (sin permisos SUPER requeridos)
- Métodos: read_variables(), validate(), log_summary(), format_bytes()
- Validación que valores actuales >= mínimos requeridos

### 2. MySQLOptimalConfig (src/util_bbdd/connection/mariadb/_config.py)
- Dataclass congelada con perfiles: dev(), production(), high_volume()
- Factory method suggest(num_rows) retorna configuración automática por dataset size
- Heurística: ≤100K → dev, ≤1M → production, >1M → high_volume

### 3. MySQLMultiRowInsertStrategy.get_min_max_allowed_packet() (src/util_bbdd/bulk/_execution/batch.py)
- Nuevo método que calcula tamaño mínimo de paquete recomendado
- Fórmula: estimated_size = max_rows × avg_row_bytes × 1.5
- Retorna 64–256 MB (potencias de 2, std en MySQL/MariaDB)

### 4. BulkCrud.__validate_mysql_config() (src/util_bbdd/bulk/crud.py)
- Integración automática en __init__ para dialectos mysql/mariadb
- Lee variables actuales y loguea recomendaciones en niveles INFO/WARNING
- Graceful error handling: no bloquea ejecución en caso de fallo

### 5. Exportes Actualizados (src/util_bbdd/connection/mariadb/__init__.py)
- MySQLVariableValidator y MySQLOptimalConfig vía lazy-loading
- 100% backward compatible (no breaking changes)

## Tests Nuevos

- tests/unit/connection/mariadb/test_mysql_variables_config.py: 18 tests
- tests/unit/bulk/test_mysql_min_packet_calculation.py: 8 tests
- Total: 26 tests nuevos, todos pasando

## Validaciones

✅ Lint: ruff check src tests → All checks passed
✅ Type-check: mypy src → 336 source files, no issues
✅ Tests: pytest → 3728 passed, 1 skipped
✅ Backward compatibility: 100% (0 breaking changes)

## Documentación

- CHANGELOG.md actualizado (sección "Added" con detalles técnicos)
- Docstrings 100% completos en todas las clases y métodos
- Ejemplos de uso incluidos en docstrings

## Permisos y Seguridad

- Solo lectura de INFORMATION_SCHEMA (sin SUPER requerido)
- Validación es logging-only (sin modificación de BD)
- Sin cambio de API pública existente
- Integración opt-in vía logging automático

## Versión

- Bump: 0.9.0 → 0.10.0 (MINOR: nuevas clases públicas sin breaking changes)
- Ver pyproject.toml para versión canónica

## Referencias

- PR: https://github.com/fmanza/util_bbdd/pull/18
- TRACEABILITY: .ai/sessions/2026-06-01g-mysql-bulk-variables-automation/TRACEABILITY.md
- CHANGELOG: CHANGELOG.md [Unreleased] → Added

Fixes: Automatiza detección de configuración insuficiente MySQL/MariaDB que causa error 2013
en bulk operations sin avisos tempranos.
```

---

## Variantes por Escenario

### Opción A: Commit Individual (Si squashing)

```
feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations

Agrega MySQLVariableValidator, MySQLOptimalConfig y validación automática en BulkCrud.__init__.
Previene error 2013 (packet size exceeded) y degradación exponencial en bulk inserts masivos.

- read_variables(): Lectura SHOW VARIABLES (sin SUPER)
- validate(): Compara actuales vs. mínimos requeridos
- log_summary(): Loguea recomendaciones en INFO/WARNING
- MySQLOptimalConfig.suggest(num_rows): Recomendación automática por dataset size
- MySQLMultiRowInsertStrategy.get_min_max_allowed_packet(): Calcula packet size mínimo
- BulkCrud.__validate_mysql_config(): Integración logging en __init__

26 tests nuevos (18 variables + 8 packet), 100% backward compatible.
Validaciones: lint ✅, type-check ✅, pytest 3728 passed ✅

Fixes: #17 (Automatizar SHOW VARIABLES para bulk operations)
Closes: https://github.com/fmanza/util_bbdd/pull/18
```

### Opción B: Commit con Body Detallado (Si no squashing)

```
feat(connection): add MySQLVariableValidator y MySQLOptimalConfig

- new: _variables.py con MySQLVariableValidator (read_variables, validate, log_summary)
- new: _config.py con MySQLOptimalConfig (dev, production, high_volume, suggest)
- new: lazy-loading exports en __init__.py

BREAKING CHANGE: None (solo nuevas clases, API pública sin cambios)
Closes: PR #18
```

```
feat(bulk): add get_min_max_allowed_packet() en MySQLMultiRowInsertStrategy

Calcula tamaño mínimo recomendado de paquete basado en max_rows_per_statement.
Estimación: max_rows × avg_row_bytes × 1.5 → retorna 64–256 MB (potencias de 2).

Closes: PR #18
```

```
feat(bulk): integrate MySQL variable validation en BulkCrud.__init__

Lee variables actuales (max_allowed_packet, innodb_buffer_pool_size) y loguea
recomendaciones en niveles INFO/WARNING sin bloquear ejecución.

Graceful error handling: SQLAlchemyError → debug log; ImportError → skip.
Solo ejecuta para dialectos mysql/mariadb.

Closes: PR #18
```

```
docs(changelog): add sección "Added" para MySQL variables automation

- MySQLVariableValidator: validación read-only de variables críticas
- MySQLOptimalConfig: recomendaciones automáticas por workload
- get_min_max_allowed_packet(): cálculo de tamaño mínimo de paquete
- __validate_mysql_config(): integración automática en BulkCrud
- 26 tests nuevos (18 variables + 8 packet calculation)

Closes: PR #18
```

---

## Instrucciones de Push

### 1. Asegurar que la rama develop esté sincronizada con origin

```bash
git fetch origin develop
git merge --ff-only origin/develop
```

### 2. Verificar que el PR #18 esté listo

```bash
git log --oneline -5  # Verificar commits locales
gh pr view 18          # Revisar estado del PR
```

### 3. Hacer commit (si hay cambios no commiteados)

```bash
git add .ai/sessions/2026-06-01g-mysql-bulk-variables-automation/
git commit -m "docs(.ai): traceability + request para sesión MySQL variables automation"
```

### 4. Push a develop

```bash
git push origin develop
```

### 5. Verificar PR en GitHub

```bash
# Visitar: https://github.com/fmanza/util_bbdd/pull/18
# Verificar que todos los checks pasen (CI/CD, lint, tests)
```

### 6. Esperar review + merge

```bash
# Mantener branch develop actualizado mientras se espera
git pull origin develop
```

---

## Checklist Pre-Merge

Antes de solicitar merge (o cuando revisor dé aprobación):

- [ ] PR #18 muestra "Checks passing" (CI/CD verde)
- [ ] Código pasa lint (ruff)
- [ ] Código pasa type-check (mypy)
- [ ] Todos los tests pasan (pytest)
- [ ] CHANGELOG.md actualizado
- [ ] Docstrings completos en todas las clases nuevas
- [ ] No hay conflictos con develop/main
- [ ] No hay breaking changes (backward compatible 100%)

---

## Post-Merge (Próximos Pasos)

1. **Tag versión**: `git tag v0.10.0` (después de merge a main)
2. **Actualizar pyproject.toml**: `version = "0.10.0"`
3. **Crear release en GitHub** con changelog
4. **Publicar en PyPI**: `python -m build && python -m twine upload dist/*` (si aplica)

---

**Mensaje Recomendado**: Usar Opción A (Commit Individual Squashed) si el PR se mergea como single commit.
