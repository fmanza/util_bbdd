# PLAN + AUDIT_PLAN — pendientes tras `documentation-architecture-audit` (v0.41.0)

Fecha: 2026-10-09 · Base: `develop` @ `2660164d` (0.41.0, sin tag) · Origen: `.ai/sessions/2026-10-09k-doc-architecture-audit/06_VERIFY.md` § 3

Solo lectura: no se ha cambiado código. Las comprobaciones de § 1 se hicieron contra el banco docker y con scripts
temporales (fuera del repo).

## 0. Decisiones pendientes del usuario

| # | Tema | Opciones | Recomendación |
|---|---|---|---|
| D1 | 0.41.0 | (a) etiquetar 0.41.0 tal cual y publicar los arreglos en 0.41.1; (b) meter P1–P4 en 0.41.0 antes del tag | **(a)**: 0.41.0 ya pasó VERIFY y lo que sigue es independiente |
| D2 | Push | Los tags y los commits están solo en local | Push solo cuando lo indiques (acción externa) |
| D3 | Dorado de Oracle (P5) | (a) usuario `ZZ_GOLD_DOC` creado con `SYSTEM` (nueva variable `UTIL_BBDD_TEST_ORACLE_ADMIN_URL`); (b) dejarlo saltado | **(a)**: es el único motor sin dorado de documentación |
| D4 | `mypy --strict` (P6) | (a) corregir los 72 `type-arg` y fijar `disallow_any_generics` en `util_bbdd.doc.*`/`analysis.*`; (b) solo corregir; (c) no hacer nada | **(a)**: evita que vuelvan |
| D5 | `matplotlib_graph` (P7) | (a) tests con backend Agg y `matplotlib`/`networkx` en el extra `dev`; (b) tests con `importorskip` sin tocar `dev`; (c) no hacer nada | **(b)**: sin coste para quien no lo usa |

## 1. Estado verificado

| ID | Pendiente | Lo comprobado | Severidad |
|---|---|---|---|
| B-04 | DDL de tabla de HSQLDB (`metadata/ddl.py` `_NATIVE_TABLE_DDL_SQL["hsqldb"]`) | Contra HSQLDB 2.7.4 del banco: (1) `LISTAGG` exige `WITHIN GROUP`; con `WITHIN GROUP (ORDER BY ORDINAL_POSITION)` funciona y además fija el orden de las columnas (hoy sin orden); (2) **la rama `UNION … INFORMATION_SCHEMA.VIEWS.TEXT` también falla**: esa columna no existe (es `VIEW_DEFINITION`); (3) los `CASE` con literales devuelven `CHAR` con relleno: `ID INTEGER         ,`. Sin PK ni FK en el DDL, a diferencia de PostgreSQL y SQL Server | **Alta** para HSQLDB: documentar con `tablas.ddl=True` falla entero |
| S-02 | HTML decodifica entidades del DDL hasta 3 veces en Python (`HtmlGenerator._decode_html_entities`, 3 llamadas) y otras 3 en `sql-highlight.js` | Vista con `CASE WHEN id < 2 THEN '&amp;<b>' ELSE '>' END` en los 6 motores del banco: **todos devuelven el texto tal cual**. La decodificación viene del commit inicial (`805889c9`) sin motivo registrado. Efecto: HTML muestra `'&<b>'` donde el motor guarda `'&amp;<b>'`; Word y Excel lo muestran bien | **Media** (fidelidad; no es inyección: el JS reescapa antes de `innerHTML`) |
| ORD | Orden no determinista del inventario de almacenamiento | MySQL/MariaDB `ficheros_fisicos` ordena por `total_mb DESC` sin desempate: las tablas del mismo tamaño salen en orden distinto en cada ejecución. PostgreSQL y SQLite no tienen `ORDER BY`. Oracle y SQL Server sí | Baja |
| DOC | `DatabaseConnectionError` en 4 docstrings (`factory/sqlalchemy_engine_factory.py:76`, `managers/sync_mgr.py:91` y `:707`, `managers/_manager_lifecycle_sync.py:107`) | No existe; el código lanza `ConnectionError` (`_core/exceptions.py`) | Baja (documentación) |
| ORA | Dorado de documentación de Oracle saltado | El contexto de metadatos de Oracle es siempre el usuario conectado (`MetadataContextResolver`), no admite otro schema; el usuario `bench` tiene objetos de otras pruebas. El contenedor tiene `ORACLE_PASSWORD` (SYSTEM) | Hueco de test |
| TYP | `mypy --strict` en `doc/`/`analysis/` | 81 errores: 72 `type-arg` (Excel 37, Word 21, HTML 12, matplotlib 2) y 9 `no-untyped-call` de python-docx (`add_page_break`, `add_row`). La puerta del repo (`mypy` sin `--strict`) está limpia | Baja |
| MPL | `analysis/matplotlib_graph.py` al 27 % | `matplotlib`/`networkx` no están en el extra `dev` (sí en el entorno local) | Baja |

## 2. PLAN por bloques (en orden)

| # | Bloque | Contenido | Flujo | Versión |
|---|---|---|---|---|
| P0 | Cierre de 0.41.0 | Tag `v0.41.0` sobre `2660164d`; `CURRENT_STATE` y `INDEX` con el tag. Push según D2 | `/version-closure` | 0.41.0 |
| P1 | B-04 | `metadata/ddl.py`: `LISTAGG(… ORDER BY ORDINAL_POSITION)` con `WITHIN GROUP`; quitar la rama `UNION` de vistas (el DDL de vistas sale del snapshot, `view_ddl`); `CAST(… AS VARCHAR(…))` en los `CASE` para quitar el relleno; añadir `CONSTRAINT … PRIMARY KEY (…)` desde `INFORMATION_SCHEMA.TABLE_CONSTRAINTS`/`KEY_COLUMN_USAGE`, como en PostgreSQL. Test de integración en `tests/integration/test_hsqldb_server.py` (`get_ddl` y `DatabaseDocumentation` con `ddl=True`) y unitario del texto en modo memoria si hay jar | `/hotfix` | 0.41.1 |
| P2 | S-02 | Quitar `_decode_html_entities` (Python) y `decodeHtmlEntities` (`sql-highlight.js`): el resaltado usa `textContent` tal cual. Test: el e2e de SQLite añade una vista con `'&amp;<b>'` y comprueba que la página la muestra igual que Word y Excel | `fix(doc)` | 0.41.1 |
| P3 | ORD | `metadata/storage.py`: desempate por nombre (`ORDER BY total_mb DESC, <objeto>`) en MySQL/MariaDB y `ORDER BY` en PostgreSQL y SQLite. Test unitario: toda consulta de inventario con filas tiene `ORDER BY`; comprobación con el banco: dos ejecuciones de `doc_output_snapshot.py` idénticas | `fix(metadata)` | 0.41.1 |
| P4 | DOC | Los 4 docstrings: `ConnectionError` | `docs` | 0.41.1 |
| P5 | ORA (si D3=a) | `_schemas.py`: target Oracle de documentación con usuario `ZZ_GOLD_DOC` (crear con `SYSTEM`: `CREATE USER … QUOTA`, `GRANT CREATE SESSION, TABLE, VIEW, PROCEDURE`; borrar en `finally` con `DROP USER … CASCADE`); `scripts/bench_env.example.{sh,ps1}` exportan `UTIL_BBDD_TEST_ORACLE_ADMIN_URL`; dorado `oracle_doc.txt` generado con `UTIL_BBDD_UPDATE_GOLDEN=1` y revisado | `test` | — |
| P6 | TYP (según D4) | Anotar los genéricos de los renderers (`list[tuple[Any, ...]]` → alias `DbRow`, `dict[str, Any]`…); override `disallow_any_generics = true` para `util_bbdd.doc.*` y `util_bbdd.analysis.*`. Los 9 `no-untyped-call` de python-docx se quedan (un `type: ignore` sería «unused» con la puerta del repo) | `refactor` | — |
| P7 | MPL (según D5) | Tests de `MatplotlibRelationshipGraph` con backend Agg sobre un `RelationshipGraphSource` falso, con `pytest.importorskip("matplotlib")`/`("networkx")` | `test` | — |

Orden: P0 primero (cierra lo verificado), P1–P4 en un mismo patch (cuatro commits, un tag `v0.41.1`), después P5–P7 sin versión
propia (tests y tipos). P1 es el único que toca el banco de forma no trivial (HSQLDB), y P5 el único que crea objetos de
administración (usuario Oracle).

## 3. AUDIT_PLAN

### Riesgos funcionales

| Bloque | Riesgo | Mitigación |
|---|---|---|
| P1 | El texto del DDL de HSQLDB cambia (orden de columnas, sin relleno, con PK) para quien lo compare como cadena | Hoy falla siempre que se pide: no hay salida previa que preservar. CHANGELOG «Fixed» |
| P1 | `get_ddl(<vista>)` en HSQLDB deja de pasar por `INFORMATION_SCHEMA.VIEWS` | Esa rama nunca funcionó (`TEXT` no existe). Comprobar en IMPLEMENT con `grep` que ningún consumidor (`comparar`, `migrate`) llama a `get_ddl` con vistas de HSQLDB |
| P1 | Los modos de compatibilidad de HSQLDB (`sql.syntax_ora`, `sql.syntax_mys`) cambian la gramática | Probar la consulta con `connection_properties={"sql.syntax_ora": "true"}` (ya hay un test así en `test_hsqldb_server.py`) |
| P2 | Un motor no probado (HSQLDB) que devuelva el DDL con entidades se vería con `&lt;` | Repetir la sonda de § 1 con HSQLDB en IMPLEMENT antes de quitar la decodificación |
| P2 | Plantillas HTML propias (`plantilla_html`) que dependan del JS antiguo | El JS se copia a la salida en cada generación; el contrato de la plantilla (`code.language-sql`) no cambia |
| P3 | El orden de filas del inventario cambia en documentos ya generados | Solo entre filas del mismo tamaño (MySQL/MariaDB) o donde no había orden (PostgreSQL, SQLite) |
| P5 | Crear un usuario con `SYSTEM` en el Oracle compartido del banco | Nombre `ZZ_GOLD_DOC` fijo; `DROP USER … CASCADE` en `finally` y antes de crear (por ejecuciones interrumpidas); el test se salta sin `UTIL_BBDD_TEST_ORACLE_ADMIN_URL` |
| P6 | `disallow_any_generics` saca errores nuevos en `doc/` | Se conocen los 72; el override entra en el mismo commit que la corrección |

### Riesgos técnicos

- **Heredocs y barras invertidas**: P1 y P3 editan SQL con `\` potenciales y P2 un JS con regex; editar con Write/Edit
  (memoria del proyecto) y comprobar con `cat -A` si hay dudas.
- **HSQLDB necesita `JAVA_HOME="C:/Program Files/Java/jdk-25"`** para el cliente JDBC; sin él sus tests dan
  `JVMNotFoundException` (entorno, no fallo).
- **Dorados**: P2 no cambia los dorados de documentación (no tienen `<`/`&`); P5 crea `oracle_doc.txt` nuevo, que hay
  que revisar a mano antes de versionarlo.

### Riesgos de seguridad

- P2 mejora la fidelidad sin abrir inyección: Jinja2 sigue escapando el DDL una vez y el JS escapa antes de `innerHTML`
  (el test `test_html_svg_escaping.py` cubre el SVG; P2 añade el caso del DDL).
- P5 maneja credenciales de `SYSTEM`: solo desde variable de entorno (`bench_env` las construye desde
  `UTIL_BBDD_BENCH_PASSWORD`), nunca en logs ni ficheros versionados.

### Verificación por bloque

| Bloque | Evidencia |
|---|---|
| P1 | `pytest tests/integration -k hsqldb` (con `JAVA_HOME`) incluye `get_ddl` y la documentación con `ddl=True`; DDL de una tabla de 3 columnas con PK, en orden y sin relleno |
| P2 | e2e de SQLite con la vista `'&amp;<b>'`; sonda de HSQLDB; `test_doc_matches_golden` sin cambios |
| P3 | `doc_output_snapshot.py` dos veces seguidas: ficheros idénticos en los 6 motores (hoy difieren MySQL/MariaDB) |
| P4 | `grep -rn DatabaseConnectionError src` vacío |
| P5 | `test_doc_matches_golden[oracle]` pasa (deja de saltarse) y es estable en dos ejecuciones |
| P6 | `mypy --strict src/util_bbdd/doc src/util_bbdd/analysis` = 9 (solo python-docx); puerta del repo limpia |
| P7 | `matplotlib_graph.py` ≥ 80 % con matplotlib instalado; se salta sin él |
| Todos | `ruff check`, `ruff format`, `mypy src tests/unit/test_protocol_conformance.py`, `pytest`, `zensical build --strict` |

### Veredicto AUDIT_PLAN

**GO_CONDICIONAL**: P0–P4 pueden ejecutarse en cuanto se resuelvan D1 y D2. P5–P7 dependen de D3–D5.
