# PLAN + AUDIT_PLAN — T-06: validadores del advisor como Strategy (absorbe T-07, T-08, T-11)

- Fecha: 2026-10-16 · Rama: `develop` (HEAD `1c4b07b4`) · Skill: `refactor` (+ dos `fix:`)
- Origen: `.ai/sessions/2026-10-15b-audit-code-v1.0.0-v2.1.0/TECH_DEBT.md` (T-06, T-07, T-08, T-11)
- Veredicto: **GO** (condiciones resueltas el 2026-10-16, ver «Decisiones»)

## PLAN

**Objetivo**: `EngineReadinessAdvisor` elige el validador de cada motor en un registro (Strategy; OCP) en lugar de un
`_check_<motor>` por motor; los checks de MySQL/MariaDB salen del advisor a un validador con la misma interfaz.

**Realidad del código**

| Hecho | Evidencia |
|---|---|
| Advisor de 732 líneas; ~210 son la lógica de MySQL dentro del advisor | `connection/performance_advisor.py` (`_check_mysql*`, `_MYSQL_MINIMUMS`) |
| PostgreSQL, SQL Server, Oracle y SQLite repiten el mismo envoltorio | `_check_postgresql` … `_check_sqlite` |
| Los 4 validadores y `MySQLVariableValidator` son API pública (`__all__` de `util_bbdd.connection.<motor>`) | `connection/<motor>/__init__.py`, `docs/api/mysql_variables.md` |
| 12 `except Exception` en el advisor, casi todos a DEBUG | T-08 |
| `int()`/`bool()` crudos en `check_static` de PostgreSQL, SQL Server y Oracle | T-07 |
| 125 tests (3 ficheros) caja negra vía `advisor.check`; solo `_conn_params_from_engine` (no se mueve) es privado | `tests/unit/connection/` |

**Rutas**: `connection/performance_advisor.py`, `connection/_advisory.py` (Protocol `ReadinessValidator`), nuevo
`connection/mariadb/_readiness.py` (`MySQLReadinessValidator`, interno), `connection/{postgresql,sqlserver,oracle}/_variables.py`
(F1 solo SQL Server por complejidad; F2/F3), tests de `tests/unit/connection/`.

**Fases** (un commit cada una)

| Fase | Tipo | Contenido |
|---|---|---|
| F0 | `test:` | Caracterización: salida de `check()` por motor con una matriz de `conn_params` y conexiones falsas (límites, inválidos, ausentes, fallos del driver) |
| F1 | `refactor:` | Protocol + registro perezoso; `MySQLReadinessValidator` (mismo comportamiento, incluido el `return` temprano); `SUPPORTED_DB_TYPES` del registro; `SQLServerVariableValidator.check_dynamic` en helpers (Sonar S3776). Caracterización intacta |
| F2 | `fix:` (T-07) | `_to_int`/`_to_bool` en todos los motores; inválido → CRITICAL por parámetro sin perder el resto; MySQL deja de cortar los dinámicos |
| F3 | `fix:` (T-08) | Validadores capturan solo `SQLAlchemyError` y errores de interpretación; la red de seguridad de `check()`/`report_once()` registra en WARNING con traza; fixture de test que falla con ese aviso |
| F4 | — (T-11) | Cerrado sin cambios: el contenido ya tiene una fuente (`ReadinessRows`); solo difiere el estilo de cada Excel |

**Riesgos de regresión**: orden/texto de hallazgos al mover código (F0); semántica de excepciones de MySQL (dinámicos
aislados de estáticos) conservada en F1; ciclos de import (registro perezoso).

## AUDIT_PLAN

- Funcionales: F2 y F3 cambian LOG y hojas «Condiciones del motor» → `fix:` separados con CHANGELOG. F1 sin cambios.
- Técnicos: API pública de los 5 validadores intacta; `MySQLReadinessValidator` interno.
- Seguridad: mismo SQL (listas blancas de `SHOW`/`PRAGMA`, binds de SQL Server y Oracle); errores con solo el tipo.
- Validación: puerta limpia + banco con **los 6 motores** en cada fase.

## Decisiones (usuario, 2026-10-16)

1. `MySQLReadinessValidator` **interno** (sin exportar).
2. F0→F1→F2→F3 en esta sesión, cada fase con su commit.
3. T-11 **cerrado sin cambios**.
4. SQL Server: **recrear en otro puerto**. Hecho: copia `util_bbdd_bench_mssql_backup:2026-10-16` (`docker commit`;
   el contenedor no tenía volúmenes) y recreado con `UTIL_BBDD_BENCH_MSSQL_PORT=51833` (51433 está en el rango
   51336–51435 que reserva Windows). Línea base sobre `1c4b07b4` con los 6 motores: **6371 passed, 7 skipped**
   (`build/logs/t06_baseline_bench6.txt`).
