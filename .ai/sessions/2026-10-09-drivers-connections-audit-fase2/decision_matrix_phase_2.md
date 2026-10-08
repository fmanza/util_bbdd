# FASE 2B — Diseño y matriz de decisiones (drivers-connections-audit)

Fecha: 2026-10-09 · Base: v0.35.8 · Hallazgos de partida: `audit_phase_2a.md` (D1–D12)

## 1. Opción A frente a Opción B, con la duplicidad medida

La skill (v1.0.3 § 2.1) estimaba A en 35–45 h y B en 15–20 h. Recalculado sobre lo medido:

| Bloque de la Opción A | Premisa de la skill | Realidad en v0.35.8 | Veredicto |
|---|---|---|---|
| `connection/_pool/base_pool.py` (pool genérico) | ~500 LoC, 60 % duplicado | pools sync 32 % de media; solo `__del__` + `close_connection` (134 LoC) superan el 50 % | No compensa: un mixin de cierre cubre lo duplicado |
| `connection/_base/config.py` | configs repetidas | 13 dataclasses con validaciones propias; los helpers (`_require_str`, `_to_int`…) ya están compartidos | Solo compensa una tabla de claves aceptadas derivada de las dataclasses |
| `connection/<motor>/{connection,pool}.py` (renombrar) | estructura más clara | 91 ficheros de tests importan `util_bbdd.connection.<motor>.*`; ningún beneficio funcional | Rechazado: rompe imports sin ganancia |
| `metadata/_base/executor.py` | no hay abstracción | ya existen `CatalogExecutor`, `AsyncCatalogExecutor` y `CatalogDialect` en `metadata/contracts.py:66-114` (ADR-003) | Premisa refutada |
| `metadata/_charset/` (paquete) | charset genérico | 2 módulos (`_charset_detection.py` 309 LoC, `_adaptive_executor.py` 221 LoC), solo MariaDB/MySQL | Mover no aporta; se mantiene |

**Recomendación: Opción B acotada** (sin mover ficheros ni romper imports), en 6 bloques independientes:

| Bloque | Contenido | Hallazgos | Esfuerzo (impl + tests) | Rompe API |
|---|---|---|---|---|
| B1 Validación única | `*Config` como fuente de claves y defaults; builder reducido a requeridos y alias; async por la misma validación | D2, D3, D4 (parte) | 6–8 h + 4 h | comportamiento async (ver Q2) |
| B2 TLS MariaDB | `ssl_*` en `MariaDBConnectionConfig`, JSON, sync, pool y aiomysql | D1 | 3–4 h + 2 h + banco | no (aditivo) |
| B3 Pools | mixin de cierre sync, `close_timeout` en `*PoolConfig`, política única del Engine | D4, D5, D6 (doc) | 4–6 h + 3 h | conexiones del Engine sync (ver Q5) |
| B4 aiomysql | una función de mapeo para conexión y pool de MariaDB y MySQL | D10 | 2–3 h + 1 h | no |
| B5 Factories | helpers comunes de URL/test query/sanitizado en un módulo compartido | duplicidad 79–92 % | 2 h + 1 h | no |
| B6 Limpieza | borrar `_manager_lifecycle_async.py` y `_translate_sql`; exportar configs MySQL | D7, D8, D11 | 1 h + 0,5 h | no (privado) |
| **Total B** | | | **18–24 h + 11,5 h tests** | |

La Opción A completa costaría lo mismo que B más ~15–20 h de mover y reimportar, para ahorrar los mismos ~200 LoC.

## 2. Decisión: estrategia de charset (solo MariaDB/MySQL)

Corrección de premisa: el enum de la skill (`DETECT/UTF8MB4/NATIVE/CUSTOM`) mezcla dos cosas distintas:

1. **Charset de la sesión** (`charset` / `SET NAMES`). MariaDB Connector/Python 1.1.14 solo admite utf8mb4 (sesión
   2026-10-08d); solo PyMySQL y aiomysql lo negocian. No hay nada que elegir en sync MariaDB.
2. **Estrategia de lectura del catálogo** (`native` / `convert` / `failfast`), que es lo que ya hace
   `select_strategy` según el diagnóstico. Aquí sí hay decisión.

| Opción | Descripción | A favor | En contra | Esfuerzo |
|---|---|---|---|---|
| CS-0 Status quo | diagnóstico `auto` interno, sin configuración | cero riesgo | no se puede forzar `convert` ni desactivar el diagnóstico (8 consultas) | 0 |
| **CS-1 (recomendada)** | parámetro `catalog_charset_mode: auto \| native \| convert` solo en mariadb/mysql; `native` omite el diagnóstico | reutiliza `select_strategy(mode)`; resuelve D9 y la mitad de M5 | un parámetro nuevo en config, JSON y docs | 3–4 h + 2 h |
| CS-2 | CS-1 + aplicarlo también en `SqlAlchemyCatalogExecutor` (bulk/dump/comparar con Engine) | paridad entre los dos caminos | el camino Engine no tiene diagnóstico; añadirlo cambia el número de consultas de ADR-003/ADR-004 (tests de caracterización) | +4–6 h |
| CS-3 | enum de la skill para todos los motores | — | sin evidencia del problema fuera de MariaDB/MySQL (FASE 1); PostgreSQL, Oracle thin, SQL Server y SQLite negocian UTF-8 solos | rechazada |

C7 (MariaDB 11.x): **sin evidencia** en el código ni en los tests. La matriz de versiones de la skill (§ 1.5) no está
verificada contra el banco: pendiente de comprobar `SELECT VERSION()` del contenedor `util_bbdd_bench_mariadb` antes de
fijar la política por versión.

## 3. Decisión: consolidación de la validación de `conn_params`

Estado: tres capas (`builder.py`, `_drivers/validator.py` + JSON, `*Config.from_params`) ya **aceptan las mismas
claves** (test `test_json_whitelist_covers_every_config_field`), pero divergen en defaults (D3), en claves sin campo
(`close_timeout`, `schema`) y en que el manager async no pasa por ninguna (D2).

| Opción | Fuente de verdad | A favor | En contra |
|---|---|---|---|
| V-0 | status quo + llamar a `prepare_and_validate` desde el async | mínimo cambio | sigue habiendo tres sitios con defaults |
| **V-1 (recomendada)** | `*Config` (campos + defaults); lista blanca = campos de config + pool + extras declarados (`close_timeout`, `schema`); builder solo valida requeridos y alias; JSON documental verificado por test (claves **y** defaults) | una sola definición; el JSON no puede volver a desincronizarse | toca builder, params y JSON; tests de builder que fijan defaults |
| V-2 | JSON como fuente; configs generadas o leídas de él | un único fichero | las reglas (regex de charset/schema, rangos, enums) no caben en el JSON; más código dinámico |

## 4. Decisión: pools

| Tema | Opciones | Recomendación |
|---|---|---|
| Cierre duplicado | (a) base `PoolConnection` genérica; (b) mixin `__del__`/`close_connection` en `connection/close.py` | (b): cubre lo que supera el 50 % de similitud |
| `close_timeout` | (a) seguir leyéndolo en 13 sitios; (b) campo de `*PoolConfig` | (b) |
| Política del Engine | (a) sync y async como hoy; (b) ambos leen `pool_size/max_overflow/pool_timeout/pool_recycle` de `conn_params` con los mismos defaults | (b), con `pool_recycle` 3600 como los nativos |
| Doble pool (manager + Engine) | (a) documentar; (b) Engine con `NullPool` si el manager ya tiene pool; (c) `creator` que pida conexiones al pool nativo | **decisión del usuario** (Q5) |
| `pool_size` por motor | (a) documentar la tabla D6; (b) unificar a "máximo" con mínimo perezoso (PostgreSQL `min_size=1`, SQL Server sin pre-crear) | (a) ahora; (b) cambia comportamiento (Q6) |

## 5. Preguntas para FASE 3 (requieren tu decisión)

1. **Q1 — Alcance**: ¿apruebas la Opción B acotada (B1–B6) y descartar la Opción A? ¿Algún bloque fuera?
2. **Q2 — Validación async (BC1)**: hoy el async acepta claves desconocidas. ¿Pasa a lanzar `ValidationError` ya
   (0.36.0) o primero `FutureWarning` durante una versión?
3. **Q3 — Defaults del builder en async (BC2)**: aplicar `schema="public"` (PostgreSQL) y `"dbo"` (SQL Server) también al
   async y a `ConnectionFactory` directo cambia el `search_path` de quien no lo indicaba. ¿Se unifica o se quitan esos
   defaults del builder?
4. **Q4 — Charset**: ¿CS-1 (parámetro solo en el camino manager) o CS-2 (también Engine, con impacto en los tests de
   caracterización de consultas)? ¿Nombre `catalog_charset_mode`?
5. **Q5 — Doble pool**: ¿documentar, `NullPool` en el Engine cuando el manager tiene pool, o reutilizar el pool nativo?
6. **Q6 — `pool_size`**: ¿se mantiene la semántica distinta por motor (solo documentarla) o se unifica (cambia cuántas
   conexiones abren PostgreSQL y SQL Server al iniciar)?
7. **Q7 — TLS MariaDB**: ¿entra en esta serie (bloque B2, aditivo) aunque sea funcionalidad nueva y no refactor? Si
   entra, iría por `/new-feature` o `/hotfix`, no por `/refactor`.
8. **Q8 — Versión**: con BC1–BC3 la serie es 0.36.0. ¿Aceptado, o se separan los bloques sin cambio de
   comportamiento (B4–B6) en 0.35.x?
9. **Q9 — C7**: ¿se verifica la versión real de MariaDB del banco y se declara la matriz de soporte (10.6/10.11/11.x),
   o C7 se cierra como "sin evidencia de diferencias"?

## 6. Decisiones de FASE 3 (resueltas 2026-10-09)

El usuario aceptó las recomendaciones («usar decisiones recomendadas»). Donde la matriz no fijaba una, se toma la de
menor riesgo, coherente con `risk_assessment_phase_2c.md`.

| Pregunta | Decisión | Consecuencia para FASE 4 |
|---|---|---|
| Q1 Alcance | **Opción B acotada (B1–B6)**; Opción A descartada | sin mover ficheros ni romper imports de `connection/<motor>/` |
| Q2 Validación async | **`ValidationError` directo** en 0.36.0 (decisión del usuario, sustituye a la recomendación de deprecación) | BC1 como ruptura con guía de migración en CHANGELOG; test de paridad sync/async |
| Q3 Defaults de `schema` | **Unificar en `*Config`**: el default pasa del builder a la config (PostgreSQL `public`; SQL Server `dbo` y HSQLDB `PUBLIC` como campos) y vale en sync, async y `ConnectionFactory` | coherente con V-1; BC2 como migración directa con nota en CHANGELOG |
| Q4 Charset | **CS-1**: `catalog_charset_mode: auto \| native \| convert`, solo mariadb/mysql y solo camino manager (sync y async); default `auto` | sin tocar el número de consultas de ADR-003/ADR-004; CS-2 queda como deuda |
| Q5 Doble pool | **Documentar** + política única del Engine (B3: `pool_*` desde `conn_params`, `pool_recycle` 3600) | `NullPool` / reutilizar pool nativo quedan fuera (cambian rendimiento de bulk/dump) |
| Q6 `pool_size` | **Documentar** la tabla D6; sin cambiar semántica | — |
| Q7 TLS MariaDB | **Entra, por `/new-feature` separado**, tras verificar contra el banco que Connector/Python 1.1.14 y aiomysql aceptan `ssl_*` | no se mezcla con `/refactor` |
| Q8 Versión | **Partir**: B6, B5, B4 (sin cambio de comportamiento) en 0.35.x; B3, B1, CS y B2 en **0.36.0** | orden de `risk_assessment_phase_2c.md` § 4 |
| Q9 C7 | **Cerrada con evidencia**: el banco es `mariadb:11.4` (11.4.13) y `mysql:8.4`, y `tests/integration` (552 passed) corre contra ellos. Soporte declarado = versiones validadas en el banco; 10.x queda "sin validar" (no "soportado") | corregir la matriz § 1.5 de la skill (lista 10.4/10.5 como soportadas, ya EOL) |

### Veredicto de preparación (implementation readiness gate)

**GO_CONDICIONAL** para FASE 4. Condiciones:

1. Actualizar `SKILL.md` a v1.0.4 (premisas refutadas en FASE 2 y matriz MariaDB) antes de empezar.
2. Cada bloque que toque parámetros de driver (B1, B2, B3, B4, CS) se valida contra el banco antes de cerrarse.
3. Un commit y una versión por bloque o grupo, en el orden de Q8.

### Comandos de FASE 4

```text
/refactor        → B6, B5, B4 (0.35.x), luego B3 y B1 (0.36.0)
/new-feature     → CS (catalog_charset_mode) y B2 (TLS MariaDB)
```
