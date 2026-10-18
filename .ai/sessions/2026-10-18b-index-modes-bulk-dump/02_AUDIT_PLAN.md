# AUDIT_PLAN — Modos de índices y FK checks en `bulk` y `dump`

**Veredicto: `GO_CONDICIONAL`** (condiciones en § 5; decisiones confirmadas por el usuario el 2026-10-18, § 6).

## 1. Riesgos funcionales

| # | Riesgo | Evidencia | Corrección |
|---|---|---|---|
| F1 | Lanzar error con InnoDB en `bulk_session` atómica rompe a quien ya pasa `disable_indexes=True`: la sesión es atómica por defecto y hoy se omite con `info` | `bulk/_execution/maintenance.py:230` | Mantener la omisión actual en sesión atómica; DROP/ADD InnoDB solo con `atomic=False`, `dump` o paralelo |
| F2 | `"all"` contradice `RejectOptions(on_error="isolate")`, que aparta filas con PK duplicada | `bulk/crud.py:205` | `"all"` + `isolate` → `ValueError` al entrar |
| F3 | `"all"` sobre destino con datos: duplicados contra filas existentes solo se ven al reconstruir | `DumpConfig.truncate_target` | `dump`: `"all"` exige `truncate_target=True`; `bulk`: aviso si la tabla no está vacía (`EXISTS`) |
| F4 | Reintentos de partición con commits periódicos pueden duplicar filas sin que lo detecte un índice único | `bulk/options.py:174` (`max_retries=0` por defecto) | Verificar antes de G5; si aplica, `"all"` + `max_retries>0` sin sesión atómica → incompatible |
| F5 | Oracle: las UNIQUE ya las desactiva la ruta de constraints; `"all"` las tocaría dos veces | `dump/_constraints.py:385`, `bulk/_execution/maintenance.py:383` | Una sola dueña: con `"all"` la estrategia de índices; la de constraints las salta |
| F6 | Con `FOREIGN_KEY_CHECKS=0` no se ejecutan `ON DELETE/UPDATE CASCADE` | — | Advertencia en docstring + aviso al primer DELETE/UPDATE dentro del bloque en MySQL |
| F7 | `disable_indexes=True` pasa a ejecutar DDL en PostgreSQL y Oracle (antes no-op) | docstring de `maintenance_scope` | CHANGELOG; sin permisos, comportamiento tolerante (aviso + `failed`) |

## 2. Riesgos técnicos

| # | Riesgo | Corrección / condición |
|---|---|---|
| T1 | `"all"` en PostgreSQL bloquea en exclusiva las tablas hijas (DROP/ADD de FK entrantes); choca con su carga en `dump`/paralelo | Retirada de FK una vez, antes de la fase 4 (junto a `ConstraintManager`) o antes del pool |
| T2 | `WITH CHECK CHECK CONSTRAINT` en SQL Server recorre la hija entera | Medir en G0; alternativa sin validar (no *trusted*) |
| T3 | DDL de MySQL desde `information_schema.STATISTICS` frágil (prefijos, funcionales, FULLTEXT, SPATIAL, invisibles, comentarios, DESC) | G6 solo BTREE de columnas simples; test de ida y vuelta comparando `SHOW CREATE TABLE` |
| T4 | Savepoints sobre la conexión de `SessionScope` con la cadencia de commit | Test de integración PostgreSQL/SQL Server con un DDL que falla a propósito |
| T5 | Anidamiento en `ParallelBulkLoader`: índices deben envolver a constraints | Test de secuencia de DDL |
| T6 | Caché de metadatos obsoleta tras DROP de PK/FK | Invalidar (`metadata/source.py:168`) tras desactivar y restaurar |
| T7 | Alcance amplio (8 grupos, 4 motores × 3 modos) | Dos entregas (§ 4) |
| T8 | LSP/ISP: sin Protocol afectado (`BulkInserter` ya no existe; `test_protocol_conformance` no cubre `maintenance_scope`); `bulk` es solo sync | Test de identidad del reexport de `IndexActionResult` |
| T9 | Capas: sin imports nuevos entre paquetes | Ejecutar `scripts/gen_arquitectura_capas.py` |

## 3. Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| S1 | Ejecución de DDL del catálogo (`pg_get_indexdef`, `pg_get_constraintdef`, `DBMS_METADATA`) | Fuente = motor destino; sin concatenar; DDL propio siempre con `quote_identifier` |
| S2 | `"all"` requiere ALTER también en tablas hijas; fallo a medias deja estado parcial | Comprobar permisos sobre destino e hijas antes de cualquier DDL (todo o nada) |
| S3 | Fichero de copia de DDL | Fuera de la primera entrega (§ 4.3) |
| S4 | DDL en log WARNING | Aceptable: estructura, no datos |

## 4. Simplificaciones

1. G0 primero y como entrega independiente.
2. Dos entregas: 3.2.0 (G1–G4, `"secondary"`, G5b, G7) y 3.3.0 (G5, G6, solo combinaciones justificadas por G0).
3. Sin `index_ddl_backup` en la primera entrega (DDL ya en resultado y log).
4. SQLite solo como apoyo de tests.
5. `unique_checks=0` solo se mide; se implementa si gana claramente y no se solapa con DROP/ADD.
6. `validate_fks_after` generaliza el SQL de PostgreSQL existente.

## 5. Condiciones para IMPLEMENT

1. F1: InnoDB en sesión atómica mantiene la omisión actual.
2. F2/F3: incompatibilidades de `"all"` validadas al entrar.
3. F4: verificar reintentos × commits periódicos antes de G5.
4. F5: una sola dueña de las UNIQUE en Oracle.
5. T4/T6: savepoints e invalidación de caché con tests de integración.
6. Orden: G0 → 3.2.0 → 3.3.0 condicionada a G0.

## 6. Decisiones confirmadas (usuario, 2026-10-18)

| # | Decisión | Valor |
|---|---|---|
| D1 | `"all"` exige `disable_constraints=True` | Sí (`ValueError` si no) |
| D2 | Fallo al reconstruir un único en `"all"` | `IndexRebuildError` con diagnóstico de duplicados |
| D3 | Umbral de ganancia en G0 | ≥ 5 % del total a 3,5M filas con ≥ 2 índices |
| D4 | SQLite | Solo apoyo de tests, no motor soportado en la documentación de rendimiento |
| D5 | `validate_fks_after` por defecto | `False` hasta tener el coste medido en G0 |
| D6 | InnoDB en sesión atómica | Resuelta por F1: omisión + aviso, sin error |
| D7 | Nombre del parámetro | Se reutilizan `disable_indexes` (`bulk`) y `manage_indexes` (`dump`) con `bool \| IndexMode` |
