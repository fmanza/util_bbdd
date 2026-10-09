# VERIFY — `doc/` + `analysis/`

## Veredicto: **READY_FOR_RELEASE** (0.41.0, sin tag)

Todas las puertas de calidad de `01_PLAN.md` §6 se cumplen. Los hallazgos diferidos están fuera del alcance (`metadata/`,
`managers/`) o son de baja severidad y tienen el motivo anotado. El tag y el push quedan para `/version-closure`.

## 1. Puertas de calidad

| Puerta | Resultado | Evidencia |
|---|---|---|
| Sin regresión funcional | ✅ | Salida de texto de Word (paginado y sin paginar), Excel, HTML y Word+HTML **con diagramas** en 6 motores (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle, SQLite) comparada con la línea base previa al cambio (`build/logs/doc_baseline/before` → `after_all`): 13 escenarios idénticos, 7 con solo el orden de filas de almacenamiento de MariaDB/MySQL (no determinista también antes: la consulta no tiene `ORDER BY`) y 10 con exactamente B-01 y B-02 |
| Integración | ✅ | `tests/integration` contra el banco docker: 559 pasan + 5 de HSQLDB con `JAVA_HOME` (`build/logs/doc_audit_20261009_verify_integration*.txt`); 8 saltos de entorno (driver ODBC async de SQL Server, schema compartido de Oracle, «solo Oracle») |
| `ruff check` / `ruff format` | ✅ | 680 ficheros |
| `mypy src tests/unit/test_protocol_conformance.py` | ✅ | 331 ficheros sin errores |
| `pytest` | ✅ | 5 476 pasan, 507 saltados (integración sin URLs); `tests/unit`: 5 035 pasan |
| `zensical build --strict` | ✅ | «No issues found» (`build/logs/doc_audit_20261009_zensical.txt`) |
| `scripts/gen_arquitectura_capas.py` | ✅ | El dibujo coincide con los imports (331 ficheros); pie de figura actualizado |
| Rendimiento ≥ 2× con diagramas, sin empeorar sin ellos | ✅ | Tabla §2 |
| Cobertura no baja | ✅ | 61 % → **81 %** (`build/logs/doc_audit_20261009_coverage_after.txt`) |
| Seguridad sin regresión | ✅ | DOC-01/DOC-03/`SafeWorkbook` intactos; S-04 corregido; S-01 fijado con test (Graphviz real) |
| Trazabilidad | ✅ | Un commit por WP con IDs de hallazgo; CHANGELOG 0.41.0 con guía de migración |

## 2. Rendimiento (antes → después)

SQLite sintético de 120 tablas, todas las secciones, Graphviz 14.1.2, Windows, 32 núcleos (`scratchpad/doc_profile.py`,
cProfile + tracemalloc; JSON en `build/logs/doc_perf_{baseline,final}_*.json`).

| Escenario | Antes | Después | Mejora |
|---|---|---|---|
| HTML con diagramas | 75,7 s | 6,0 s | 12,6× |
| Word con diagramas | 68,3 s | 17,0 s | 4,0× |
| Word + HTML con diagramas | 127,8 s | 22,4 s | 5,7× |
| Excel | 3,1 s | 2,9 s | = |
| Word + Excel + HTML sin diagramas | 26,4 s | 16,8 s | 1,6× |
| Pico de memoria (Word + HTML) | 24,1 MB | 18,3 MB | −24 % |

Contribuciones: los lotes `dot -O` (P-01) explican casi toda la mejora con diagramas; el estilo de Word resuelto una vez
por documento (P-02), la de Word sin diagramas. Lo que queda en Word es python-docx (`add_row`, `cell.text`).

## 3. Completitud de hallazgos

| ID | Estado | Commit / motivo |
|---|---|---|
| A-01, B-01, B-03 | ✅ | `70f9e6df` |
| A-02, A-03, A-13, A-14, B-02, P-01, P-04, S-04 | ✅ | `53ff3c55` |
| A-04, A-05, A-09, A-10, A-12 | ✅ | `03783459` |
| A-06 | ✅ | `03783459` + `54ff56d6` |
| A-07, A-08 | ✅ | `54ff56d6` |
| A-11, P-02, P-03 | ✅ | `9d4d3429` |
| S-01 | ✅ (test) | `03783459`: un nombre de tabla con marcado llega escapado al SVG incrustado |
| S-03 | ✅ | `a4652f74` |
| T-01 (cobertura) | ✅ | `5a949e82`: Excel 18 % → 68 %, Word 37 % → 68 %, HTML 63 % → 84 % |
| S-02 | ⏸ Diferido (baja) | Decodificar entidades del DDL hasta 3 veces altera literales como `'&amp;lt;'`. Se mantiene porque no se sabe qué motor devuelve DDL con entidades: quitarlo sin un caso real podría romper la presentación. Requiere un dorado con ese literal |
| B-04 | ⏸ Fuera de alcance | `metadata/ddl.py`: DDL de tabla de HSQLDB con `LISTAGG` sin `WITHIN GROUP` (HSQLDB 2.7.4 lo rechaza). Ya fallaba antes. Siguiente paso: `/hotfix` en `metadata/` |
| — | ⏸ Fuera de alcance | 4 docstrings de `managers/`/`factory/` citan `DatabaseConnectionError`, que no existe |
| — | ⏸ Fuera de alcance | Orden no determinista de `ficheros_fisicos` de MySQL/MariaDB (`metadata.storage` sin `ORDER BY`) |
| `mypy --strict` | ⏸ Diferido | 93 → 81 errores (`type-arg` en firmas de los renderers, python-docx sin tipos); no es la puerta del repo |
| `matplotlib_graph` | ⏸ Diferido | 27 % de cobertura; sin uso desde `doc/` |
| Dorado Oracle de documentación | ⏸ Diferido | Saltado: el schema del usuario `bench` no está aislado |

## 4. Validación por motor

| Motor | Banco | Word | Excel | HTML | Diagramas | Almacenamiento |
|---|---|---|---|---|---|---|
| PostgreSQL 17 | docker | ✅ | ✅ | ✅ (+ dorado) | ✅ | ✅ |
| MySQL 8.4 | docker | ✅ | ✅ | ✅ (+ dorado) | ✅ | ✅ (orden de filas variable) |
| MariaDB 11.4 | docker | ✅ | ✅ | ✅ (+ dorado) | ✅ | ✅ (orden de filas variable) |
| SQL Server 2022 | docker | ✅ | ✅ | ✅ (+ dorado) | ✅ | ✅ sin aviso falso (B-01) |
| Oracle 23 Free | docker | ✅ | ✅ | ✅ | ✅ | ✅ idéntico a la línea base |
| SQLite | archivo | ✅ | ✅ | ✅ (+ dorado) | ✅ | ✅ |
| HSQLDB 2.7.4 | docker (servidor) | ✅ sin DDL | ✅ | ✅ | ✅ | ✅ aviso genérico (sin consultas) |
| Snowflake | — | N/A | N/A | N/A | N/A | N/A (no soportado por la librería) |

## 5. API

- `util_bbdd.doc.__all__ == ["DatabaseDocumentation", "DocumentationResult"]` (antes, además, los tres renderers).
- La fachada no expone estado interno (test `test_constructor_validates_without_reading_the_database`).
- Sin ciclos de import (`gen_arquitectura_capas.py`).
- `-615` sentencias en `doc/` + `analysis/` (4 504 → 3 889) con más funcionalidad cubierta.
