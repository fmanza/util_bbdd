# TRACEABILITY

## Session metadata
- id: 2026-10-09g-hsqldb-server
- fecha: 2026-10-09
- rama: develop
- skill: tests de integración + infraestructura de banco (sin cambios en `src/`)
- fase: P5 (H1) de `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md`

## Prompt issued
Continuación del plan aprobado («si»); decisión del usuario para H1: «Contenedor en el banco».

## Context supplied
- `PLAN_AUDIT_PLAN.md` (P5); `tests/integration/metadata/test_hsqldb_catalog.py` (HSQLDB en memoria)

## AI output summary
- Jar `hsqldb-2.7.4.jar` descargado de Maven Central a `build/bench_hsqldb/` (ignorado por git), SHA-1 verificado con el `.sha1` publicado.
- `docker-compose.bench-hsqldb.yml` (opcional): `eclipse-temurin:21-jre` + `org.hsqldb.server.Server`, base en memoria `bench`, `127.0.0.1:59001`, healthcheck por TCP. Servidor en línea («HSQLDB server 2.7.4 is online»).
- `tests/integration/test_hsqldb_server.py` (3): conexión nativa (`jaydebeapi`) lee datos con `ñandú`; `get_schema_metadata()` ve tabla, comentario y columnas; `connection_properties` llega (la conexión funciona) pero `sql.syntax_ora` no actúa contra una base ya creada en el servidor (propiedad de creación; en memoria sí, validado antes).
- `scripts/bench_env.example.{sh,ps1}`: `UTIL_BBDD_TEST_HSQLDB_JAR` y `UTIL_BBDD_TEST_HSQLDB_SERVER_URL` si el jar existe.
- `tests/integration` completo (con `JAVA_HOME=C:/Program Files/Java/jdk-25`): 564 passed, 8 skipped (`build/logs/p5_hsqldb_integration.txt`); antes 559/10.
- Docs: roadmap sin H1; `.ai/runtime.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Compose | `docker-compose.bench-hsqldb.yml` | nuevo |
| Tests | `tests/integration/test_hsqldb_server.py` | nuevo |
| Scripts | `scripts/bench_env.example.sh`, `scripts/bench_env.example.ps1` | modificados |
| Docs | `docs/roadmap.md`, `.ai/runtime.md` | |

## Directrices para Futuras IAs
- **[HSQLDB/servidor]**: la conexión nativa funciona contra un servidor HSQLDB 2.7.4 (`jdbc:hsqldb:hsql://...`); las propiedades `sql.syntax_*` son de creación de base: no sirven para probar `connection_properties` contra un servidor.
- **[HSQLDB/Java]**: en este equipo `JAVA_HOME` no está definido; JPype necesita `JAVA_HOME=C:/Program Files/Java/jdk-25`.

## Veredicto final
Veredicto: CLOSED (H1 cerrado: validado en memoria y en red)
Pendientes al cierre:
- Cierre del plan de pendientes (CURRENT_STATE) y push de `develop` + tag `v0.40.0`.
