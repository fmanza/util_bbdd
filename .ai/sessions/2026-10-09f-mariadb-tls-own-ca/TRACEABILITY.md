# TRACEABILITY

## Session metadata
- id: 2026-10-09f-mariadb-tls-own-ca
- fecha: 2026-10-09
- rama: develop
- skill: hotfix (sin cambio de código: premisa refutada) + infraestructura de banco
- fase: P4 de `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md` (F3)

## Prompt issued
```text
/hotfix

Bug: P4 del plan de pendientes (F3 cerrado como límite del driver): MariaDB Connector/Python exige rutas absolutas en ssl_ca/ssl_cert/ssl_key (su documentación) y la librería las pasa tal como llegan, así que una ruta relativa puede fallar en sync; además validar con CA propia que con ssl_ca se verifican certificado y hostname en sync y async
Rutas: src/util_bbdd/connection/config.py (MariaDBConnectionConfig._tls_kwargs); infraestructura nueva: scripts/bench_tls_certs.py y docker-compose.bench-tls.yml (opcional, monta la CA en el MariaDB del banco)
Supuesto: Connector/C 3.4.7 comprueba el hostname con ssl_verify_cert (por verificar en el banco)
Prioridad: P3
Versión: 0.40.1. Recrear el MariaDB del banco (autorizado). Commit + versión al cerrar.
```
Decisiones del usuario: puerta P4.0 → «Cerrar como límite del driver»; hallazgo de hostname → «Probar en remoto».

## Context supplied
- `PLAN_AUDIT_PLAN.md` (P4); documentación de `mariadb.connect` (Connector/Python 1.1.14)

## AI output summary
- P4.0: Connector/Python 1.1.14 rechaza `ssl_verify_identity` y variantes (`TypeError`); solo `ssl_verify_cert`. F3 se cierra como límite del driver (decisión del usuario).
- Infraestructura: `scripts/bench_tls_certs.py` (CA + certificado de servidor con SAN solo `IP:127.0.0.1`, en `build/bench_tls/`, ignorado por git); `docker-compose.bench-tls.yml` (override opcional que monta la CA en MariaDB; el compose base no cambia). MariaDB del banco recreado con `--force-recreate -V`: datos borrados, contraseña ahora la común (memoria del proyecto actualizada).
- Matriz contra el banco antes de tocar código (`build/logs/hotfix_p4_bench_before.txt`): la **ruta relativa funciona** en sync y async → premisa de P4 refutada, **sin cambio de código** (sin versión 0.40.1). CA propia por `127.0.0.1` cifra y verifica; CA ajena rechazada; sin TLS sigue funcionando.
- Hallazgo: con CA propia y host `localhost` (no está en el SAN) el sync conectaba. Prueba no local (puerto publicado temporalmente en `127.0.0.2`, sin exponer a la red; retirado después): Connector/C rechaza con `CERT_E_CN_NO_MATCH` y aiomysql también (`build/logs/hotfix_p4_bench_hostname.txt`). Conclusión: exención de `localhost` del conector sync, no fallo; en remoto sí se comprueba el hostname.
- `tests/integration/test_mariadb_tls_own_ca.py` (7; se salta sin la CA): sync/async × directa/pool con CA propia, CA ajena rechazada, hostname fuera del certificado rechazado en async, sin TLS sigue conectando. `tests/integration` 559 passed, 10 skipped; `pytest` 5422 passed, 504 skipped; `zensical build --strict` OK.
- Docs: `connection_guide.md` (hostname, exención de `localhost`, rutas relativas), roadmap (F3 como límite del driver), ADR-005, `.ai/runtime.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Script | `scripts/bench_tls_certs.py` | nuevo |
| Compose | `docker-compose.bench-tls.yml` | nuevo |
| Tests | `tests/integration/test_mariadb_tls_own_ca.py` | nuevo |
| Docs | `docs/guides/connection_guide.md`, `docs/roadmap.md`, `docs/adr/ADR-005-conexiones-multimotor.md`, `.ai/runtime.md` | |

## Directrices para Futuras IAs
- **[MariaDB/TLS sync]**: Connector/C 3.4.7 verifica CA y hostname con `ssl_verify_cert`, pero **no comprueba el hostname si se conecta como `localhost`**; para probar la comprobación del hostname en el banco hay que usar una dirección no local (p. ej. publicar el puerto en `127.0.0.2` temporalmente).
- **[MariaDB/TLS rutas]**: aunque la documentación de Connector/Python pide rutas absolutas en `ssl_ca`/`ssl_cert`/`ssl_key`, las relativas al directorio de trabajo funcionan (1.1.14).
- **[banco/MariaDB]**: con `docker-compose.bench-tls.yml` el MariaDB del banco usa la CA de `build/bench_tls/`; recrearlo solo con el compose base vuelve al certificado autogenerado y borra los datos si se usa `-V`.
- **[proceso]**: verificar la premisa de un hotfix contra el driver real antes de cambiar código: aquí la documentación del driver era más estricta que su comportamiento.

## Veredicto final
Veredicto: CLOSED (F3 cerrado como límite del driver; sin cambio de código)
Pendientes al cierre:
- P5 (HSQLDB en red).
- Push de `develop` y tag `v0.40.0` pendientes.
