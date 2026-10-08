# FASE 2C — Evaluación de riesgos (drivers-connections-audit)

Fecha: 2026-10-09 · Plan evaluado: Opción B acotada (B1–B6) de `decision_matrix_phase_2.md`

## 1. Riesgos por motor

| Motor | Bloques que lo tocan | Riesgo | Por qué | Validación mínima |
|---|---|---|---|---|
| MariaDB | B1, B2, B3, B4, CS | **ALTO** | 4 bloques; historial de regresiones (M1 en v0.35.6 solo con tests unitarios); el conector rechaza parámetros con `TypeError` | banco real: sync, pool, async y Engine; `charset="latin1"`; TLS si B2 |
| MySQL | B1, B3, B4, CS | MEDIO | `build_aiomysql_connect_kwargs` pasa a ser compartido; TLS async falla con `ProactorEventLoop` en Windows | banco: sync, `QueuePool`, async con `SelectorEventLoop`, TLS |
| PostgreSQL | B1 (defaults `schema`), B3 | MEDIO | Q3 cambia `search_path`; pool abre `pool_size` conexiones al iniciar | banco: psycopg y asyncpg, `schema` explícito y omitido |
| SQL Server | B1 (`schema`), B3 | MEDIO | pool propio con lock (Q2 de FASE 1); dos drivers | banco: pymssql y pyodbc/aioodbc |
| Oracle | B1, B3 | BAJO | DSN ya centralizado; `close_timeout` en `__del__` con `is_shutdown` (`pool_connection_oracle.py:89-94`) | banco: TCP; tests de caracterización ADR-004 |
| SQLite | B1, B3 | BAJO | todo en memoria; es el motor de los tests unitarios | suite unitaria |
| HSQLDB | B1 | BAJO en código, **sin red** | no hay servidor en el banco (H1 sin validar) | solo unitarios; documentar |

## 2. Qué puede romperse

| Id | Cambio | Quién lo nota | Tipo | Mitigación |
|---|---|---|---|---|
| BC1 | async rechaza claves desconocidas | quien pasaba claves de más a `AsyncDatabaseManager` | comportamiento | `ValidationError` directo en 0.36.0 (Q2); mensaje con las claves válidas y guía de migración |
| BC2 | defaults del builder también en async/`ConnectionFactory` | PostgreSQL sin `schema`: pasa a `search_path=public` | comportamiento | decidir Q3; nota en CHANGELOG |
| BC3 | Engine sync respeta `pool_size`/`max_overflow` | bulk/dump con muchas conexiones | recursos | mismos defaults que hoy (5/10/30) salvo `pool_recycle` |
| BC4 | defaults de JSON pasan a ser los de `*Config` | quien lee `get_db_type_info()` (docs, CLI) | documental | test de coherencia de defaults |
| BC5 | borrar `_manager_lifecycle_async.py` y `_translate_sql` | nadie en `src/`; solo tests de `test_charset_detection.py` usan `_translate_sql` | privado | borrar los tests asociados |
| BC6 | `catalog_charset_mode=native` | quien lo active en un servidor MIXED/latin1 | opt-in | default `auto`; docs |
| — | Opción A (descartada) | 91 ficheros de tests + usuarios con imports de `connection.<motor>` | imports | no aplica si se aprueba B |

Dependencias externas: ningún consumidor de `bulk/` o `dump/` depende del pool nativo (reciben `Engine`); sí dependen
del número de consultas de metadatos (tests de caracterización de ADR-003/ADR-004), afectado solo por CS-2.

## 3. ¿Deprecación o migración directa?

- BC1: migración directa a `ValidationError` en 0.36.0 (decisión del usuario 2026-10-09). Es el único cambio que puede romper código que hoy funciona: CHANGELOG con sección de ruptura y ejemplo.
- BC2: migración directa con nota, si Q3 se resuelve hacia "unificar"; si se quitan los defaults del builder, también
  cambia el sync → deprecación.
- BC3–BC6: directa.

## 4. Estrategia de rollback

- Un commit por bloque (B1…B6, CS) y una versión patch/minor por commit o grupo, como en v0.35.5–v0.35.8: el rollback
  es `git revert` del bloque sin arrastrar a los demás.
- Sin migraciones de datos ni de esquema: ningún bloque persiste estado. El rollback no necesita pasos en BD.
- Orden que minimiza el radio de cada revert: B6 → B5 → B4 → B3 → B1 → CS → B2 (lo aditivo y lo privado primero; lo que
  cambia comportamiento al final, cada uno revertible por separado).
- Criterio de rollback: cualquier fallo del banco de integración (`tests/integration`, hoy 552 passed / 10 skipped) o
  de los tests de caracterización de consultas.

## 5. Riesgos del proceso

| Riesgo | Evidencia | Mitigación |
|---|---|---|
| Validar solo con unitarios | regresión M1 de v0.35.6 | cada bloque que toque parámetros de driver se valida contra el banco antes de cerrar |
| Premisas de la skill sin verificar | 10 premisas refutadas en FASE 1; 4 más en esta fase (pool genérico, `metadata/_base`, enum de charset, matriz MariaDB) | actualizar `SKILL.md` a v1.0.4 antes de FASE 4 |
| Mocks que fijan comportamiento falso | 3 tests retirados en v0.35.7 (driver que "aceptaba" `charset`) | test-first contra el driver real cuando exista |
| HSQLDB sin entorno | H1 | marcar como no validado en CHANGELOG |
| Trabajo en paralelo del usuario | memoria del proyecto | añadir solo rutas propias; nunca `git add -A` |
