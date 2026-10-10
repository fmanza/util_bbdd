# PLAN + AUDIT_PLAN — revisión de docs, nivel 2 (D2)

Fecha: 2026-10-10 · Base: `develop` @ `fbcf63ff` (código = v1.1.0 `e4467d25`; el paquete instalado es el editable de
`src/`) · Fase: solo lectura. Logs de esta fase: `build/logs/docsn2_{doc_check,overlap,sweep}_before.txt`.

## 0. Fuentes revisadas

Los dos `02_DOC_REVIEW.md` (método y tipos de error), `03_DOCS_PENDIENTES.txt` (copiado a esta sesión),
`.github/DOCUMENTATION_STANDARD.md`, `.github/instructions/docs.instructions.md`, `mkdocs.yml` (nav y
`pymdownx.snippets` con `base_path: [docs]`), `pyproject.toml` (extras), `docs/examples/*.py`, `docker ps` (banco).

## 1. Herramientas (en `tools/` de esta sesión)

El comprobador de las sesiones anteriores no quedó en el repo (solo sus logs), así que lo he reescrito:

- **`tools/doc_check.py`**: recorre cada `.md` por líneas (fences ``` y ~~~ con sangría y longitud de cierre ≥
  apertura), bloques python/py/pycon o sin lenguaje; **sigue las inclusiones `--8<-- "x.py"`** (los 17 ejemplos meten
  así su `.py`, y `parallel_bulk_insert.md` 4 más de `examples/database/`). Comprueba (1) cada import de `util_bbdd`
  contra el paquete instalado y (2) los accesos `x.m` de variables ligadas a un punto de entrada
  (`x = SyncDatabaseManager(...)`, `with … as x`, `await Clase.create(...)`) y de los nombres convencionales
  (`manager`, `mgr`, `db`…) contra los managers. Usa `ast`; si el bloque no parsea, cae a líneas.
- **`tools/overlap.py`**: solapamiento textual entre páginas (shingles de 6 palabras, sin código ni encabezados).

Línea base (`docsn2_doc_check_before.txt`): 82 páginas, 21 inclusiones `.py`, **93 imports y 74 accesos a métodos**,
11 hallazgos, ninguno real:

- 10 son bloques «antes» intencionados: `guides/api_1_0_migration.md:62` (imports 0.x desde la raíz) y
  `guides/migration_guide_v0.6.7.md:64, 74` (excepciones de 0.6.6). Irán a una lista de excepciones `path:línea`
  (`tools/doc_check_allow.txt`) para que la puerta «sin hallazgos» sea literal.
- 1 es `util_bbdd._support.sql_normalizer` en `code_reusability_analysis_guide.md:258`, ya registrado en la sesión de
  1.0 como propuesta hipotética ilustrativa.

**Conclusión de la línea base**: los ejemplos y los imports están sanos; los errores de estas páginas están en el
**texto y en las tablas** (firmas, parámetros, excepciones, listas de motores, cifras), que el comprobador no ve. Por
eso el peso de la sesión es la lectura con `inspect`, no la herramienta.

## 2. Inventario por tanda

~8.800 líneas en total. Todas las páginas están en el `nav`.

| Tanda | Páginas | Líneas | Naturaleza | Riesgos ya detectados (con evidencia) |
|---|---|---|---|---|
| **1** `docs/api/` | 26 (6 con autodoc `:::`: `bulk`, `comparator`, `dump_autodoc`, `exceptions`, `managers`, `reporters`) | ~2.460 | Tablas «Firma simplificada», contratos de entrada/salida, errores | **`managers_sync_technical.md` describe una API que no existe**: `introspect()`, `execute(query)`, `DatabaseSchema`, `__init__(db_type, credenciales, pool_config?)`, `pool_config={"min_size", "max_size"}`. `managers_sync.md`: `db_type` sin `mysql`, `Rows = list[tuple]` y tabla de errores (`ValidationError`, `ConnectionError`) por verificar contra `_core/exceptions.py`. `bulk_parallel.md:80`: aceleraciones «con 4 hilos (1M filas, v0.26.0)» sin fuente citada |
| **2** `docs/functional/` | 15 | ~1.200 | Reglas de negocio, casos de uso, precondiciones | `managers_sync.md`: lista de motores sin MySQL (2 sitios). `managers_sync_session_lifecycle.md`: «el gestor no paraleliza solicitudes; usa una cola de espera», «timeout de reconexión» (huelen a inventado; verificar) |
| **3** `docs/examples/` | 17 `.md` + 17 `.py` (+4 de `examples/database/`) | ~930 + código | Ejemplo + explicación + «Ejecución y pruebas» | `schema_comparison.md` dice «requiere dos BDs accesibles» y el `.py` usa SQLite en memoria. Los 4 `migrate_*` y `dump_data_export`/`bulk_insert_csv` llevan hosts de relleno (`mariadb-host`…): se ejecutan con copias en el scratchpad apuntando al banco. Los `migrate_*` solo planifican (leen el origen); `dump_data_export.py` escribe en SQL Server `dbo` y `bulk_insert_csv.py` crea `usuarios` en PostgreSQL |
| **4** `docs/guides/` + 4 sueltas | 20 + `architecture.md`, `downloads.md`, `legacy_versions.md`, `ai-config/claude.md` | ~3.650 + ~550 | Guías paso a paso, IA, históricas | `pip install "util_bbdd[x]"` sin URL de git: 11 líneas en `connection_guide` (4), `drivers` (3), `ddl_migration_guide` (2), `troubleshooting`, `functional/managers_sync`. `migration_guide.md:22` `pip install --upgrade util_bbdd`. `async_guide.md:55` tabla de pool con `max_overflow`, `pool_recycle` y «Throughput aprox.» sin fuente. `troubleshooting.md:47` `max_overflow` en `conn_params`. `connection_guide.md:286–310` `max_overflow` por motor (en MySQL puede ser correcto: `QueuePool`; verificar por motor). `legacy_versions.md`: cronología que acaba en «v0.8.0 – v0.10.0 (Actual)» y etiqueta «Migración v0.5 → v0.6» para la guía v0.6.7. 7 guías de configuración IA (`claude_code_guide`, `codex_guide`, `github_copilot_guide`, `doc_generation_vscode_guide`, `doc_verification_guide`, `ai-config/claude.md`, `code_reusability_analysis_guide`) a verificar contra `.claude/commands/`, `.github/agents/`, `.github/prompts/` |

## 3. Consolidaciones (propuestas antes de corregir)

El solapamiento **literal** es bajo (`docsn2_overlap_before.txt`: máximo 23 %, y es entre los `migrate_*`, de
estructura paralela a propósito). Las repeticiones son de **tema**:

| # | Páginas | Evidencia | Propuesta |
|---|---|---|---|
| C1 | `api/managers_sync_technical.md` → `api/managers_sync.md` | Mismo objeto (`SyncDatabaseManager`); la «técnica» tiene la API pública inventada (ver tanda 1) y solo aporta una tabla de componentes internos (`SyncConnectionLifecycleManager`, `CatalogSource`, `SnapshotCache`, `SyncCatalogFacade`, `SyncQueryExecutor`), mientras `managers_sync.md` §3 dice «No aplica» y remite a otras páginas | Llevar la tabla de componentes (verificada) a §3 de `managers_sync.md`, borrar `managers_sync_technical.md`, quitarla del `nav` y rehacer sus enlaces. Commit propio `docs(api)` |
| C2 | `functional/managers_sync_session_lifecycle.md` → `functional/managers_sync.md` | Mismo tema funcional (manager síncrono: precondiciones, cierre, pool); la de ciclo de vida repite precondiciones y añade reglas por verificar | **Decidir tras leerlas en la tanda 2**: te traigo el diff de contenido único de cada una antes de tocar nada |
| C3 | `guides/migration_guide.md` (→ v0.6.3) y `guides/migration_guide_v0.6.7.md` | Históricas, con aviso de guía histórica | **No consolidar**; revisión ligera (ver D3) |
| — | `api/dump.md` + `dump_autodoc.md` + `dump_reporter.md`; `api/schema_comparator.md` + `comparator.md` + `reporters.md`; `api/managers.md` + `managers_sync.md` | Patrón deliberado: página manual + página autodoc (`:::`) + clase auxiliar | No consolidar; solo vigilar que no se contradigan |
| — | `functional/dump_data_export.md` ↔ `guides/dump_guide.md` (14 %) | Arquetipos distintos (funcional / guía) | No consolidar; coherencia cruzada |

## 4. Método por página (el de las sesiones anteriores, concretado)

1. `doc_check.py` sobre la página → 0 hallazgos fuera de la lista de excepciones.
2. Lectura completa. Cada tabla «Firma simplificada» contra `inspect.signature` (nombres, orden, `*`, defaults, retorno);
   parámetros de conexión contra `connection/config.py` y las `*Config` por motor; excepciones con `grep raise` en el
   módulo real; motores contra `get_supported_db_types()`; extras contra `pyproject.toml`; CLI de scripts con
   `--help`/`list`; rutas con `ls`; códigos de aviso contra su `Enum`.
3. Ejemplos tocados: ejecución real (tanda 3: todos). SQLite en el scratchpad; motores del banco con copias del `.py`
   que solo sustituyen `conn_params` por los del banco (contraseña leída de los contenedores, nunca mostrada) y
   esquemas/tablas temporales que se borran al terminar.
4. Cifras de rendimiento: se busca su sesión de medición en `.ai/sessions/` y `build/logs/`; sin fuente → se quitan o
   se marcan «pendiente de verificación».
5. Barrido de errores típicos (`docsn2_sweep_before.txt`): instalación PyPI, `psycopg2`/`cx_Oracle` como driver de
   los managers, «wrappers» de paramstyle, `max_overflow` en PostgreSQL, `migrate` sin MySQL como destino, SQL de otro
   motor.
6. Registro en `02_DOC_REVIEW.md` (tabla Hallazgo / Dónde / Corrección, como las anteriores) y commit
   `docs(<área>): revisión nivel 2 de …` por tanda.

Orden: C1 (si se aprueba) → tanda 1 → 2 (con la propuesta de C2 al empezar) → 3 → 4 → puerta de cierre → VERSION
(`TRACEABILITY.md` con «Directrices para Futuras IAs»). La tanda 3 va después de 1–2 a propósito: si un ejemplo destapa
un fallo de la librería, las páginas de API y funcionales ya estarán corregidas y el `/hotfix` se aísla mejor.

## 5. AUDIT_PLAN — riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Un ejemplo destapa un fallo de la librería (precedentes: asyncpg, pyodbc) | Media (tanda 3 toca 5 motores) | Alto | **Me detengo y te pregunto** (`/hotfix` aparte); la tanda sigue con el resto de páginas y el ejemplo afectado queda marcado en el registro |
| «Corregir» hacia lo que creo y no hacia el código | Media | Alto | Toda corrección cita su fuente (`inspect`, fichero:línea, salida de ejecución); lo no verificable se marca «pendiente de verificación», no se inventa |
| Ensuciar el banco al ejecutar `dump`/`bulk` | Media | Medio | Esquemas o tablas temporales con prefijo `docsn2_` y borrado al final; los `migrate_*` solo leen |
| La puerta «comprobador sin hallazgos» imposible por los bloques «antes» | Segura | Bajo | Lista de excepciones explícita `path:línea` en `tools/` |
| Enlaces rotos al borrar o mover páginas (C1, C2) | Media | Bajo | `zensical build --strict` en la puerta de cada tanda + `grep` de enlaces entrantes antes de borrar |
| Tanda 4 desborda (3.650 líneas, 7 guías de IA con mucho prosa de proceso) | Media | Medio | Si se alarga, la parto en 4a (uso: conexión, drivers, async, dump, ddl, excepciones, troubleshooting, onboarding) y 4b (IA, históricas, docs offline, arquitectura) con un commit cada una |
| Tú trabajas en paralelo en el repo | Media | Medio | Solo `git add` de rutas propias; `.ai/sessions/2026-10-10-api-1-0-final/NEXT_SESSION_PROMPT.md` (sin seguimiento) no es mío y no lo toco |
| Cambios de API detectados que piden código, no docs (p. ej. un parámetro documentado que debería existir) | Baja | Medio | Se registran como «fuera de alcance» con propuesta; no se tocan `src/` en esta sesión |

## 6. Decisiones para ti

| # | Tema | Opciones | Recomendación |
|---|---|---|---|
| D1 | C1: `managers_sync_technical.md` | (a) consolidar en `managers_sync.md` y borrarla; (b) corregirla y mantener las dos | **(a)** |
| D2 | C2: funcionales del manager síncrono | (a) te traigo la propuesta al empezar la tanda 2; (b) consolidar ya sin leer | **(a)** |
| D3 | Guías históricas (`migration_guide.md`, `migration_guide_v0.6.7.md`, `mariadb_v0.35.0_charset_handling.md`) | (a) revisión ligera: aviso de histórica, instalación, enlaces, y que nada se presente como vigente; no se reescribe la API antigua; (b) revisión completa contra 1.1.0 | **(a)**: su valor es el «antes»; reescribirlas contra 1.1.0 las destruye |
| D4 | Dónde vive el comprobador | (a) `tools/` de esta sesión (ya está); (b) `scripts/check_doc_code.py` versionado con test, como puerta permanente | **(a)** ahora; (b) es candidato a deuda técnica (evita reescribirlo una tercera vez), lo anoto en «Directrices para Futuras IAs» |
| D5 | Ejemplos con escritura en el banco (`dump_data_export`, `bulk_insert_csv`) | (a) esquemas/tablas temporales `docsn2_*` en el banco, borrados al final; (b) solo SQLite | **(a)** |

**Decisión del usuario (2026-10-10): «ok» → D1–D5 según la recomendación.** D1 (a) consolidar C1; D2 (a) propuesta
de C2 al empezar la tanda 2; D3 (a) revisión ligera de históricas; D4 (a) comprobador en `tools/`; D5 (a) esquemas
temporales `docsn2_*` en el banco.
