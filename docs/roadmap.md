<!-- arquetipo: informativo-libre -->
# Roadmap de util_bbdd

Visión de versiones de la librería: qué se ha entregado, qué hay en curso y hacia dónde va.
El detalle exhaustivo de cada cambio vive en el
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) (formato
[Keep a Changelog](https://keepachangelog.com/) + [SemVer](https://semver.org/)); esta página
es la vista panorámica.

> **Versión vigente: v1.2.0.** API pública estable bajo SemVer: la raíz `util_bbdd` (13 puntos de entrada) y sus
> submódulos públicos solo cambian de forma incompatible en una versión MAJOR. Las series `0.x` eran pre-estables.

## En curso (`develop`)

Sin trabajo abierto tras v1.1.1. Lo que se
añada a `develop` antes del próximo tag aparecerá en el
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md).

### Limitaciones conocidas de los drivers

Solo quedan anotadas dos limitaciones, y ninguna se puede corregir desde la librería porque están
en el driver. Decisiones en [ADR-005](adr/ADR-005-conexiones-multimotor.md).

| Motor | Limitación | Qué hace la librería | Alternativa |
|---|---|---|---|
| MariaDB | MariaDB Connector/Python no tiene `ssl_verify_identity`: con `ssl_ca` verifica la CA **y** el hostname a la vez, sin forma de verificar solo la CA (comprobado el 2026-10-09 con CA propia). | Activa `ssl_verify_cert` cuando hay `ssl_ca`. | Conectar con un nombre o IP que figure en el certificado del servidor. Ver [TLS en MariaDB](guides/connection_guide.md#tls-en-mariadb-ssl-ssl_ca-ssl_cert-ssl_key-ssl_verify_cert-desde-v0390). |
| SQL Server | `trust_cert` no tiene efecto con pymssql: la validación del certificado depende de FreeTDS (`freetds.conf`), no de la conexión. | Desde v0.39.2 avisa una vez por servidor y proceso (WARNING en el logger). | `sql_server_driver="pyodbc"` (sync) o `aioodbc` (async), que envían `TrustServerCertificate`. Ver [TLS en SQL Server](guides/connection_guide.md#tls-en-sql-server-encryption-y-trust_cert). |

## Entregado

### Serie 0.11 – 1.0 — Auditorías, rendimiento con banco real y conexiones

| Versiones | Fechas | Hito |
|---|---|---|
| `v1.1.0` | 2026-10-10 | Rutas `str` además de `Path` en `bulk`, `ParallelBulkLoader` y `dump` (con `output_dir` como `str` el volcado perdía su resultado); **hotfix**: las consultas async de PostgreSQL (asyncpg) fallaban siempre, con SQL Server y pyodbc las filas llegaban anidadas y el pool async ignoraba `driver_name`; `BulkCrud` dividido por dentro (mantenimiento de tabla y aislamiento de rechazos en clases propias); guías de rendimiento y de migración revisadas. |
| `v1.0.0` | 2026-10-10 | **API pública estable**: alias de 0.x retirados de la raíz y `SyncDatabaseManager.close_connection()` retirado; documentación revisada para 1.0 (README reescrito, instalación desde el repositorio, drivers de PostgreSQL, extras reales). Cobertura de tests 91 %. Guía: [Migración a la API 1.0](guides/api_1_0_migration.md). |
| `v0.44.0` | 2026-10-10 | Las excepciones se presentan como `util_bbdd.exceptions` (trazas, `repr`, logs, pickle); los pickles antiguos se siguen cargando. |
| `v0.43.0` | 2026-10-10 | **API pública 1.0, fase 0.43.0**: raíz reducida a 13 puntos de entrada con carga perezosa (`import util_bbdd` ~1,1 s → ~0,3 s), módulo público `util_bbdd.exceptions`, 46 alias con `DeprecationWarning` hasta 1.0.0 y managers sync/async simétricos (`init`, `release_connection`). Guía: [Migración a la API 1.0](guides/api_1_0_migration.md). |
| `v0.41.0 – v0.42.1` | 2026-10-09 – 2026-10-10 | Auditoría de la arquitectura de `doc/` y `analysis/` (`documentation-architecture-audit`): diagramas Graphviz por lotes (HTML con diagramas, 12× más rápido), un generador de grafos por documentación, inventario de almacenamiento declarativo por motor y API de `util_bbdd.doc` reducida a `DatabaseDocumentation`/`DocumentationResult` con errores propios. |
| `v0.36.0 – v0.40.0` | 2026-10-09 | Auditoría de conexiones multimotor (`drivers-connections-audit`, [ADR-005](adr/ADR-005-conexiones-multimotor.md)): pools con política común, validación única de `conn_params` también en async, `catalog_charset_mode`, TLS en MariaDB, avisos una sola vez y URL de los Engine sync/async con la misma semántica. |
| `v0.31.0 – v0.35.x` | 2026-10-04 – 2026-10-07 | Extracción de metadatos centralizada en `metadata/` (ADR-003), soporte de Oracle 11g con resolución perezosa de versión (ADR-004) y detección de charset de MariaDB/MySQL. |
| `v0.29.0 – v0.30.0` | 2026-10-02 – 2026-10-03 | Módulo de auditoría común `util_bbdd.audit` (ADR-002) y comparación de esquemas fiable entre motores y schemas. |
| `v0.24.0 – v0.28.0` | 2026-10-01 – 2026-10-02 | Rendimiento de `bulk` por motor (lote por motor y operación, `prefetch_blocks`), aislamiento de filas erróneas (`on_error="isolate"`, rechazos) y corrección de la pérdida de datos de la 0.24.0 en SQL Server. |
| `v0.19.0 – v0.23.0` | 2026-09-29 – 2026-10-01 | MySQL como motor propio (PyMySQL/aiomysql); `migrate` reescribe vistas con sqlglot y convierte jerarquías `CONNECT BY` de Oracle. |
| `v0.11.0 – v0.18.0` | 2026-09-22 – 2026-09-27 | Auditoría completa del proyecto y auditorías de rendimiento de `bulk` y `dump` con banco de pruebas contra motores reales. |

### Serie 0.7 – 0.10 — Rendimiento y cobertura de tipos

| Versión | Fecha | Hito |
|---|---|---|
| `v0.10.0` | 2026-06-01 | Vías rápidas de INSERT por motor en `bulk` (PostgreSQL `COPY` vía psycopg3, MySQL/MariaDB multi-fila); `dump` reutiliza la resolución única por tabla; fix de la vía rápida de PostgreSQL que era código muerto con psycopg3. |
| `v0.9.0` | 2026-06-01 | Palancas de rendimiento opt-in en `dump` (cadencia de commit, gestión de índices, paralelización), todas desactivadas por defecto y combinables. |
| `v0.8.0` | 2026-04-21 | **Cobertura completa del sistema de tipos** (introspección de tipos avanzados en los 8 motores: composite/OBJECT/UDT, JSON schema, ARRAY); hotfix de finalización del pool en cierre del intérprete. Ver [plan original (entregado)](v0.8.0/PLAN_v0.8.0_TYPE_SYSTEM_IMPROVEMENTS.md). |
| `v0.7.0` | 2026-04-21 | Monitorización de rendimiento: timing automático de operaciones en bulk CRUD (columna `tiempo_seg` en la auditoría CSV); retirada de scripts legacy con credenciales hardcodeadas. |

### Serie 0.1 – 0.6 — Construcción y consolidación

| Versión | Hito |
|---|---|
| `v0.6.7` | Comparador de esquemas, imports canónicos desde la raíz, estructura actual como estándar. |
| `v0.6.0 – v0.6.6` | Grafos multinivel, HTML tabulado, contrato documental, capa de agentes Copilot, estabilización de managers y testing. |
| `v0.5.0` | Refactorización arquitectónica (jerarquía de 3 niveles). |
| `v0.4.0` | Consolidación de conexiones (primera estable). |
| `v0.3.0` | Soporte PostgreSQL mejorado. |
| `v0.2.0` | Documentación de BD automática mejorada. |
| `v0.1.0` | CRUD base + auditoría. |

## Futuro

- **`v1.0.0`** — ✅ entregado el 2026-10-10: API estable bajo SemVer y cobertura de tests ≥ 85 % (91 % medido con `pytest --cov` sin el banco).
- **`v1.2.0`** (propuesta) — `DumpResult` informa del fallo general al reactivar las constraints del destino (hoy solo
  queda en el log): campo nuevo `constraint_reactivation_error`, aditivo, + nueva hoja "Errores de Reactivación"
  en el informe Excel (opcional, solo si hay error).
- **`v2.0.0`** — retirar `PoolExhaustedError` y `DiffReportGenerationError`, públicas pero que la librería
  nunca lanza (documentadas como reservadas desde 1.1.1).
Ideas exploradas pero **fuera de alcance** por ahora (registradas en el
[plan de tipos v0.8.0](v0.8.0/PLAN_v0.8.0_TYPE_SYSTEM_IMPROVEMENTS.md)):
validación completa de JSON Schema, generación de dataclasses/TypeScript, motores no relacionales
(MongoDB, Cassandra) y notificaciones de cambio de esquema en tiempo real.

---

*Esta página es planificación (`informativo-libre`): orientativa y sujeta a cambios. La fuente de
verdad de lo ya publicado es el
[CHANGELOG](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md).*
