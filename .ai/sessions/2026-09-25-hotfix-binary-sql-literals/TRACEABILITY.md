# TRACEABILITY

## Session metadata
- id: 2026-09-25-hotfix-binary-sql-literals
- fecha: 2026-09-25
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
- "Adelante con el hotfix" → `/hotfix` P-30 + C-1 (`.ai/audit/audit_report_bulk_sql_serialization_20260925.md`)

## Context supplied
- Informe de auditoría de serialización SQL (C-1, P-30); commit e1adcc2 (P-31/P-32/P-33).
- Contenedores del banco en ejecución (`util_bbdd_bench_*`); sin `UTIL_BBDD_TEST_*_URL` en el entorno.

## AI output summary
- RCA con el arnés `repro/binrepro.py`: SQL generado ejecutado dentro de cada contenedor (`docker exec`, cliente nativo, credenciales del propio contenedor). El fallo es más amplio que en la auditoría: también los bytes UTF-8 (`'abc'`) fallan en SQLite, SQL Server y Oracle (en Oracle, corrupción silenciosa).
- Arreglo en `sql_helpers.py`: literal hexadecimal por dialecto en la plantilla y en el camino por fila (SET/VALUES y WHERE).
- Tests: 2 unitarios (8 drivers; fallan con el código anterior) y 1 de integración (falla en SQLite con el código anterior). Referencias `_ref_*` actualizadas.
- Antes → después (9 valores): SQLite 1→9, PostgreSQL 7→9, MySQL 9→9, MariaDB 9→9, SQL Server 3→9, Oracle 1→9.
- ruff y mypy en verde; pytest completo 4913 passed; tras el ajuste de tipos, 633 passed en bulk, helpers e integración.
- CHANGELOG (*Fixed*); estado del roadmap actualizado.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| HOTFIX (PLAN → VERSION) | `.ai/sessions/2026-09-25-hotfix-binary-sql-literals/HOTFIX.md` | emitido |
| Arnés y salidas antes/después | `.ai/sessions/2026-09-25-hotfix-binary-sql-literals/repro/` | emitido |
| Código | `src/util_bbdd/bulk/_support/sql_helpers.py` | completado |
| Tests | `tests/unit/bulk/test_generate_sql_template.py`, `tests/integration/test_bulk_engines.py` | completado |
| CHANGELOG | `CHANGELOG.md` (*Unreleased → Fixed*) | actualizado |

## Directrices para Futuras IAs
- **[bulk/sql_helpers]**: el `literal_processor` de `LargeBinary` en SQLAlchemy 2.0.50 escribe los bytes como cadena entre comillas. No es un literal binario válido en SQLite, SQL Server ni Oracle (en Oracle se reinterpreta como hex sin error). Usar `_BINARY_LITERAL_FORMATS`.
- **[tests/integración]**: sin `UTIL_BBDD_TEST_*_URL`, `repro/binrepro.py` valida el SQL en los contenedores del banco con `docker exec` y las variables de entorno de cada contenedor. En SQL Server, separar las sentencias con `GO`: sin él, un error de compilación anula todo el lote. Usar `-y 0` (incompatible con `-h`) para no recortar columnas.
- **[Oracle]**: un literal de cadena admite como máximo 4000 caracteres (2000 bytes en hex) y `sqlplus` corta las líneas de más de 4999. Los BLOB mayores no se pueden escribir como literal SQL simple.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit.
- Ejecutar `tests/integration/test_bulk_engines.py -k binary` con `scripts/bench_env.example.*` cargado, para cubrir los servidores con el test versionado.
