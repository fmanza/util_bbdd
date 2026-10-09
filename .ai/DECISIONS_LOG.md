# DECISIONS LOG — util_bbdd

Registro cronológico de decisiones arquitectónicas, técnicas y de proceso.  
Formato: **Decisión → Alternativas descartadas → Razón → Impacto actual**.  
Fuente: TRACEABILITYs de sesiones + docs de análisis.

---

## 2026-03 — Arquitectura 3 niveles Foundation/Services/Domain

**Decisión**: Dividir el módulo en 3 niveles jerárquicos:
- Nivel 1 `_core/`: capabilities, contratos base, tipos internos.
- Nivel 2 `connection/`, `metadata/`, `query/`: servicios reutilizables.
- Nivel 3 `bulk/`, `dump/`, `comparar/`, `migrate/`: lógica de dominio.

**Alternativas descartadas**: Módulo plano sin jerarquía; herencia profunda.  
**Razón**: SOLID — dependencias solo fluyen de Nivel 3 → Nivel 2 → Nivel 1. Previene ciclos.  
**Impacto actual**: Regla de oro en `architecture.instructions.md`: "un módulo de Nivel N solo importa de Nivel N y N-1". Los 3 niveles son el vocabulario compartido entre todas las IAs.

---

## 2026-04-10 — Logging centralizado en 36 clases (v0.6.8)

**Decisión**: Añadir `self.logger: logging.Logger` tipado en 36 clases de todos los niveles. Logger nombrado `__name__` (jerarquía de paquete). Sin logger global.

**Alternativas descartadas**: `print()` + `logging.basicConfig()`; logger a nivel módulo global.  
**Razón**: Trazabilidad granular por clase; silenciable por namespace sin afectar otras clases.  
**Impacto actual**: Cada clase loguea en INFO/WARNING/DEBUG con contexto propio. Patrón obligatorio para clases nuevas.

---

## 2026-04-13 — tech-debt comparar/: gaps multimotor (Fases 0-3)

**Decisión**: Resolver gaps D6+D3, D2+D5, D1+D4, M1+M2 en `comparar/` para soporte multimotor completo. 4 fases ejecutadas en una sesión.

**Razón**: La comparación de esquemas entre motores distintos (Oracle vs MariaDB) fallaba silenciosamente por incompatibilidades de tipo.  
**Impacto actual**: `SchemaComparator` soporta comparación cross-engine. Ver también: decisión 2026-06-01 (case-insensitive columns).

---

## 2026-04-14/16 — SchemaDiff reporters (HTML/Excel/Word/Markdown/SQL)

**Decisión**: Implementar 5 formatos de reporte en `comparar/reporters/` usando clases independientes con `@staticmethod` exclusivo (no herencia). Cada reporter tiene su clase; `SchemaDiffReporter` como facade.

**Alternativas descartadas**: Un único reporter configurable; herencia profunda; funciones sueltas.  
**Razón**: Política OOP: herencia para contratos de tipo (protocols); @staticmethod para utilidades sin estado. Documentado en `CLAUDE.md` y `python.instructions.md`.  
**Impacto actual**: Reporters HTML (Jinja2+Mermaid), Excel (openpyxl), Word (docx), Markdown, SQL. Complejidad cognitiva ≤ 4 en todos.

---

## 2026-04-16 — Excepciones tipadas en comparar/: ComparerError

**Decisión**: Reemplazar `ValueError`/`Exception` genéricas en `comparar/` por `ComparerError` + 3 subclases: `SchemaDiffValidationError`, `MetadataIntrospectionError`, `DiffReportGenerationError`.

**Alternativas descartadas**: Mantener excepciones genéricas; una única excepción de módulo.  
**Razón**: Permite captura diferenciada por capa. Jerarquía documentada en `docs/api/exceptions.md`.  
**Impacto actual**: Patrón replicado en `dump/` (`DumpError`/`DumpConstraintError`/`DumpReportError`).

---

## 2026-04-21 — Eliminación completa de legacy (31 funciones deprecated)

**Decisión**: Eliminar 31 funciones wrapper deprecated de 5 módulos `managers/`. 6 consumidores migrados a OOP directo. Propiedad `DatabaseQueries.queries` eliminada.

**Alternativas descartadas**: Mantener wrappers con deprecation warning.  
**Razón**: Deuda técnica acumulada; wrappers sin tests propios ocultan bugs en la interfaz real.  
**Impacto actual**: API pública de managers es 100% OOP. No hay wrappers de compatibilidad hacia atrás.

---

## 2026-05-18 — Pipeline 3 capas para módulo migrate/

**Decisión**: Arquitectura `extractor → transformer → emitter` para cada flujo DDL. Cada motor tiene sus propias implementaciones. `MigrationPlanner` orquesta.

**Alternativas descartadas**: Conversión directa SQL→SQL; un único transformer genérico.  
**Razón**: Separación de responsabilidades: extractor lee metadatos reales (INFORMATION_SCHEMA/syscat), transformer aplica reglas semánticas, emitter genera DDL dialect-específico.  
**Impacto actual**: 12 flujos validados (4 fuentes × 3 destinos). Añadir un nuevo motor = implementar las 3 clases para ese motor.

---

## 2026-05-19 — `metadata/*/tables.py` como punto canónico del SQL de introspección (sustituida el 2026-10-04 por ADR-003)

**Decisión**: Todo SQL de introspección (fetch tablas, vistas, rutinas, índices) vive exclusivamente en `metadata/<motor>/tables.py`. Prohibido duplicar en `migrate/`, `comparar/` u otras capas.

**Alternativas descartadas**: SQL inline en cada módulo consumidor; `migrate/sql/` como paquete separado (creado y eliminado en misma semana).  
**Razón**: Un único punto de verdad para SQL de metadatos evita divergencias entre la comparación y la migración del mismo motor. Regla REGLA #1 en `architecture.instructions.md`.  
**Impacto actual**: `migrate/sql/` fue eliminado (sesión `2026-05-22-metadata-sql-canonical`). Toda función `fetch_*_sql()` vive en `metadata/`.

---

## 2026-05-22 — "Directrices para Futuras IAs" formalizada en TRACEABILITY

**Decisión**: Toda TRACEABILITY.md de sesión debe incluir sección `## Directrices para Futuras IAs` con hechos verificables, patrones y contratos que una IA nueva no puede inferir del código.

**Razón**: IAs sucesivas perdían contexto de decisiones tomadas. Las directrices son persistencia de memoria entre sesiones.  
**Impacto actual**: Plantilla `TEMPLATE/TRACEABILITY.md` incluye el placeholder. REGLAS #1–#6 de metadata access documentadas como modelo.

---

## 2026-05-25 — dump/ y BulkInserter Protocol

**Decisión**: `dump/` no depende directamente de `BulkCrud` (Nivel 3 → Nivel 3 prohibido). Se introduce `BulkInserter` Protocol (`@runtime_checkable`) en `dump/_protocols.py`. `DumpConfig.bulk_audit_path` propagado al constructor.

**Alternativas descartadas**: Import directo de BulkCrud en DumpOrchestrator.  
**Razón**: Evitar dependencia circular entre módulos del mismo nivel. Protocol permite mock en tests.  
**Impacto actual**: `dump._process_table` tipado con `crud: BulkInserter`. `BulkInserter` re-exportado en `dump/__init__.py`.

---

## 2026-05-31 / 2026-06-01 — Palancas de rendimiento bulk/dump (v0.9.0 → v0.10.0)

**Decisiones de performance implementadas**:
1. `commit_every_n_chunks` (commit-as-you-go, reduce memoria).
2. `IndexManager.manage_indexes` — deshabilita índices secundarios no únicos durante carga masiva.
3. `bulk_session(atomic=True)` — transacción única por tabla (antes 1 por chunk).
4. `ParallelBulkLoader` — paralelización por tabla (niveles topológicos FK) y por rangos de PK.
5. `bulk_insert_from_chunks` — streaming de datos.
6. **v0.10.0**: `PostgresCopyStrategy` (psycopg3 COPY ~10×), `MySQLMultiRowInsertStrategy` (multi-fila parametrizado), `InsertStrategyResolver` reescrito.
7. **Dump sin SchemaComparator**: `DumpOrchestrator.run()` eliminó la llamada a `compare()` (cascada ~500 queries/100 tablas).

**Razón**: Perfiles de producción mostraron cuellos de botella en commit granular, índices y paso de comparación innecesario.  
**Impacto actual**: Tabla de estrategias INSERT en `docs/api/bulk-crud.md`. `collect_row_counts=False` para volcados de alto volumen.

---

## 2026-06-01 — MySQL/MariaDB variables auto-config en BulkCrud (PR #18)

**Decisión**: `BulkCrud.__init__` detecta `innodb_buffer_pool_size` y `max_allowed_packet` via `SHOW VARIABLES` (read-only) y loguea recomendaciones. No modifica la BD (sin `SET GLOBAL`).

**Alternativas descartadas**: SET GLOBAL automático (requiere SUPER privilege); documentación solamente.  
**Razón**: Variables por defecto (<128 MB buffer, 16 MB packet) causan error 2013 "Lost connection" en cargas masivas. La lectura es segura y transparente.  
**Impacto actual**: `MySQLVariableValidator` + `MySQLOptimalConfig` en `connection/mariadb/`. Logging INFO para estado, WARNING si debajo de mínimos. PR #18 OPEN.

---

## 2026-06-02 — Paralelismo safe: `_resolve_max_workers` acota a pool_size

**Decisión**: `ParallelBulkLoader._resolve_max_workers` = `min(requested, pool_size)`. Constraints DDL se deshabilitan UNA VEZ antes del pool (no per-worker) para MSSQL (SCH-M) y PostgreSQL (ACCESS EXCLUSIVE).

**Razón**: Workers > pool_size causa deadlock por agotamiento de conexiones. Per-worker DDL en MSSQL/PG falla por bloqueos exclusivos.  
**Impacto actual**: `ValueError` explícito si `commit_every_n_chunks` y `max_retries > 0` simultáneos (incompatibles semánticamente).

---

## 2026-06-03 — Estándar documental v2: 5 arquetipos × 5 secciones

**Decisión**: Toda documentación sigue 5 arquetipos (Funcional, Técnico/API, Guía, Ejemplo, ADR) × 5 secciones fijas. Nav MkDocs tiene exactamente 7 secciones top-level (no añadir más).

**Alternativas descartadas**: Documentación libre sin estructura; 4 arquetipos × 4 secciones (v1).  
**Razón**: Facilita búsqueda por IA y por humanos. Enlace bidireccional api↔examples es obligatorio.  
**Impacto actual**: Prompts actualizados: `functional_doc.prompt.md`, `technical_doc.prompt.md`, `guide_doc.prompt.md`, `example_doc.prompt.md`, `architecture_doc.prompt.md` (nuevo ADR). `mkdocstrings` apunta a nombre real de clase (no alias).

---

## 2026-06-04 — Collation por defecto MariaDB: utf8mb4_uca1400_ai_ci

**Decisión**: `DEFAULT_COLLATION` en `migrate/charset.py` cambiado de `utf8mb4_unicode_ci` → `utf8mb4_uca1400_ai_ci`.

**Razón**: UCA1400 es el estándar moderno de MariaDB ≥ 10.10 (mejor ordenación Unicode, case-insensitive, accent-insensitive).  
**Impacto actual**: Destinos MariaDB < 10.10 o MySQL DEBEN pasar `collation=` explícito. Tests existentes con `utf8mb4_unicode_ci` como entrada son válidos (sigue siendo collation válida).

---

## 2026-06-04 — Documentación: Zenical vs MkDocs vs Sphinx

**Decisión**: **Zenical** como generador estático de destino. MkDocs Material 9.5 se mantiene provisionalmente mientras Zenical no esté en crates.io.

**Alternativas descartadas**:
- **Sphinx**: requiere ~70% reescritura de docs, complejidad alta de configuración, no apto para multi-lenguaje.
- **Seguir con MkDocs**: sin ventaja técnica a largo plazo.

**Razón**: Zenical = +80% performance (Rust), Material Design 3, Mermaid nativo, 100% compat. con Markdown existente, 0 cambios de contenido.  
**Impacto actual**: Rama `migrate/zenical-pure` lista (5 commits, `zensical.toml` 634L). Bloqueado por publicación en crates.io. Rollback: `git checkout develop && mkdocs build`.

---

## 2026-06-05 — Bootstrap IA cross-project: modelo PULL

**Decisión**: Para trasladar config IA a otro proyecto, invocar desde el DESTINO con el origen como plantilla de solo lectura (modelo PULL). Clasificar activos en 4 capas: A (verbatim+revisar comandos), B (copiar+reescribir dominio), C (regenerar), D (excluir).

**Alternativas descartadas**: Modelo PUSH (desde el origen) — arrastra supuestos Python/util_bbdd al destino.  
**Razón**: El destino puede tener otro lenguaje y arquitectura. El prompt necesita el código real del destino en contexto.  
**Impacto actual**: Prompt `.github/prompts/bootstrap_ai_config.prompt.md`. Soporta 5 plataformas: Claude, Gemini, Copilot, Cursor, Codex.

---

## 2026-09-21 — Regla #6: niveles canónicos, imports acíclicos dentro de un nivel y guarda automática

**Decisión**: (1) Los niveles canónicos son los de `.ai/architecture.md`, los mismos que `LEVEL` en `scripts/gen_arquitectura_capas.py`; `models.py` y `async_utils.py` son Foundation (no importan nada de la librería). (2) Un paquete importa de su nivel o de niveles inferiores, nunca de uno superior; dentro de un nivel el import es válido solo si va en un único sentido (sin ciclos). Los imports perezosos cuentan como dependencia. (3) `tests/unit/test_architecture_import_rules.py` hace cumplir la ausencia de ciclos entre paquetes, de imports ascendentes y que todo paquete nuevo tenga nivel. Excepción acotada: `metadata/` → `managers/` bajo `TYPE_CHECKING` (marca 1 de `docs/architecture.md`).

**Alternativas descartadas**:
- **Prohibir todo import horizontal** (la frase inicial de la Regla #6 y «Level 2 → Level 1 únicamente»): el código tiene 11 pares de paquetes con import en un solo sentido dentro del mismo nivel (p. ej. `factory` → `connection`, `metadata` → `results`, `executors` → `query`); prohibirlos con solo 3 niveles obligaría a reestructurar código; con capas finas no hace falta tocarlo (ver la decisión de 2026-09-22).
- **Los niveles de `architecture.instructions.md`** (`connection/`, `factory/`, `results/` en Level 1; `managers/` en Level 2): README, onboarding, `.ai/architecture.md`, la decisión de 2026-03 y el script coinciden en la otra asignación, y D3 de `.ai/architecture.md` justifica `managers/` en Level 3.
- **import-linter**: añade una dependencia y un fichero de contratos para lo que `gen_arquitectura_capas.py` ya mide.

**Razón**: Convivían dos asignaciones de niveles y una regla cuya frase inicial prohibía lo que su propia lista de reglas daba por supuesto («dentro del mismo nivel») y el código practica. Sin guarda automática, `connection/` ⇄ `factory/` cerró un ciclo latente (`update_auto_increment.py`, reescrito el mismo día para recibir el `Engine` por parámetro); un import perezoso no lo habría arreglado, porque la dependencia sigue.
**Impacto actual**: Sustituye la parte «Nivel 3 → Nivel 3 prohibido» de la decisión 2026-05-25: `dump/` importa `BulkCrud` en `dump/orchestrator.py` (l. 38) y lo instancia (l. 154 y 672). `architecture.instructions.md`, `.ai/architecture.md`, `README.md` y `docs/guides/onboarding_dev.md` enuncian la misma regla. `UpdateAutoIncrement` (`connection/mariadb/`) recibe el `Engine` por parámetro y descubre las columnas `AUTO_INCREMENT` con el Inspector de SQLAlchemy: excepción a la Regla #2 documentada en el propio módulo, como `comparar/`.

---

## 2026-09-22 — Regla #6: capas estrictas por función

**Decisión**: La Regla #6 pasa de «3 niveles + imports acíclicos dentro de un nivel» a capas estrictas: cada nivel se divide en capas numeradas y un paquete importa solo de paquetes de capas de número menor; los de una misma capa son independientes. La tabla (7 capas asignadas por función, no por la profundidad que tenga hoy el grafo de imports) es `LAYER` en `scripts/gen_arquitectura_capas.py`; de ella se derivan `LEVEL`, las notas de banda de la figura y la tabla generada de `docs/architecture.md`. `.ai/architecture.md` la documenta a mano. La guarda `tests/unit/test_architecture_import_rules.py` exige imports hacia capas inferiores, una tabla coherente y capa para todo paquete.

**Alternativas descartadas**:
- **3 niveles + acíclico dentro del nivel** (decisión de 2026-09-21): dejaba pasar inversiones entre hermanos que no cierran ciclo (p. ej. `results → connection` o `connection → query`). Se supera, no se descarta por coste: el código ya cumplía las capas.
- **Prohibir lo horizontal con solo 3 niveles**: obligaría a reestructurar 11 pares de paquetes; con capas finas no hace falta tocar código.
- **Derivar las capas de la profundidad del grafo**: fija como norma un accidente (`comparar/` caería en la capa 2 solo porque apenas importa nada) y prohibiría imports futuros legítimos.

**Razón**: Tres niveles no expresan la estructura real sin imports horizontales, y «acíclico dentro del nivel» solo detecta ciclos, no inversiones semánticas entre hermanos. Las capas estrictas cierran ambas cosas sin cambiar el comportamiento en ejecución.
**Impacto actual**: 0 violaciones y 0 excepciones. `metadata/` depende de `MetadataCachePort` (`metadata/adapters/_adapter_protocol.py`), `analysis/` de `RelationshipGraphSource` (`analysis/contracts.py`) y `doc/` de `DocumentationSourcePort` (`doc/application/ports.py`): Protocols definidos por el consumidor, con parámetros posicionales porque mypy no compara los nombres al comprobar un Protocol. `tests/unit/test_protocol_conformance.py` verifica con mypy (tipos, aridad, miembros) que `CacheService`, `SyncDatabaseManager` y el adaptador de `doc` los cumplen; el paso `mypy` de CI (`.github/workflows/tests.yml`) lo ejecuta junto a `src`. `SyncMetadataProvider` no se reutilizó: cubre solo 9 lecturas y usa parámetros con nombre. Con estas capas `analysis` baja a la capa 6 y `doc` a la 7 (7 capas).

---

## 2026-09-27 — Verificación de condiciones del motor: una vez por Engine, en `connection/`

**Decisión**: `EngineReadinessAdvisor.report_once(engine)` verifica cada `Engine` una sola vez por proceso. El registro es un `weakref.WeakSet` de clase protegido por un `threading.Lock`; el engine se registra antes de verificarlo, así que los hilos concurrentes no repiten la verificación ni esperan. La clave es el objeto `Engine`, no la URL. La lectura de URL y pool (`pool.size()`, `pool._max_overflow`, `pool._timeout`, driver de SQL Server) vive en `connection/performance_advisor.py` (`_conn_params_from_engine`); `BulkCrud.__init__` solo llama a `report_once`.

**Alternativas descartadas**:
- **Una verificación por `BulkCrud`** (v0.18.1): `ParallelBulkLoader` y `dump` crean una `BulkCrud` por partición o hilo, así que había N informes idénticos y N conexiones extra que competían con los workers.
- **Parámetro `check_engine_readiness` en `BulkCrud`** (patrón `warn_if_audit_disabled`): obliga a cada consumidor a desactivarlo y no cubre a quien cree varias `BulkCrud` por su cuenta.
- **Clave por URL**: dos engines a la misma URL pueden tener pool distinto (`pool_size`, `max_overflow`).
- **Marca en el propio `Engine`** (atributo añadido): escribe en un objeto de SQLAlchemy; el `WeakSet` no lo retiene y no lo modifica.

**Razón**: El resultado depende del engine, no de la instancia que lo usa. Es estado mutable a nivel de clase (excepción a SHARED § OOP), justificado porque el requisito «una vez» es de proceso; con referencias débiles no mantiene vivo ningún engine.
**Impacto actual**: `bulk/` ya no conoce atributos privados del pool. `engine.dispose()` no provoca una nueva verificación; `report()` explícito no está limitado. Sesión `2026-09-27c-readiness-once-per-engine`.

---

## 2026-10-04 — Metadatos por lotes en `metadata/` (ADR-003); sustituye a la decisión de 2026-05-19

**Decisión**: `metadata/` es el único lugar con SQL de catálogo y reflexión `Inspector`. Se lee por lotes:
`CatalogSource.snapshot()` (o `get_schema_metadata()` de los managers) devuelve un `SchemaSnapshot` de modelos neutros
con una consulta por tipo de objeto y schema; el SQL de cada motor vive en `metadata/<motor>/catalog.py`
(`CatalogDialect`). Los `get_*` de los managers devuelven esos modelos. Fuera: registry de catálogo
(`data/sql_queries.json` sin consultas), adaptadores por motor, `MetadataManager`, cachés paralelas y
`metadata.redshift`/`metadata.snowflake`. Detalle y excepciones en `docs/adr/ADR-003-metadata-centralizada.md`.

**Alternativas descartadas**: paquete nuevo `catalog/`; solo `Inspector`; derivar tipos SQLAlchemy del snapshot;
conservar el registry añadiendo consultas por schema (ver ADR-003 § 4).
**Razón**: el patrón tabla a tabla costaba hasta 365 s de catálogo con 500 tablas (Oracle) frente a 0,27 s por tipo de
objeto, y había cuatro caminos de lectura para el mismo dato.
**Impacto actual**: guardas `tests/unit/test_architecture_metadata_rules.py` (pendientes en cero) y
`tests/unit/metadata/test_query_counts.py` (sin `xfail`). La `MetadataCachePort` de la decisión de capas ya no existe.
Sesión `2026-10-03-metadata-centralization`.

---

## 2026-10-09 — Conexiones multimotor: validación única, pool de los Engine, charset del catálogo y TLS en MariaDB (ADR-005)

**Decisión**: Opción B acotada de `drivers-connections-audit` (consolidar sin mover ficheros). Las `*Config` de
`connection/config.py` son la fuente única de claves y defaults de `conn_params` (`ConnectionParamsManager.allowed_keys`);
`AsyncDatabaseManager` valida como el sync (`ValidationError`, sin inyectar defaults del camino sync). Los Engine sync y
async siguen una política de pool común (`factory/_pool_policy.py`). `catalog_charset_mode` (`auto`/`native`/`convert`)
solo en MariaDB/MySQL. TLS en MariaDB con `ssl`, `ssl_ca`, `ssl_cert`, `ssl_key`, `ssl_verify_cert`.

**Alternativas descartadas**: Opción A (reorganizar por capas: rompía imports de 91 ficheros de tests por el mismo
ahorro); JSON como fuente única; estrategia de charset para todos los motores; exigir `ssl_ca` en TLS async.
**Razón**: la FASE 1 encontró que los dos caminos de conexión (nativo y Engine) y los dos managers aplicaban la
configuración de forma distinta; la duplicidad medida (pools 32 %) no justificaba una reorganización.
**Impacto actual**: v0.35.9–v0.39.1 (cambios incompatibles en v0.36.0 y v0.37.0, documentados en el CHANGELOG).
Detalle en `docs/adr/ADR-005-conexiones-multimotor.md`; deuda en `docs/roadmap.md`. Sesiones `2026-10-09-*`.

---

## 2026-10-09 — Documentación (`doc/` + `analysis/`): sin paquetes por motor, diagramas por lotes y API mínima (v0.41.0)

**Decisión**: Mantener la arquitectura hexagonal de `doc/` y consolidar dentro de ella: inventario de almacenamiento
declarativo por motor (`doc/infrastructure/storage/engines.py`), un generador de grafos por documentación, renders de
Graphviz por lotes (`GraphvizRelationshipGraphExt.prefetch`, `dot -O`) y fachada pública reducida a
`DatabaseDocumentation` + `DocumentationResult`, con `DocumentationConfigError`/`DocumentationRenderError`.

**Alternativas descartadas**: paquetes `doc/motors/<motor>/` (el código por motor es el 8 % y ya estaba en `storage/`);
un proceso `dot` por grafo en un pool de hilos (escala 4,4× con 8 hilos, porque el coste es arrancar `dot`); mantener la
caché SVG entre Word y HTML (hacía que el .docx dependiera de los demás formatos pedidos).
**Razón**: auditoría `documentation-architecture-audit`: 26 hallazgos; el 89 % del HTML con diagramas era esperar a
`dot` en serie.
**Impacto actual**: HTML con diagramas 12,6× más rápido (120 tablas: 75,7 s → 6,0 s); cobertura de `doc/`+`analysis/`
61 % → 81 %; ruptura de API documentada en el CHANGELOG 0.41.0. Sesión `2026-10-09k-doc-architecture-audit`.
