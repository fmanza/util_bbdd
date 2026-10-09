# FASE 5 — AUDIT_CODE post-IMPLEMENT (drivers-connections-audit)

Fecha: 2026-10-09 · Alcance: `git diff v0.35.8..v0.39.0 -- src/` (32 ficheros, +706/−627) · Modo: solo lectura

Validación: `pytest` 5395 passed, 497 skipped (`build/logs/drivers_audit_fase5_suite.txt`); `mypy` y `ruff` OK.
Cada bloque se validó además contra el banco (logs `build/logs/refactor_drivers_b*`, `feature_*`, `hotfix_*`).

## Cumplimiento de las decisiones de FASE 3

| Decisión | Bloque / versión | Cumple | Evidencia |
|---|---|---|---|
| Q1 Opción B acotada | B6–B1 | ✅ | sin mover ficheros; imports de `connection/<motor>/` intactos |
| Q2 `ValidationError` directo en async | B1 v0.37.0 | ✅ | `async_mgr.py:67-78`; `test_async_conn_params_validation.py` |
| Q3 `schema` en `*Config`, todos los caminos | B1 v0.37.0 | ✅ | `config.py`; `_metadata_context.py`; banco PostgreSQL async `search_path=public` |
| Q4 CS-1 `catalog_charset_mode` | CS v0.38.0 | ✅ | camino manager sync y async; Engine fuera |
| Q5 doble pool: documentar + política única | B3 v0.36.0 | ✅ | `factory/_pool_policy.py`; `connection_guide.md` § 7 |
| Q6 `pool_size`: documentar | B3 v0.36.0 | ✅ | `connection_guide.md` § 7 |
| Q7 TLS MariaDB por `/new-feature`, verificado contra el driver | B2 v0.39.0 | ✅ | sondeos previos; 16 casos en el banco |
| Q8 B6/B5/B4 en 0.35.x; el resto con bump | todos | ⚠️ desviación menor | B3, B1, CS y B2 salieron en 4 versiones minor (0.36–0.39) en vez de una 0.36.0: un bloque por versión, como pedía la condición de rollback |
| Q9 C7 cerrada (11.4 / 8.4) | SKILL v1.0.4 | ✅ | `SKILL.md` § 1.5 |

## Hallazgos

| Id | Prio. | Hallazgo | Evidencia | Estado |
|---|---|---|---|---|
| F1 | P3 | `AsyncDatabaseManager.database` se calcula de los `conn_params` **originales**, no de los validados: con el alias `filepath` (SQLite) queda `""` aunque la conexión funcione; afecta a `get_connection_info()["database"]` y al id de caché (`sqlite://:/`). El sync lo toma de los validados. | `async_mgr.py:79`; reproducido | confirmado |
| F2 | P3 | Sin test unitario de que `SyncDatabaseManager` pase `catalog_charset_mode` al ejecutor (solo el async y el banco). | `tests/unit/metadata/test_catalog_charset_mode.py` | confirmado |
| F3 | P3 | TLS MariaDB con `ssl_ca`: la verificación incluye el hostname (sync y async) y no hay `ssl_verify_identity` para desactivarlo sin desactivar la CA (MySQL sí lo tiene). Conectar por IP con un certificado sin SAN de IP falla. | `config.py::_tls_kwargs`, `build_ssl_context` | hipótesis (no probado con CA propia) |
| F4 | P3 | El WARNING de TLS async sin verificar se emite en cada conexión nueva que crea el `async_creator` del AsyncEngine (ruido). | `_aiomysql.py:85-86` | confirmado por lectura |
| F5 | P3 | Los `_build_*_connection_string` de las factories siguen divergiendo en casos límite; B5 lo dejó para B1, que no los redujo. Sin impacto en los 5 motores con `creator` (la URL solo elige dialecto). | `factory/*_engine_factory.py` | deuda abierta |

Sin hallazgos P0–P2. Sin regresiones detectadas.

## Contratos sync/async

- Validación de `conn_params`: misma lista blanca y mismos requeridos en sync y async (B1); el async no inyecta defaults (R1) ni comprueba drivers sync (R2), por diseño.
- Pools: `close_timeout` desde `*PoolConfig` en los 11 pools; `SyncPoolCloseMixin` solo sync.
- Engine: misma política de pool en sync y async (`engine_pool_kwargs`); asimetría previa documentada: `use_pool=False` → `NullPool` solo en async.
- TLS MariaDB: sync verifica sin CA (zero-config 11.4); async no (WARNING) — aceptado en FASE 4.

## Seguridad

- ✅ Async rechaza claves desconocidas y valida `schema`/`charset`/`catalog_charset_mode` antes de conectar.
- ✅ TLS sin degradación: si falla, falla la conexión; CA ajena rechazada en los 4 caminos nativos.
- ✅ Credenciales: escapado S1 y redacción SVC-01 centralizados en `factory/_url.py`; `password` con `repr=False`. Las rutas de certificados aparecen en `repr` de la config (no son secretos).

## Tipado

Sin `Any` nuevos en firmas públicas salvo los ya existentes en `conn_params: dict[str, Any]`. `mypy` limpio (332 ficheros).

## Tests

5279 → 5395 tests (+116). Cada bloque con tests test-first que fallaban antes del cambio; los cambios sin efecto funcional, con comparaciones antes/después (9.744 casos en B5, 54 llamadas en B4, 37 en el builder de B1).

## Veredicto

**APROBADO CON CONDICIONES**

Condiciones (no bloqueantes para FASE 6, pero a resolver o registrar):

1. F1: corregir con un `/hotfix` de una línea (`self.database` desde `self.conn_params`) o registrar como deuda.
2. F2: añadir el test del camino sync en el próximo cambio que toque `sync_mgr.metadata_source`.
3. F3–F5: registrar como deuda en el CHANGELOG/roadmap de FASE 6.
