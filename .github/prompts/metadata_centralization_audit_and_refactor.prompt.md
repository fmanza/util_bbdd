# Prompt: Centralización y rendimiento de la extracción de metadatos

**Rol**: Arquitecto de software senior, experto en Python, SQLAlchemy 2.x y catálogos de sistema de los motores soportados
**Objetivo**: Llevar **toda** la extracción de metadatos (diccionario de datos) de `util_bbdd` a un único módulo y,
en el mismo diseño, reducir su coste (consultas, latencia, memoria)
**Alcance**: Todo `src/util_bbdd/`. Se **permite romper la API pública y los contratos** si el beneficio está justificado
y documentado. La auditoría no tiene límite de profundidad y se puede consultar internet.
**Agentes**: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor (AUDIT_CODE) →
Version Closer (VERSION). Apoyo: Performance Auditor (eje de rendimiento) y Explore (inventario).
**Invocación**: `/metadata-centralization` en Claude Code; en el resto de plataformas, aplica este prompt por nombre.

> **Este prompt es un plan, no un script**: cada fase acaba en un entregable que una persona revisa antes de seguir.
> IMPLEMENT no empieza sin aprobación explícita del AUDIT_PLAN.

---

## 📋 Inputs requeridos

- ✅ **Módulo destino**: `metadata/` ampliado (recomendado) | módulo nuevo (justificar en PLAN)
- ✅ **Ejes**: `centralización` | `rendimiento` | `ambos` (por defecto: `ambos`)
- ✅ **Motores**: `MariaDB` | `MySQL` | `Oracle` | `PostgreSQL` | `SQL Server` | `SQLite` | `Redshift` | `Snowflake` | `HSQLDB` | `todos`
- ✅ **Baseline de rendimiento**: ¿existe? Si no, se captura en PLAN (ver §5.3) antes de proponer cambios
- ✅ **Volumen de catálogo para medir**: nº de tablas por schema (p. ej. 50 / 500 / 5000) y nº de routines
- ✅ **Banco de pruebas**: contenedores de `docker-compose.bench.yml` (sí/no); sin banco, solo SQLite y estimación razonada
- ✅ **Fases autorizadas**: `PLAN + AUDIT_PLAN` | `hasta IMPLEMENT de un grupo` | `completo`

Si falta alguno, decláralo como supuesto explícito antes de continuar.

---

## 0. Reglas de este prompt

1. **No inventar.** Cada hallazgo lleva `ruta:línea` comprobada en el árbol actual. Lo que no se pueda verificar se
   marca `PENDIENTE DE VERIFICACIÓN`. Los ejemplos de tabla de este prompt son **formato**, no hallazgos.
2. **Revalidar el punto de partida** (§2): se midió el 2026-10-02 sobre v0.29.0 y puede haber cambiado.
3. **Capas (Regla #6) mandan**: ningún diseño puede exigir un import a capa igual o superior. Si un consumidor de capa
   ≤ 5 necesita metadatos, se mueve la lógica o se inyecta: no se fuerza el import. Verificar con
   `python scripts/gen_arquitectura_capas.py` y `tests/unit/test_architecture_import_rules.py`.
4. **Rendimiento con números**: ninguna mejora de rendimiento se declara sin medir antes y después (§5). Las
   estimaciones previas a la medición se etiquetan `ESTIMADO`.
5. **Fuentes externas citadas** (URL + fecha de consulta) y contrastadas con el comportamiento real del motor y de
   la versión de SQLAlchemy fijada en `pyproject.toml`.
6. **Artefactos de sesión** en `.ai/sessions/<AAAA-MM-DD>-metadata-centralization/` (plantilla en
   `.ai/sessions/TEMPLATE/`); nada en `/tmp` ni en la raíz del repo.

---

## 1. Definición de «extracción de metadatos»

**Dentro del alcance** (todo lo que lee el diccionario de datos, sea cual sea el mecanismo):

- **SQL de catálogo**: `INFORMATION_SCHEMA`, `pg_catalog`/`pg_*` y funciones `pg_get_*`, Oracle `ALL_*`/`USER_*`/`DBA_*`
  y `DBMS_METADATA`, SQL Server `sys.*` y `OBJECT_DEFINITION`/`OBJECTPROPERTY`, SQLite `sqlite_master`/`sqlite_schema`
  y `PRAGMA` de esquema (`table_info`, `index_list`, `foreign_key_list`…), Redshift `SVV_*`/`PG_TABLE_DEF`,
  Snowflake `INFORMATION_SCHEMA`/`SHOW …`, MariaDB/MySQL `SHOW CREATE|STATUS|INDEX|COLUMNS`.
- **Reflexión de SQLAlchemy**: `inspect(engine|conn)` y `Inspector.get_*` / `get_multi_*`. Es extracción de
  metadatos aunque no haya SQL escrito a mano.
- **Queries de catálogo en datos empaquetados**: `src/util_bbdd/data/sql_queries.json` (vía `query/registry.py`).
- **Objetos**: schemas, tablas, vistas, columnas, tipos, PK/FK/UK/CHECK, índices, routines y sus parámetros, triggers,
  secuencias e identidades, comentarios, charset/collation, particiones, almacenamiento/tablespaces, versión del
  motor, privilegios relevantes para la librería (p. ej. `CREATE TEMPORARY TABLES`).

**Fuera del alcance**:

- SELECT de filas de negocio; DDL/DML que la librería **emite** (es salida, no introspección).
- `PRAGMA` de **configuración de sesión** (`journal_mode`, `synchronous`…) en `connection/sqlite/_variables.py`:
  inventariar y decidir explícitamente en PLAN si se queda en `connection/`.
- Traducción de tipos a la IR de `migrate/` (consume metadatos, no los extrae).

---

## 2. Punto de partida verificado (2026-10-02, v0.29.0) — revalidar

Es la línea base para que la auditoría no empiece de cero; **no** es el inventario final.

**Fuentes de SQL de catálogo hoy (al menos tres)**:

| Fuente | Dónde | Observación |
|---|---|---|
| `fetch_*_sql()` por motor | `metadata/<motor>/{tables,constraints,indexes,routines,common}.py` | Recuento `^def fetch_.*_sql`: postgresql 21, oracle 20, sqlserver 13, mariadb 9, mysql 1; redshift, snowflake y sqlite 0 (SQL en constantes/PRAGMA) |
| Registry JSON | `data/sql_queries.json` + `query/registry.py` (capa 4), usado por `metadata/fetcher.py`, `managers/`, `executors/`, `validators/` | 7 motores, incluido **HSQLDB, que no tiene subpaquete en `metadata/`** |
| Reflexión SQLAlchemy | `dump/orchestrator.py`, `dump/_constraints.py`, `bulk/crud.py`, `comparar/comparator.py`, `comparar/_prefetch.py`, `connection/mariadb/update_auto_increment.py` | `connection/` es capa 4: **no puede** importar `metadata/` (capa 5) |

**SQL de catálogo escrito fuera de `metadata/`** (candidatos a violación de las Reglas #1/#3):

- `comparar/_routine_fetchers.py`: `all_procedures`, `DBMS_METADATA.GET_DDL` (una llamada por objeto),
  `sys.procedures`, `sys.objects`, `sys.sql_modules`, `SHOW CREATE {kind}`.
- `bulk/_support/pk_sync.py`: `pg_get_serial_sequence` inline (el resto ya importa de `metadata/`).
- `migrate/extractors/*.py`: importan `fetch_*_sql` de `metadata/` (cumplen la Regla #1), pero ejecutan y parsean
  filas ellos mismos (¿cumplen la Regla #2?).

**Consumidores que ya importan `fetch_*_sql` de `metadata/`** (buen síntoma, pero acoplan al detalle por motor):
`bulk/` (5 ficheros), `comparar/_prefetch.py`, `dump/{_constraints,_fk_graph,_indexes}.py`, `migrate/extractors/*`.

**Contrato actual**: `metadata/contracts.py` define `SyncMetadataProvider`/`AsyncMetadataProvider` **solo con métodos
por tabla** (`get_columns(tabla)`, `get_indices(tabla)`…). Un consumidor que recorre un schema hace N+1 consultas por
diseño.

**Precedente de rendimiento ya medido**: `comparar/_prefetch.py` usa `Inspector.get_multi_*` (SQLAlchemy 2.0) y una
consulta por schema para FKs de SQL Server; su docstring registra ≈ 2,1–2,4 s → 0,06–0,09 s por lado con 200 tablas
en PostgreSQL/Oracle. Es el patrón a generalizar, no a duplicar.

**Caché**: `metadata/cache.py` (`DatabaseMetadataCache`, `RelationshipMetadataCache`) indexa por tabla, sin lock ni
límite de tamaño visibles; los managers acceden a sus dicts internos (`db_cache._tables_cache`). Además existe
`managers/_metadata_cache.py`.

**Capas** (`LAYER` en `scripts/gen_arquitectura_capas.py`): `connection`/`query` = 4; `metadata` = 5;
`bulk`/`comparar`/`migrate`/`managers`/`analysis` = 6; `dump`/`doc` = 7.

**Reglas a revisar**: `.github/instructions/architecture.instructions.md` § «Reglas de acceso a metadatos» cita
`metadata/<motor>/tables.py` como único destino y `migrate/extractors/oracle.py` como patrón canónico: ambas
afirmaciones deben revalidarse con el diseño final.

---

## 3. Devuelve en este orden

### PLAN

#### 3.1 Inventario (Explore)

Recorre `src/util_bbdd/` completo (no solo los módulos citados en §2). Búsquedas mínimas, sin truncar con `head`:

```bash
# SQL de catálogo fuera de metadata/ (ajusta el patrón si aparecen catálogos nuevos)
grep -rniE "information_schema|\b(all|user|dba)_[a-z_]+\b|dbms_metadata|pg_catalog|\bpg_[a-z_]+\(|pg_(class|attribute|constraint|index|namespace|proc|depend|description)\b|sqlite_(master|schema)|pragma[ _]+(table_info|table_xinfo|index_list|index_info|foreign_key_list)|\bsys\.[a-z_]+|object_definition|svv_|pg_table_def|show (create|full|index|columns|tables|procedure|function)" \
  src/util_bbdd --include=*.py | grep -v "src/util_bbdd/metadata/"

# Reflexión SQLAlchemy en cualquier módulo
grep -rnE "\binspect\(|Inspector\b|get_multi_" src/util_bbdd --include=*.py

# Funciones de SQL de catálogo y quién las consume
grep -rnE "def (fetch|build)_.*_(sql|query)\b" src/util_bbdd --include=*.py
grep -rnE "from (util_bbdd|\.+)\.?metadata[.a-z_]* import" src/util_bbdd --include=*.py | grep -v "src/util_bbdd/metadata/"

# Registry JSON
python -c "import json;d=json.load(open('src/util_bbdd/data/sql_queries.json',encoding='utf-8'));[print(k,sorted(v)) for k,v in d.items()]"
```

Entregable `01_INVENTARIO.md`:

| ID | Ruta:línea | Mecanismo (`fetch_sql` / JSON / Inspector / inline) | Motor | Objeto | Consumidor(es) | Sync/Async | Capa |
|---|---|---|---|---|---|---|---|

Añade la **matriz motor × objeto** (✓ existe / ✗ no aplica al motor / ? por investigar), incluidos MySQL y HSQLDB, y
la lista de duplicados (misma información obtenida por dos caminos; p. ej. FKs vía `fetch_*_sql` y vía
`Inspector.get_foreign_keys`).

#### 3.2 Diagnóstico de rendimiento (Performance Auditor)

Para cada flujo que lee metadatos (`managers.get_*`, `doc`, `analysis`, `comparar`, `dump`, `migrate`, `bulk`):

- **Round trips**: consultas por operación en función del nº de tablas (O(1) por schema vs. O(N) por tabla).
  Medir contando con el evento `before_cursor_execute` de SQLAlchemy; no inferir.
- **Lecturas repetidas**: el mismo dato pedido varias veces en una misma operación (sin caché o con caché por tabla).
- **Coste por motor**: vistas de catálogo caras, columnas `LONG`/CLOB, `DBMS_METADATA` por objeto, filtros que no
  restringen por schema.
- **Memoria**: tamaño de la caché y de los resultados (definiciones de routines y vistas).
- **Concurrencia**: seguridad de la caché entre hilos (`bulk` usa hilos) y paridad sync/async.

Entregable `02_BASELINE_RENDIMIENTO.md` con tabla `flujo × motor × volumen → nº consultas, tiempo, pico de memoria`.

#### 3.3 Arquitectura objetivo

Entregable `03_DISENO.md` + borrador de **ADR-003** (`docs/adr/ADR-TEMPLATE.md`). Debe decidir y justificar, con la
alternativa descartada:

1. **Ubicación**: ampliar `metadata/` (capa 5) o crear otro paquete; qué pasa con `query/registry.py` +
   `sql_queries.json` (capa 4) y con la introspección de `connection/mariadb/update_auto_increment.py` (capa 4).
2. **Un único camino por objeto y motor**: SQL propio, Inspector o ambos con criterio explícito (p. ej. Inspector
   `get_multi_*` donde el dialect lo resuelve en una consulta; SQL propio donde SQLAlchemy no cubre el dato o va tabla
   a tabla).
3. **API orientada a lotes**: además de (o en lugar de) los métodos por tabla, una lectura por schema y tipo de objeto
   (p. ej. `get_schema_metadata(schema, kinds=…, tables=None)` que devuelve un snapshot inmutable). Los métodos por
   tabla, si se mantienen, leen del snapshot.
4. **Modelo de datos normalizado** e independiente del motor (dataclasses tipadas en lugar de `dict` por motor), con
   conversión a `Rows` solo en el borde público si hace falta.
5. **Caché**: ámbito (operación / sesión / manager), clave (`motor`, `database`, `schema`, `kind`), invalidación tras
   DDL propio (`migrate`, `dump` con constraints), límite de memoria, lock para hilos y equivalente async. Sin acceso a
   atributos privados desde fuera.
6. **Contrato**: `Protocol` sync y async en `metadata/contracts.py` (o donde fije el diseño) y adaptadores por motor;
   cómo se registra un motor nuevo sin tocar consumidores (OCP).
7. **Consumidores**: qué recibe cada módulo (provider inyectado) y qué deja de importar (`fetch_*_sql`, `inspect`).
   Revalidar la excepción de `comparar/` (Regla #2): con la API rota permitida, ¿sigue justificada?
8. **Diagrama Mermaid** del flujo objetivo (consumidor → provider → caché → adaptador → catálogo).

#### 3.4 Plan incremental

Entregable `04_PLAN.md`. Grupos ordenados por dependencia; cada uno es un PR revisable, con tests en verde al acabar.
Orden orientativo (ajustar al inventario):

| Grupo | Contenido | Depende de |
|---|---|---|
| A | Contrato, modelo normalizado, caché y API por lotes en el módulo destino; adaptadores por motor | — |
| B | Mover al módulo destino el SQL de catálogo que vive fuera (`comparar/_routine_fetchers.py`, `bulk/_support/pk_sync.py`, `sql_queries.json` de catálogo, …) | A |
| C | Migrar consumidores de capa 6 (`bulk`, `comparar`, `migrate`, `managers`, `analysis`) | A, B |
| D | Migrar consumidores de capa 7 (`dump`, `doc`) | A, B |
| E | Resolver la introspección en capa 4 (`connection/`) y HSQLDB | A |
| F | Optimizaciones por motor medidas (§5) | A; en paralelo con C–E |
| G | Guardas automáticas (§6) | A; endurecer al final |
| H | Docs, reglas IA, CHANGELOG con guía de migración, diagrama de capas | Todos |

Para cada grupo: ficheros, cambios de API, tests que lo cubren, métrica de rendimiento esperada (`ESTIMADO`) y
rollback (`git revert` del PR; qué datos o configuraciones no se revierten solos).

### AUDIT_PLAN

- **Riesgos funcionales**: diferencias de normalización entre el camino viejo y el nuevo (mayúsculas en Oracle,
  schemas por defecto, columnas generadas/identity, vistas sin definición por permisos, routines cifradas o sin
  `DBMS_METADATA`).
- **Riesgos de capas**: imports nuevos que suban de capa; dependencias circulares `managers` ↔ `metadata`.
- **Riesgos de rendimiento**: consultas por schema que traen demasiado en catálogos enormes (paginar o filtrar por
  `tables`); caché obsoleta tras DDL; memoria.
- **Riesgos de seguridad**: identificadores interpolados en SQL de catálogo (`SHOW CREATE`, `PRAGMA`) → validar o
  citar con los helpers existentes (`quote_mariadb_identifier`…); bind parameters en el resto; privilegios mínimos.
- **Compatibilidad**: lista de APIs públicas que se rompen y su sustituto.
- **Simplificaciones**: código que desaparece (wrappers, helpers duplicados, cachés paralelas).

Decisión: `GO` | `GO_CONDICIONAL` (condiciones listadas) | `NO_GO` (bloqueos). Sin `GO`/`GO_CONDICIONAL` aprobado, no
se pasa a IMPLEMENT.

### IMPLEMENT (por grupo)

- Cambios por archivo; docstrings Google-style en las clases públicas nuevas.
- Tests unitarios con SQLite en memoria; integración por motor en `tests/integration/metadata/<motor>/` con
  `pytest.mark.integration`.
- Antes de cerrar cada grupo: `python -m ruff check src tests`, `python -m ruff format src tests`,
  `python -m mypy src tests/unit/test_protocol_conformance.py`, `python -m pytest`,
  `python scripts/gen_arquitectura_capas.py`.
- Medición después del cambio con el mismo procedimiento del baseline (§5.3).

### AUDIT_CODE

- Las búsquedas de §3.1 fuera del módulo destino devuelven solo comentarios o docstrings (o excepciones registradas
  en el ADR).
- Contratos: `Protocol` cumplido por todas las implementaciones (sync y async).
- Rendimiento: tabla antes/después por flujo, motor y volumen; regresiones ≥ 10 % bloquean.
- Veredicto: `GO` | `GO_CONDICIONAL` | `NO_GO`.

### VERSION

Según `.github/prompts/version_closure.prompt.md`: commit (`refactor(metadata): …` / `perf(metadata): …`; si se rompe
API, `!` y `BREAKING CHANGE:`), CHANGELOG con guía de migración, rollback y `## Directrices para Futuras IAs` en el
`TRACEABILITY.md` de la sesión.

---

## 4. Áreas de rendimiento a auditar

Cada área: situación actual medida, propuesta, impacto (`MEDIDO` o `ESTIMADO`), esfuerzo y riesgo.

1. **N+1 de introspección**: recorridos de tablas que llaman `get_columns`/`get_foreign_keys`/`get_pk_constraint` por
   tabla (`dump/orchestrator.py`, `dump/_constraints.py`, `bulk/crud.py`, `analysis/base.py`, `doc/`). Sustituir por una
   lectura por schema y tipo (SQL propio o `Inspector.get_multi_*`).
2. **Lecturas duplicadas en una operación**: p. ej. `dump` lee FKs para el grafo de orden y otra vez para
   desactivar/restaurar constraints. Un snapshot por operación las comparte.
3. **Definiciones de objetos**: `DBMS_METADATA.GET_DDL` por objeto (`comparar/_routine_fetchers.py`) frente a una
   consulta a `ALL_SOURCE` por owner (ya usada en `migrate/extractors/oracle.py`) o `DBMS_METADATA` en modo lote;
   `SHOW CREATE` por routine frente a `INFORMATION_SCHEMA.ROUTINES`; `sys.sql_modules` en una consulta por schema.
4. **Elección de vista de catálogo por motor** (hipótesis a verificar con fuentes y medición):
   - PostgreSQL: `pg_catalog` suele ser más rápido que `information_schema` (vistas con joins y comprobaciones de
     privilegios).
   - SQL Server: `sys.*` frente a `INFORMATION_SCHEMA` (más rápido y más completo; `INFORMATION_SCHEMA.VIEWS` trunca a
     4000 caracteres).
   - Oracle: `USER_*` cuando el owner es el usuario conectado frente a `ALL_*`; evitar columnas `LONG`; estadísticas
     de diccionario (`DBMS_STATS.GATHER_DICTIONARY_STATS`) como recomendación al DBA, no como acción de la librería.
   - MariaDB/MySQL: filtrar siempre por `TABLE_SCHEMA`; en MariaDB `INFORMATION_SCHEMA.TABLES` puede abrir ficheros de
     tabla; en MySQL 8 el diccionario es transaccional y `information_schema_stats_expiry` cachea estadísticas.
   - SQLite: funciones tabla `pragma_table_info(…)`, `pragma_foreign_key_list(…)` unidas a `sqlite_schema` en una sola
     consulta, frente a un `PRAGMA` por tabla.
   - Snowflake: `SHOW …` (solo metadatos, sin warehouse) frente a `INFORMATION_SCHEMA` (necesita warehouse y tiene
     límites de filas).
   - Redshift: `SVV_*` frente a `PG_TABLE_DEF` (solo muestra schemas del `search_path`).
5. **Fetch y transferencia**: `arraysize`/`prefetchrows` en `oracledb`, streaming frente a `fetchall` en catálogos
   grandes, columnas innecesarias (`SELECT *`).
6. **Caché**: tasa de aciertos, ámbito, invalidación, memoria; seguridad entre hilos.
7. **Paralelismo**: lectura concurrente de tipos de objeto independientes (columnas, FKs, índices) con conexiones del
   pool, solo si la medición lo justifica y sin agotar el pool del consumidor.
8. **Normalización**: coste de convertir filas por motor a la estructura común (evitar pasar por `pandas` para
   metadatos, evitar copias).
9. **Async**: que el camino async no serialice lo que el sync agrupa (paridad de número de consultas).

---

## 5. Medición

### 5.1 Métricas

| Métrica | Cómo | Objetivo |
|---|---|---|
| Consultas por operación | Contador con `event.listen(engine, "before_cursor_execute", …)` | O(1) por schema y tipo de objeto, no O(tablas) |
| Tiempo por operación | `time.perf_counter()`, mediana de ≥ 3 repeticiones | Fijar en PLAN tras el baseline |
| Pico de memoria | `tracemalloc` | No empeorar más de un 10 % |
| Aciertos de caché | Estadísticas de la caché (`get_cache_stats` o equivalente) | Una lectura por dato y operación |

No fijes umbrales porcentuales antes de tener baseline: decídelos en PLAN con los números delante.

### 5.2 Guardas deterministas (CI, sin motores)

Tests con SQLite en memoria que **cuentan consultas** de cada flujo para 1, 10 y 100 tablas y fallan si el número
crece con las tablas. Son la protección contra regresiones N+1.

### 5.3 Benchmark por motor (banco opcional)

`scripts/bench_metadata.py` (nuevo, mismas convenciones que `scripts/bench_dump.py`: subcomandos `setup`/`run`,
puertos `UTIL_BBDD_BENCH_<MOTOR>_PORT`, contraseña `UTIL_BBDD_BENCH_PASSWORD`, solo `127.0.0.1`, resultados en
`bench_results/metadata/`). Genera schemas con N tablas, FKs, índices, vistas y routines; mide cada flujo de §3.2
antes y después. Contra los contenedores de `docker-compose.bench.yml`, nunca contra bases reales.

---

## 6. Guardas automáticas

- `tests/unit/test_architecture_metadata_rules.py` (nuevo): falla si aparece SQL de catálogo (patrones de §3.1) o
  `inspect(`/`Inspector` fuera del módulo destino, salvo una lista de excepciones con justificación y referencia al
  ADR. Escanea código, no comentarios ni docstrings (usar `ast` como `scripts/gen_arquitectura_capas.py`).
- Tests de conteo de consultas de §5.2.
- Test de conformidad de `Protocol` (ampliar `tests/unit/test_protocol_conformance.py`).
- `tests/unit/test_architecture_import_rules.py` sigue en verde sin excepciones nuevas.

---

## 7. Documentación y configuración a sincronizar

- `docs/api/metadata_manager.md`, `docs/api/managers_metadata_factory.md`, `docs/functional/metadata_extraction.md`,
  guía de migración en `CHANGELOG.md`, `docs/adr/ADR-003-*.md`, `mkdocs.yml` si hay páginas nuevas.
- `docs/architecture.md` (diagrama regenerado) y `.ai/architecture.md` si cambian paquetes o capas.
- `.github/instructions/architecture.instructions.md` § «Reglas de acceso a metadatos»: nuevo destino, nuevo patrón
  canónico, excepciones vigentes.
- `SHARED_INSTRUCTIONS.md` (tabla de responsabilidades) y entry points según su checklist de sincronización.

---

## 8. Criterios de éxito (veredicto final)

| Criterio | Verificación | Umbral |
|---|---|---|
| Centralización | Búsquedas de §3.1 + `test_architecture_metadata_rules.py` | 0 apariciones fuera del módulo destino salvo excepciones del ADR |
| Un camino por dato | Matriz de §3.1 sin duplicados | 0 duplicados no justificados |
| Cobertura de motores | Matriz motor × objeto | Sin `?`; cada `✗` justificado |
| Capas | `gen_arquitectura_capas.py` + `test_architecture_import_rules.py` | Verde, sin excepciones |
| Rendimiento | Tabla antes/después (§5) | Consultas O(1) por schema y tipo; tiempos según umbrales fijados en PLAN; sin regresiones ≥ 10 % |
| Tests | `python -m pytest` | Sin fallos nuevos |
| Documentación | `zensical build --strict` | Sin errores ni enlaces rotos |

`GO` si se cumplen todos; `GO_CONDICIONAL` si solo quedan pendientes documentados y no bloqueantes; `NO_GO` en otro
caso.

---

## 9. Referencias

**Internas**: `.github/instructions/architecture.instructions.md` (Reglas #1–#6), `.ai/architecture.md`,
`docs/architecture.md`, `docs/adr/ADR-002-modulo-auditoria.md` (precedente de centralización de un módulo transversal),
`comparar/_prefetch.py` (precedente de lectura por lotes), `.github/prompts/performance_audit_dump.prompt.md` (formato de
hallazgos de rendimiento).

**Externas** (consultar la versión vigente y anotar fecha):

- SQLAlchemy 2.x — Reflection / `Inspector`, incluidos los métodos `get_multi_*`: https://docs.sqlalchemy.org/en/20/core/reflection.html
- PostgreSQL — System Catalogs: https://www.postgresql.org/docs/current/catalogs.html
- SQL Server — System catalog views: https://learn.microsoft.com/sql/relational-databases/system-catalog-views/catalog-views-transact-sql
- Oracle Database Reference — Static data dictionary views (`ALL_*`, `USER_*`) y `DBMS_METADATA`
- MariaDB — Information Schema: https://mariadb.com/kb/en/information-schema/ · MySQL 8 — INFORMATION_SCHEMA y data dictionary
- SQLite — PRAGMA (funciones tabla `pragma_*`): https://www.sqlite.org/pragma.html
- Snowflake — `SHOW` frente a `INFORMATION_SCHEMA`; Redshift — vistas `SVV_*`
- Proyectos de referencia en lectura de catálogos multimotor: SQLAlchemy dialects, Alembic autogenerate, dbt adapters
  (`get_columns_in_relation`, caché de relaciones)

---

*Prompt versión: 2.0* · *Actualizado: 2026-10-02* · *Línea base medida sobre util_bbdd v0.29.0*
