# TRACEABILITY

## Session metadata
- id: 2026-09-24-bench-containers-independence
- fecha: 2026-09-24
- rama: develop
- skill: plan-architect (PLAN + AUDIT_PLAN) → implementación aprobada
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + VERIFY

## Prompt issued
```
Quiero independencia con los contenedores, para postgres has usado el que tenia levantado, quiero usar uno propio para su idependencia y yque este y el resto el puerto sea diferencte al estandar. PLAN y AUDIT_PLAN
```
Decisiones del usuario tras el AUDIT_PLAN:
```
Fixtures de conftest.py: eliminarlas (lo recomiendo, porque nadie las usa)
SQL Server: crear la base propia bench (D)
Puertos: mantener los actuales (55432, 53306, 53307, 51433, 51521), configurables por variable
```

## Context supplied
- `docker-compose.bench.yml`, `docker-compose.yml` (proyecto `util_bbdd`: `postgres_db` en el 5432), `docker ps`, `docker inspect`
- `tests/integration/conftest.py`, `scripts/bench_bulk.py`, `docs/guides/benchmarks.md`, `.github/workflows/` (sin servicios de BD)

## AI output summary
- **Diagnóstico** (con evidencias):
  - el banco nunca usó `postgres_db`: la URL del banco llega a `bench@bench` en PostgreSQL **17.11** (`util_bbdd_bench_postgres`, 55432), mientras `postgres_db` es PostgreSQL **18.3** (5432);
  - los 5 servidores del banco ya estaban en puertos no estándar;
  - el único contacto con `postgres_db` fue el choque de proyecto de compose del 2026-09-23, que recreó el contenedor con el volumen intacto; se resolvió entonces con `name: util_bbdd_bench`.
- **Acoplamientos reales encontrados**:
  1. `tests/integration/conftest.py`: 4 fixtures fijas a `localhost:5432` (`postgres/postgres`, `util_bbdd_test`), sin usos:
     - `postgresql_available` siempre devolvía `True`, porque `create_engine` no conecta;
     - `postgresql_engine` ejecutaba `DROP SCHEMA public CASCADE`.
  2. Puertos del banco publicados en `0.0.0.0`.
  3. Puertos fijos en el compose.
  4. SQL Server trabajaba en `master`.
  5. Sin plantilla versionada de URLs.
- **Implementado**:
  - **A**: eliminadas las 4 fixtures (se deja un comentario que remite a `UTIL_BBDD_TEST_POSTGRESQL_URL`).
  - **B/C**: `ports: "127.0.0.1:${UTIL_BBDD_BENCH_<MOTOR>_PORT:-<actual>}:<interno>"` en los 5 servicios; cabecera del compose con la tabla de puertos y variables.
  - **D**: base `bench` en SQL Server. **Desviación del plan**: se crea en el healthcheck (`IF DB_ID('bench') IS NULL CREATE DATABASE bench; SELECT 1`, idempotente) en lugar de un servicio de un solo uso `mssql-init`. Así no hay contenedor extra y `up --wait` sigue terminando solo cuando la base existe.
  - **E**: `scripts/bench_env.example.sh` y `scripts/bench_env.example.ps1`:
    - definen `UTIL_BBDD_BENCH_*` y `UTIL_BBDD_TEST_*` con `127.0.0.1` y los puertos configurables;
    - la contraseña se toma de `UTIL_BBDD_BENCH_PASSWORD` y se aborta si falta.
  - **F**: `bench_bulk.warn_if_standard_port` registra un WARNING si la URL usa el puerto estándar del motor o no indica ninguno. Solo avisa.
  - **G**: `docs/guides/benchmarks.md`:
    - tabla de contenedores, puertos, variables y bases;
    - URLs con `127.0.0.1` y `bench` en SQL Server;
    - uso de las plantillas;
    - nota sobre `localhost`/`::1`.
  - **H**: contenedores recreados con `docker compose -f docker-compose.bench.yml up -d --wait`.
- **Verificación**:
  - `docker compose … config`: proyecto `util_bbdd_bench`, 5 puertos con `host_ip: 127.0.0.1`;
  - `docker ps` tras recrear: `127.0.0.1:55432/53306/53307/51433/51521`, los 5 healthy;
  - `postgres_db`: **mismo Id y `StartedAt`** antes y después (`2026-09-23T22:37:09Z`);
  - conexión por las URLs de la plantilla: PostgreSQL, MySQL y MariaDB → `bench`; SQL Server → `db_name() = bench`; Oracle → `FREEPDB1`;
  - plantilla `.ps1` con `UTIL_BBDD_BENCH_MSSQL_PORT=61433` → URL con 61433; ambas plantillas fallan con mensaje si falta la contraseña;
  - integración 6 motores con la plantilla: 162 passed / 24 skipped;
  - `bench_bulk.py --sizes 1000 --repeat 1`: 30 mediciones, 0 errores, 6 motores, sin contraseña en `environment.json`;
  - `ruff check src tests scripts` y `mypy` limpios;
  - suite 4735 passed / 164 skipped (+8 casos del aviso de puerto);
  - `mkdocs build --strict`: los mismos 13 avisos previos.

## Segundo cambio: `docker-compose.yml`
Prompt:
```
el docker-compose.yml  usar el contenedor postgres nuevo y dejar de usar el mio
```
- **Antes**: `docker-compose.yml` definía `postgres_db` (postgres:latest, `0.0.0.0:5432`, `admin/admin123`, base `testdb`, volumen `postgres_data`, `restart: always`), proyecto `util_bbdd`. Ningún código ni test lo usaba; solo `.ai/runtime.md` (desfasado) y textos del banco lo citaban.
- **Ahora**: `docker-compose.yml` = `name: util_bbdd_bench` + `include: [docker-compose.bench.yml]`. Desde la raíz, `docker compose ...` gestiona los contenedores del banco, y `docker compose up -d --wait postgres` levanta el PostgreSQL 17 propio (127.0.0.1:55432, `bench`).
  - Se descartó definir el servicio aparte con `extends`: mismo `container_name` en otro proyecto, o servicios huérfanos en el mismo.
- **Credenciales**: `admin/admin123` desaparecen del repositorio; la contraseña sale de `UTIL_BBDD_BENCH_PASSWORD` (falla con mensaje si falta).
- **Tu contenedor**: `postgres_db` y su volumen `util_bbdd_postgres_data` siguen en el proyecto `util_bbdd`, que ya no se usa desde el repositorio. No se paran ni se borran.
- **Verificación**:
  - `docker compose config` (sin `-f`): proyecto `util_bbdd_bench`, los 5 servicios con los mismos `container_name` y puertos `127.0.0.1`;
  - `docker compose --dry-run up -d`: `Running`, sin crear, recrear ni huérfanos;
  - `docker compose up -d --wait postgres` y `docker compose ps` listan solo los contenedores del banco;
  - Id y `StartedAt` de los 6 contenedores (incluido `postgres_db`) idénticos antes y después.
- **Docs**: cabecera de `docker-compose.bench.yml`, `docs/guides/benchmarks.md`, `.ai/runtime.md` y CHANGELOG.

## Fuera de alcance (observación)
- Si quieres retirar tu contenedor: `docker stop postgres_db`, y `docker rm postgres_db` para borrarlo. Con `restart: always` vuelve a arrancar con Docker hasta que lo pares o lo borres. El volumen `util_bbdd_postgres_data` solo se borra con `docker volume rm util_bbdd_postgres_data` (pierde los datos). No se ha hecho nada de esto.
- `tests/integration/test_update_auto_increment_mariadb.py` necesita una cuenta con `CREATE DATABASE`. Con la URL del banco (usuario `bench`) da 3 errores, como antes; no cambia con esta sesión.

## Directrices para Futuras IAs
- **[banco]**: cargar las URLs con `scripts/bench_env.example.*`; no escribir URLs a mano con `localhost` ni con puertos estándar.
- **[banco]**: no reutilizar un servidor local existente: los contenedores del proyecto `util_bbdd_bench` son los únicos destinos del banco y de los tests de integración.
- **[tests]**: ninguna fixture debe ejecutar DDL destructivo (`DROP SCHEMA`, `DROP DATABASE`) contra una URL fija. Solo contra una URL explícita de pruebas y en objetos propios.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
