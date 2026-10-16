# TRACEABILITY

## Session metadata
- id: 2026-10-16b-fix-mysql-redo-variables
- fecha: 2026-10-16
- rama: develop (base `77748174`, tras v2.2.0)
- skill: fix (dos commits) + version_closure v2.2.1
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«Dos riesgos residuales menores, para la 2.2.x: read_variables falla si recibe filas con una forma inesperada; en MySQL
8.0.30+ el advisor sigue leyendo innodb_log_file_size en lugar de innodb_redo_log_capacity. PLAN y AUDIT_PLAN»; después
«si» (implementar) y «si» (cerrar y publicar).

## Context supplied
- Riesgos residuales de `.ai/sessions/2026-10-16-refactor-advisor-strategy/TRACEABILITY.md`
- `SHOW VARIABLES` en el banco: MySQL 8.4.11 (`innodb_log_file_size`=48 MB, `innodb_redo_log_capacity`=100 MB) y
  MariaDB 11.4.13 (`innodb_log_file_size`=96 MB, sin `innodb_redo_log_capacity`)

## AI output summary
- PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`) con 4 decisiones del usuario (todas las recomendadas).
- `ed7c27ea` (R-1, R-1b): `SHOW VARIABLES WHERE Variable_name = '…'`; fila inesperada → WARNING y se omite esa
  variable. Caracterización sin cambios (conexión falsa adaptada); 2 tests. Los 6 avisos «error interno» de
  `tests/unit/test_bulk_crud_helpers.py` (engines `MagicMock`) desaparecen. El ejemplo `mysql_variables_example.py`
  da la misma salida.
- `9627eff5` (R-2): `MySQLReadinessValidator._check_redo_log`; `read_variables` lee `innodb_redo_log_capacity`.
  Caracterización: 0 casos cambian, 10 añadidos (`mysql_8030`); 3 tests. Banco: MySQL 8.4 → `innodb_redo_log_capacity`
  100 MB (antes `innodb_log_file_size` 48 MB); MariaDB 11.4 sin cambios.
- Puertas: ruff, format, mypy (337), `zensical build --strict`; pytest limpio 6078 passed; 6 motores 6602 passed
  (0 avisos «error interno» en integración).
- `/version-closure` v2.2.1: CHANGELOG, versión en `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`,
  pie de `docs/architecture.md` (337 ficheros), `CURRENT_STATE`, `SESSIONS_DIGEST`, `INDEX`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-16b-fix-mysql-redo-variables/PLAN_AUDIT_PLAN.md` | aprobado |
| Logs | `build/logs/r1_*.txt`, `build/logs/r2_*.txt`, `build/logs/v221_*.txt` | generados |

## Rollback
- `git revert 9627eff5 ed7c27ea` (y el commit de release); el tag `v2.2.1` se retira con `git push origin :v2.2.1`.

## Directrices para Futuras IAs
- **[advisor]**: el redo log de MySQL/MariaDB se evalúa en `MySQLReadinessValidator._check_redo_log`: con
  `innodb_redo_log_capacity` (MySQL 8.0.30+) esa variable; sin ella, `innodb_log_file_size`.
- **[mysql]**: `MySQLVariableValidator.read_variables` usa `SHOW VARIABLES WHERE Variable_name = '…'` (nunca `LIKE`:
  el `_` es comodín) y tolera filas inesperadas por variable.
- **[tests]**: la suite con los 6 motores y `-o log_cli=true --log-cli-level=WARNING` tarda ~10 min (sin logs, ~4,5):
  lanzarla en segundo plano.
