# PLAN + AUDIT_PLAN — 2.2.1: lectura de variables de MySQL y redo log en MySQL 8.0.30+

- Fecha: 2026-10-16 · Rama: `develop` (`77748174`, tras v2.2.0) · Tipo: dos `fix:` → **v2.2.1** (PATCH)
- Origen: riesgos residuales de `.ai/sessions/2026-10-16-refactor-advisor-strategy/TRACEABILITY.md`
- Veredicto: **GO** (decisiones del usuario 2026-10-16, abajo)

## PLAN

**Realidad del código y del banco**

| # | Hecho | Evidencia |
|---|---|---|
| R-1 | `read_variables` desempaqueta `_name, value_str = rows[0]` en un `try` que solo captura `SQLAlchemyError`: una fila que no sea de 2 columnas lanza `ValueError`/`TypeError`; desde F3 es un WARNING «error interno» y se pierden todos los dinámicos de MySQL | `connection/mariadb/_variables.py:70-88`; `tests/unit/test_bulk_crud_helpers.py` (engines `MagicMock`) |
| R-1b | `SHOW VARIABLES LIKE 'nombre'`: `_` es comodín; `rows[0]` con varias filas sería ambiguo. Hoy 1 fila por nombre en el banco (hipótesis) | MySQL 8.4.11 y MariaDB 11.4.13 del banco |
| R-2 | MySQL 8.4.11: `innodb_log_file_size`=48 MB (ignorada), `innodb_redo_log_capacity`=100 MB (la vigente). El advisor informa 48 MB y recomienda una variable inerte | `SHOW VARIABLES` en el banco |
| R-2b | MariaDB 11.4.13: no existe `innodb_redo_log_capacity`; `innodb_log_file_size`=96 MB sí manda | idem |

**Rutas**: `connection/mariadb/_variables.py` (`read_variables`, `_CRITICAL_VARIABLES`),
`connection/mariadb/_readiness.py` (check de redo log), `tests/unit/connection/test_advisor_characterization.py` (escenario
MySQL 8.0.30+ y conexión falsa con `WHERE Variable_name`), `tests/unit/connection/mariadb/test_mysql_variables_config.py`,
`docs/api/mysql_variables.md`, `docs/guides/performance_readiness_guide.md`.

**Commits**: `fix(connection): read_variables con coincidencia exacta y tolerante a filas inesperadas (R-1, R-1b)` y
`fix(connection): redo log de MySQL 8.0.30+ con innodb_redo_log_capacity (R-2)`; después `/version-closure` v2.2.1.

## AUDIT_PLAN

- Funcionales: en MySQL 8.0.30+ el hallazgo pasa a `innodb_redo_log_capacity` (valor real; ≥512 MB → OK). MariaDB y
  MySQL < 8.0.30 sin cambios.
- Técnicos: `read_variables` (API pública) gana la clave `innodb_redo_log_capacity` cuando el servidor la tiene
  (aditivo). La conexión falsa de la caracterización se adapta al SQL nuevo; los casos existentes no deben cambiar.
- Seguridad: nombres de variable constantes; sin entrada del usuario en el SQL.
- Validación: caracterización (solo casos añadidos), banco MySQL 8.4 (`innodb_redo_log_capacity`=100 MB) y MariaDB 11.4
  (sin cambios), suite completa con los 6 motores.

## Decisiones (usuario, 2026-10-16)

1. R-1: fila inesperada → WARNING y se omite esa variable (como un valor no entero).
2. R-2: en MySQL 8.0.30+ solo `innodb_redo_log_capacity` (umbral 512 MB, recomendación 1–2 GB con `SET GLOBAL`,
   dinámica); `innodb_log_file_size` no se informa allí.
3. `innodb_redo_log_capacity` se añade a las variables de `read_variables` (aditivo, documentado).
4. R-1b: `SHOW VARIABLES WHERE Variable_name = '<nombre>'` (coincidencia exacta) en el mismo fix.
