# TRACEABILITY

## Session metadata
- id: 2026-10-09-feature-mariadb-tls
- fecha: 2026-10-09
- rama: develop
- skill: new_feature
- fase: FASE 4 de `drivers-connections-audit`, bloque B2 (TLS MariaDB): PLAN + AUDIT_PLAN (GO_CONDICIONAL) + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/new-feature

Objeto: drivers-connections-audit FASE 4 — bloque B2 (TLS en MariaDB)
Funcionalidad: parámetros TLS en conn_params de MariaDB (ssl, ssl_ca, ssl_cert, ssl_key, ssl_verify_cert) aplicados en conexión sync, pool sync (mariadb.ConnectionPool), conexión y pool async (aiomysql vía connection/_aiomysql.py) y, por el creator, en los Engine
Contexto: D1 de audit_phase_2a.md; decision_matrix § 6 (Q7); sondeo del banco 2026-10-09: servidor MariaDB 11.4 con TLS (have_ssl=YES) pero la librería conecta sin cifrar; Connector/Python 1.1.14 (Connector/C 3.4.7) acepta ssl, ssl_ca, ssl_cert, ssl_key, ssl_verify_cert, tls_version en connect y ConnectionPool; con ssl=True y sin CA verifica por huella (zero-config de 11.4); ssl_ca sin ssl_verify_cert no exige la CA (conecta con una CA ajena); ssl_ca + ssl_verify_cert=True sí la exige; aiomysql cifra con ssl=SSLContext
Fuera de alcance: cambiar el default (TLS sigue desactivado si no se pide), otros motores
Versión: 0.39.0. Validar contra el banco. Commit + versión al cerrar.
```
Antes: push de `develop` y tag `v0.38.0` («si»). Condición del AUDIT_PLAN aceptada («si»): en async, `ssl=True` sin `ssl_ca` cifra sin verificar y avisa con WARNING.

## Context supplied
- `.github/prompts/new_feature.prompt.md`
- Sondeos del banco (`b2_probe.py`, `b2_probe2.py`, scratchpad)

## AI output summary
- Verificación previa contra el banco: servidor con TLS, librería sin cifrar (`Ssl_cipher` vacío) en sync y async; Connector/Python acepta `ssl`, `ssl_ca`, `ssl_cert`, `ssl_key`, `ssl_verify_cert`, `tls_version` en `connect` y `ConnectionPool`; `ssl_verify_cert` solo no cifra; `ssl_ca` con CA ajena conecta salvo `ssl_verify_cert=True`.
- Test-first: `tests/unit/connection/mariadb/test_mariadb_tls.py` (12; 9 fallaban).
- `MariaDBConnectionConfig`: campos TLS y `_tls_kwargs` (`ssl=True` si hay cualquier opción; `ssl_verify_cert=True` por defecto con `ssl_ca`); sin opciones, `to_driver_kwargs` idéntico. `_aiomysql.build_aiomysql_connect_kwargs`: `ssl=True` → `SSLContext` sin ficheros; WARNING si `CERT_NONE`. JSON: 5 claves en `mariadb`.
- `ruff`/`mypy` OK; `pytest` 5395 passed, 497 skipped (`build/logs/feature_mariadb_tls_suite.txt`); `tests/integration` 552 passed, 10 skipped; `zensical build --strict` OK.
- Banco (`build/logs/feature_mariadb_tls_bench*.txt`), `Ssl_cipher` en conexión nativa y Engine, sync y async, directa y pool: sin TLS → sin cifrar; `ssl=True` → `TLS_AES_256_GCM_SHA384` en los 6 caminos; `ssl_ca` ajena → falla en los 4 caminos nativos; `ssl_ca` ajena + `ssl_verify_cert=False` → cifrado.
- Docs: `docs/guides/connection_guide.md` § 6. Versión 0.39.0. Cierra la FASE 4.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/config.py`, `connection/_aiomysql.py`, `data/database_types.json` | modificados |
| Tests | `tests/unit/connection/mariadb/test_mariadb_tls.py` | nuevo |
| Docs | `docs/guides/connection_guide.md` § 6, `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` | |
| VERSION | ficheros de versión | 0.39.0 |

## Directrices para Futuras IAs
- **[MariaDB/TLS]**: con Connector/Python 1.1.14 (Connector/C 3.4.7): `ssl_verify_cert` solo no cifra (siempre pasar `ssl=True`); `ssl_ca` sin `ssl_verify_cert=True` no exige la CA; `ssl=True` sin CA verifica por huella contra MariaDB 11.4+. La traducción está en `MariaDBConnectionConfig._tls_kwargs`.
- **[aiomysql/TLS]**: sin `ssl_ca`, el TLS async no verifica el certificado (WARNING); un fallo de verificación llega como `(2003, "Can't connect to MySQL server ...")`, menos explícito que el del conector sync.
- **[banco/TLS]**: comprobar el cifrado con `SHOW SESSION STATUS LIKE 'Ssl_cipher'` (vacío = sin TLS). En modo directo del manager sync no llamar a `close_connection` sobre la conexión única (el `close()` del manager falla al cerrarla de nuevo).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- FASE 4 cerrada (B6, B5, B4, B3, B1, CS, B2). Siguiente: FASE 5 (`/audit-code` post-implementación) y FASE 6 (`/version-closure`).
- Push y tag `v0.39.0` pendientes.
