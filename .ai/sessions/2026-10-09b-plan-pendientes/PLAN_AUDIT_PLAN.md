# PLAN + AUDIT_PLAN — pendientes tras `drivers-connections-audit` (v0.39.1)

Fecha: 2026-10-09 · Base: `develop` @ `f5c98bc1` (v0.39.1) · Decisiones del usuario: ver § 0

## 0. Decisiones tomadas (2026-10-09)

| Tema | Decisión |
|---|---|
| Alcance | Los cuatro grupos: mantenimiento, deuda pequeña de código, F3 (TLS con CA propia) y diagnóstico y resto (M5, F5, H1) |
| `init_command` en MariaDB async | Enviarlo a aiomysql **solo si es propio** (distinto de `SET NAMES utf8mb4`); el por defecto se sigue omitiendo |
| `trust_cert` con pymssql | **WARNING** (una vez) indicando que no se aplica y que use pyodbc/aioodbc |
| Schemas `zz_md_*` | **Conservar** (datos de `scripts/bench_metadata.py`); borrar solo los `zz_it_dump_*` huérfanos |
| F3 en el banco | **Recrear el contenedor MariaDB** con CA y certificado propios montados |
| F5 | Unificar con la **semántica del async** |
| H1 | **Contenedor HSQLDB en el banco** (`eclipse-temurin` + `org.hsqldb.server.Server`) |
| M5 | **Una consulta** de diagnóstico + corregir el falso `MIXED` con schema vacío |

## 1. Estado verificado antes de planificar

- Ya resueltos (solo falta reflejarlo en `.ai/CURRENT_STATE.md`): `migrate/zenical-pure` integrada en `develop` y `zensical` 0.0.44 en uso; código de la PR #18 (`MySQLVariableValidator`) en `develop` (estado de la PR sin confirmar: no hay `gh`); la sección «Criterios de Aceptación» ya no existe en el estándar funcional; push y tag de `v0.31.0` hechos.
- Banco: PostgreSQL con 14 `zz_it_dump_*` (los crea `tests/integration/test_dump_engines.py` y los borra en `finally`: quedan de ejecuciones interrumpidas) y 3 `zz_md_*`; MySQL y Oracle con 3 `zz_md_*` cada uno; MariaDB y SQL Server sin `zz_*`.
- Fuera de este plan: publicar el issue del ORA-03106 (`.ai/sessions/2026-10-01y-ora03106-repro/ISSUE_DRAFT.md`) es una acción externa del usuario.

## 2. PLAN por bloques (en orden)

| # | Bloque | Contenido | Comando | Versión |
|---|---|---|---|---|
| P0 | Mantenimiento | `CURRENT_STATE.md` al día (Zenical, PR #18, criterios, v0.31.0); `DROP SCHEMA … CASCADE` de los 14 `zz_it_dump_*` de PostgreSQL | sin flujo (housekeeping) + commit `docs:` | — |
| P1 | Deuda pequeña | **F4**: WARNING de TLS async sin verificar una vez por pool/Engine (no por conexión). **init_command**: `_aiomysql` deja de excluirlo cuando es propio. **trust_cert**: WARNING con pymssql | `/hotfix` (P3) | v0.39.2 |
| P2a | M5 — una consulta | `CharsetStateDetector`/`adiagnose`: las 5 variables en un único `SELECT @@…, @@…`; mismas reglas y mismo `CharsetDiagnosis`; reescritura de los tests de mocks secuenciales (13 `side_effect` en `test_charset_detection.py`) | `/refactor` | v0.39.3 |
| P2b | M5 — falso MIXED | con un schema sin tablas, `_test_read_comments` → `None` no cuenta como fallo de lectura; el estado sale `UTF8MB4_CLEAN` si sesión y BD son utf8mb4 | `/hotfix` | v0.39.3 (mismo cierre que P2a, commits separados) |
| P3 | F5 | los `_build_*_connection_string` sync adoptan la semántica async: coerción a `str` (sin `host='None'`), `database` desde `conn_params` si no se pasa, SQL Server exige `database`, Oracle `service_name=""` → `database` | `/refactor` (cambio de API justificado) | v0.40.0 |
| P4.0 | F3 — investigación (puerta) | comprobar contra el driver real si MariaDB Connector/Python 1.1.14 puede verificar la CA **sin** comprobar el hostname (Connector/C 3.4.7 no expone una opción separada; `ssl_verify_cert` cubre ambos) | lectura + sondeo | — |
| P4 | F3 — `ssl_verify_identity` | campo en `MariaDBConnectionConfig` y JSON; async: `check_hostname` del `SSLContext`; sync: según P4.0. Infraestructura: CA + certificado de servidor (SAN `127.0.0.1`, `localhost`) generados en un directorio ignorado por git; `docker-compose.bench.yml` monta `ssl_ca`/`ssl_cert`/`ssl_key` en MariaDB; contenedor recreado | `/new-feature` | v0.41.0 |
| P5 | H1 — HSQLDB en red | servicio `hsqldb` en `docker-compose.bench.yml` (`eclipse-temurin` + jar 2.7.4 de Maven Central en un directorio ignorado); `UTIL_BBDD_TEST_HSQLDB_URL` en `scripts/bench_env.example.*`; tests de integración de la conexión nativa (`jdbc:hsqldb:hsql://`) | flujo de tests (`test:`/`chore:`); `/hotfix` si aparece un bug | — (o patch si hay fix) |

Orden: primero lo que no toca el banco (P0–P3), después la infraestructura (P4, P5), para que un problema con los contenedores no bloquee el resto. Un commit y un tag por bloque, como en la FASE 4.

## 3. AUDIT_PLAN

### Riesgos funcionales

| Bloque | Riesgo | Mitigación |
|---|---|---|
| P1 init_command | un `init_command` propio que haga `SET NAMES` distinto de `charset` cambia la sesión async (hoy se ignoraba) | es lo que pide el usuario al indicarlo; documentarlo; el por defecto no cambia |
| P1 F4 | un aviso por pool oculta conexiones posteriores mal configuradas | la configuración TLS es la misma para todas las conexiones del pool/Engine |
| P2a | una sola consulta: si una variable no existe en una versión, falla la consulta entera (hoy cada `_fetch_one` devuelve `None` por separado) | `try` sobre la consulta combinada con caída a consultas sueltas; banco MariaDB 11.4 y MySQL 8.4 |
| P2b | un schema vacío pasa de `convert` a `native` | sin tablas no hay comentarios que leer: el resultado de los metadatos no cambia |
| P3 | cambia el Engine sync en casos límite (`host=None`, SQL Server sin `database`) para quien llame a `SQLAlchemyEngineFactory` directamente | sección «Cambios que pueden afectarte» en el CHANGELOG; comparación de salidas antes/después como en B5 (se documentan las diferencias esperadas) |
| P4 | si el sync no puede separar CA y hostname, `ssl_verify_identity=False` no se puede cumplir en sync | puerta P4.0: decidir con el usuario (rechazar con `ValidationError` en sync, o aplicarlo solo en async con aviso) antes de implementar |

### Riesgos técnicos

- **Recrear el MariaDB del banco** (`--force-recreate -V`): borra sus datos (hoy sin `zz_*`) y la contraseña pasa a la de `UTIL_BBDD_BENCH_PASSWORD`, **igual que el resto de servidores** (hoy MariaDB tiene otra). Hay que actualizar el script de entorno del banco y la memoria del proyecto (`feedback-bench-password-from-containers`). Los grants de `mariadb_bench_grants` se reaplican al estar vacío el directorio de datos.
- **TLS obligatorio por error**: montar el certificado no debe activar `require_secure_transport`; las conexiones sin TLS del resto de tests deben seguir funcionando (control sin TLS en la validación).
- **Descargas** (P4/P5): imagen `eclipse-temurin`, jar de HSQLDB 2.7.4 de Maven Central; ficheros fuera de git (`.gitignore`), con suma SHA verificada.
- **P2a**: 13 mocks secuenciales que reescribir; mapear cada caso actual a uno nuevo para no perder cobertura (`_determine_state` no cambia).
- **Contratos sync/async**: `adiagnose` y `CharsetStateDetector` comparten la consulta (`_VARIABLES_SQL`); se cambian juntos.

### Riesgos de seguridad

- Las claves privadas de la CA y del servidor de pruebas no se versionan (directorio ignorado) y solo sirven para el banco local.
- `ssl_verify_identity=False` debilita la verificación: solo con `ssl_ca` y documentado.
- `trust_cert` con pymssql: el WARNING no debe sugerir que el cifrado está verificado.

### Simplificaciones posibles

- P2a y P2b en la misma versión (v0.39.3), commits separados.
- Si P4.0 concluye que el sync no puede separar CA y hostname y el usuario opta por no ofrecerlo en sync, P4 se reduce a async + documentación.
- P5 sin cambios en `src/` si la conexión nativa funciona en red: solo tests e infraestructura.

### Validación por bloque

`ruff`, `mypy`, `pytest` completo, `zensical build --strict`, `tests/integration` (552 + los nuevos) y banco específico: P1 (logs de TLS async, `init_command` propio en MariaDB async, aviso de pymssql), P2 (diagnóstico de 1 consulta y schema vacío en MariaDB/MySQL), P3 (Engine sync de los 5 motores), P4 (CA propia: verificación OK, CA ajena rechazada, hostname incorrecto rechazado salvo `ssl_verify_identity=False`, control sin TLS), P5 (HSQLDB en red: conexión, consulta y metadatos).

### Veredicto

**GO_CONDICIONAL**. Condiciones:

1. P4.0 se resuelve antes de implementar P4 (puede requerir una decisión del usuario).
2. Recrear MariaDB y añadir el servicio HSQLDB solo tras cerrar P0–P3 (banco estable mientras tanto).
3. Tras recrear MariaDB, actualizar la memoria del proyecto sobre la contraseña del banco.
4. Cada bloque cierra con commit, versión y validación contra el banco, como en la FASE 4.
