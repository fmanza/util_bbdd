# Instrucciones Compartidas: Copilot Chat + Claude Code + Gemini + Codex + Cursor

Configuración unificada para trabajar en `util_bbdd` con asistentes de código.
Las reglas de cada plataforma solo deben añadir especialización; esta página es la
fuente común para arquitectura, calidad, pruebas y documentación.

---

## Rol esperado

Actúa como senior de ingeniería Python especializado en:
- Operaciones de bases de datos: conexiones pooled, CRUD en lote, introspección y documentación de esquemas.
- Diseño de librerías multimotor (MariaDB, MySQL, Oracle, PostgreSQL, Redshift, Snowflake, SQLite, SQL Server, HSQLDB).
- Programación asíncrona con `asyncio` y drivers async (`asyncpg`, `aiosqlite`, `aiomysql`).
- Procesamiento de datos con `pandas` y SQLAlchemy.
- Testing determinista con `pytest` sin servicios externos (SQLite en memoria).
- Documentación de librerías Python con Zensical / MkDocs Material (mismo `mkdocs.yml`).

---

## Proyecto: util_bbdd

`util_bbdd` es una librería Python para operaciones con múltiples motores de base de datos:
conexiones pooled (sync/async), CRUD masivo, auditoría, introspección de esquemas, comparación
entre esquemas, migración DDL entre motores, generación de documentación y visualización de relaciones.

**Versión canónica**: consultar `pyproject.toml` antes de cerrar releases.
**Python**: `>=3.12` según `pyproject.toml`.

### Capacidades principales

- **Managers sync/async**: `SyncDatabaseManager` y `AsyncDatabaseManager` con pool de conexiones.
- **Bulk CRUD**: inserciones, actualizaciones y borrados masivos desde `pandas.DataFrame`.
- **Metadatos e introspección**: listar tablas, columnas, índices, DDL por motor; soporta
  MariaDB, MySQL, Oracle, PostgreSQL, Redshift, Snowflake, SQLite, SQL Server.
- **Migración DDL**: `MigrationPlanner` traduce esquemas completos entre motores (Oracle, MariaDB,
  SQL Server, PostgreSQL como origen o destino).
- **Comparación de esquemas**: `SchemaComparator` + reporters (SQL, HTML, Word, Excel, Markdown).
- **Documentación de BD**: genera documentación en Word, Excel o HTML a partir de metadatos reales.
- **Análisis de relaciones**: grafos con Graphviz (`GraphvizRelationshipGraphExt`).
- **Validadores y query registry**: `QueryRegistry`, `QueryResolver`, validadores de parámetros.

---

## Arquitectura real

```text
src/util_bbdd/
  managers/             # SyncDatabaseManager, AsyncDatabaseManager
  bulk/                 # bulk_crud, AuditManager
  dump/                 # Volcado de datos entre esquemas/motores (orden FK, constraints, informe Excel)
  migrate/              # MigrationPlanner: migración DDL entre motores (extractors, IR, emitters)
  metadata/             # SyncMetadataProvider, AsyncMetadataProvider, DatabaseMetadataCache
  comparar/             # SchemaComparator, SchemaDiff, reporters (SQL/HTML/Word/Excel/MD)
  doc/                  # Generación de documentación (Word, Excel, HTML, Jinja2)
  connection/           # build_conn_params, params builder, configs por motor
  factory/              # ConnectionFactory, PoolFactory
  query/                # QueryRegistry, QueryResolver, query execution
  validators/           # Validadores de parámetros de queries
  analysis/             # GraphvizRelationshipGraphExt, grafos de relaciones
  executors/            # Ejecutores de queries (sync/async)
  results/              # Row, Rows, RowOrNone, QueryResult
  core/                 # capabilities.py (capacidades por motor)
  _core/                # exceptions.py (jerarquía centralizada de excepciones)
  _drivers/             # get_supported_db_types, detección de drivers
  data/                 # database_types.json, sql_queries.json (datos empaquetados)
  docs_build_plugin.py  # Plugin de build de la documentación (ZIP offline)
  models.py             # Modelos de datos compartidos
  async_utils.py        # maybe_await
  __init__.py           # API pública
```

### Responsabilidades por módulo

| Módulo | Responsabilidad |
|---|---|
| `managers/` | Ciclo de vida de conexión: init, pool, cierre; operaciones de BD |
| `bulk/` | CRUD masivo desde DataFrame con auditoría y generación de SQL |
| `dump/` | Volcado de datos entre esquemas/motores con orden por dependencias FK |
| `migrate/` | Migración DDL entre motores (`MigrationPlanner`) |
| `metadata/` | Introspección de esquemas: tablas, columnas, índices, DDL; caché en sesión; único punto autorizado para SQL de introspección (ver `.github/instructions/architecture.instructions.md` § Reglas de acceso a metadatos) |
| `comparar/` | Comparación de dos esquemas; diff estructurado; reporters por formato |
| `doc/` | Documentación de BD en Word, Excel y HTML vía Jinja2 |
| `connection/` | Construcción de parámetros y configuración de conexión por motor |
| `factory/` | Factory de conexiones y pools; abstracción de engine SQLAlchemy |
| `query/` | Registry de queries nombradas, resolver, parámetros |
| `validators/` | Validación de parámetros de queries antes de ejecución |
| `analysis/` | Grafos de relaciones entre tablas (Graphviz) |
| `results/` | Tipos de retorno: `Row`, `Rows`, `RowOrNone`, `QueryResult` |
| `_core/` | Jerarquía de excepciones canónica |

### API pública recomendada

```python
from util_bbdd import (
    SyncDatabaseManager,
    AsyncDatabaseManager,
    SyncMetadataProvider,
    AsyncMetadataProvider,
    SchemaComparator,
    ConnectionFactory,
    PoolFactory,
    DatabaseMetadataCache,
    maybe_await,
    build_conn_params,
)

# Ejemplo: conexión y listado de tablas
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "usr", "password": "pwd", "database": "mydb"},
)
tables = manager.get_tables()
manager.close()
```

---

## Principios de diseño

### Operaciones de bases de datos
- Usa `sqlalchemy` como capa de abstracción; no construyas SQL raw en la capa de managers.
- Valida `db_type` al inicio; lanza `InvalidDatabaseType` antes de intentar conexión.
- Parámetros de conexión via `conn_params: dict`; usa `build_conn_params()` para normalizar.
- Cierres explícitos: llama siempre a `manager.close()` o usa el manager como context manager.
- Pool habilitado por defecto en ambos managers (`use_pool=True`); desactivable con `use_pool=False`.

### Procesamiento de datos
- Usa `pandas.DataFrame` para operaciones masivas (bulk insert, bulk update, bulk delete).
- Retorna `Rows` (lista de dicts), `Row` (dict) o `RowOrNone` según la cardinalidad esperada.
- Para metadatos, usa `SyncMetadataProvider` / `AsyncMetadataProvider`; no hagas raw SQL de introspección en managers.

### SOLID operativo
- **SRP**: cada servicio tiene una razón de cambio principal.
- **OCP**: nuevas familias de archivos o instrucciones IA deben añadirse con
  generadores o listas de soporte acotadas, sin reescribir el workflow completo.
- **LSP**: cualquier componente inyectado debe respetar el contrato esperado por
  managers y CLIs.
- **ISP**: evita servicios "todo en uno"; prefiere métodos pequeños.
- **DIP**: la orquestación debe depender de servicios claros, no de detalles de IO
  duplicados en varias capas.

### OOP y estado
- Mantén el estilo basado en clases para servicios y CLIs.
- Funciones a nivel de módulo solo para utilidades compartidas pequeñas, como
  `get_logger`.
- Evita estado global mutable.
- Usa `ClassVar` para constantes de clase.

### Logging
- Las clases con lógica deben tener `self.logger: logging.Logger`.
- En servicios (`managers/`, `bulk/`, `metadata/`), pasa logger como parámetro si es necesario.
- En handlers de error inesperado, usa `exc_info=True`.
- Evita `print()` en la librería; solo permitido en scripts de ejemplo/CLI externos.

### Formato de cadenas
- Usa f-strings para strings con parámetros.
- Evita `.format()`, `%` formatting y concatenación para interpolación.
- Strings estáticos, docstrings y ejemplos sin parámetros están permitidos.

---

## Calidad y pruebas

### Comandos de desarrollo

```bash
python -m ruff check src tests
python -m ruff format src tests
python -m mypy src tests/unit/test_protocol_conformance.py   # el segundo verifica Protocols de la Regla #6 (docs/architecture.md)
python -m pytest
python -m build
zensical build        # generador por defecto (CI); lee mkdocs.yml
mkdocs build          # equivalente recíproco con el mismo mkdocs.yml
python scripts/build_docs_zip.py   # build + ZIP offline en dist/util_bbdd-docs-{version}.zip
python scripts/gen_arquitectura_capas.py   # regenera el diagrama de capas e imports (falla si no coincide con el código)
# Onboarding: generar/actualizar guía de incorporación para nuevos desarrolladores
# → aplicar .github/prompts/onboarding_dev.prompt.md → docs/guides/onboarding_dev.md
```

### Estrategia de tests
- Managers y bulk: tests unitarios con SQLite en memoria (`":memory:"`); sin BD externas en CI.
- Metadata, comparar, doc: tests con fixtures de esquemas mock o SQLite.
- No depender de PostgreSQL, Oracle, SQL Server, MariaDB ni HSQLDB reales en tests unitarios.
- Fixtures en `tests/conftest.py` para datos de prueba (DataFrames, esquemas mock).
- Tests de integración opcionales en `tests/integration/` marcados con `pytest.mark.integration`.

### Documentación obligatoria

#### Cuándo es CRÍTICA (bloquea PRs)

- ✅ Nueva clase pública → docstring Google-style + ejemplo
- ✅ Cambio de API pública → actualizar guías en `docs/`
- ✅ Refactor con breaking changes → guía de migración en CHANGELOG.md
- ✅ Antes de cerrar versión → `zensical build` (o `mkdocs build`) sin errores ni links rotos
- ✅ Cambios en instrucciones IA → sincronizar todos los ficheros afectados
- ✅ Nuevo archivo generado o copiado → actualizar README y/o docs de uso
- ✅ Cambio de CLI → actualizar ejemplos en README, `docs/` y `.ai/runtime.md`
- ✅ **Nueva versión (VERSION)** → revisar `.github/instructions/sync.instructions.md`
  para validar que CHANGELOG.md y `pyproject.toml` están sincronizados

#### Configuración de documentación — cuándo actualizar

> **Fuente única**: `mkdocs.yml`. Dos generadores recíprocamente compatibles lo consumen:
> **Zensical** (`zensical serve` / `zensical build`, usado por el CI) y **MkDocs Material**
> (`mkdocs serve` / `mkdocs build`). No se usa `zensical.toml`. Ver `ZENICAL.md`.

- ✅ Módulo o clase pública nueva → entrada en `mkdocs.yml` bajo `nav:`
- ✅ Página nueva, movida o eliminada en `docs/` → actualizar `mkdocs.yml`
- ✅ Reorganización funcional/técnica/ejemplos → validar que `nav:` mantiene apartados separados
- ✅ Ejecutar `zensical serve` (o `mkdocs serve`) localmente antes de publicar
- ✅ Verificar que `zensical build` (o `mkdocs build`) pase sin warnings

#### Convención de nombres en `docs/`

- **Todos los ficheros `.md`** en `docs/` (y subdirectorios) usan nombre **en minúsculas con guiones bajos**: `installation.md`, `async_guide.md`, `migration_guide.md`.
- **Guías** → siempre en `docs/guides/`, nunca en la raíz de `docs/`.
- **Conjunto mínimo obligatorio en `guides/`**: `onboarding_dev.md` + `troubleshooting.md`.
- Sección `Guías:` en `mkdocs.yml`: `onboarding_dev.md` siempre primero; `troubleshooting.md` siempre en subsección "Errores y Diagnóstico".

#### 📦 Distribución de documentación offline

ZIP offline con SHA256 (`scripts/build_docs_zip.py`, plugin `src/util_bbdd/docs_build_plugin.py`),
página `docs/downloads.md` y publicación en GitHub Releases (`.github/workflows/docs-zip-release.yml`).
Uso y comandos: `docs/guides/docs_offline_zip_guide.md`; mantenimiento: `.github/docs-zip-setup-guide.md`.
Traslado a otros proyectos: `bootstrap_ai_config.prompt.md` § «Sección Especial: Descarga de Documentación Offline (Capa B)».

#### Estándar de generación documental

- Usa Zensical (o MkDocs con Material for MkDocs, recíprocamente compatibles) como salida estática de referencia.
- Usa Mermaid.js para diagramas de flujo, secuencia o clases cuando aporte claridad.
- Unifica creación y actualización: busca primero documentación existente y actualízala si es el punto de entrada correcto.
- Para documentación de proyecto completo, revisa README, `docs/`, `docs/examples/`, docstrings públicos, prompts/agentes IA y `mkdocs.yml`.
- Separa claramente documentación funcional, técnica y ejemplos.
- No inventes capacidades, módulos, APIs, salidas, reglas ni dependencias. Si falta información, márcala como pendiente de verificación.
- No uses ejemplos heredados de otros repositorios: valida nombres de proyecto, rutas, clases y tests contra el árbol real antes de documentarlos.
- No uses un único prompt masivo; divide en mapeo funcional, técnica, ejemplos, Mermaid y revisión final.
- Excluye por el momento generación de documentación mediante APIs externas.

#### Diagrama de capas e imports

La figura «Capas e imports reales» de `docs/architecture.md` se genera desde el código; no se edita a mano.

```bash
python scripts/gen_arquitectura_capas.py          # mide imports con ast, verifica el dibujo y reescribe SVG + CSS
python scripts/gen_arquitectura_capas.py --edges  # tabla de imports medida (diagnóstico, no escribe nada)
```

- Ejecútalo si un cambio añade, mueve o elimina un paquete de primer nivel de `src/util_bbdd/` o un import entre ellos.
- Si falla, no escribe nada: el dibujo (`LEVEL`, `DRAWN` y `render_svg()` en el script) ya no coincide con el código. Decide si el import es correcto (actualiza el dibujo) o un error (corrige el código); no fuerces la salida.
- Si pasa, revisa el pie de figura de `docs/architecture.md` (versión, fecha y número de ficheros medidos).
- Guía completa: `docs/guides/architecture_diagram_guide.md`.

#### Estándar: Docstrings Google-style

```python
class SyncDatabaseManager:
    """Manager sincrónico para operaciones de base de datos.

    Gestiona conexión (directa o pooled), introspección de esquemas y
    ejecución de queries para los motores soportados.

    Attributes:
        db_type (str): Tipo de motor declarado en la instancia.
        conn_params (dict): Parámetros de conexión normalizados.

    Example:
        >>> manager = SyncDatabaseManager(
        ...     db_type="postgresql",
        ...     conn_params={"host": "localhost", "database": "mydb", ...}
        ... )
        >>> tables = manager.get_tables()
        >>> manager.close()
    """
```

#### Estándar: Validación de Markdown en documentación

Reglas y errores conocidos (líneas en blanco antes de listas y tablas, viñetas reales, fences
anidados, enlaces a artefactos generados): `.github/instructions/docs.instructions.md` § «Reglas
Markdown (CRÍTICAS)». Validación: `zensical build --strict` (o `python -m mkdocs build --strict`).

### Formato de commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     nueva funcionalidad (dentro de scope, no refactor)
fix:      corrección de bug fuera del flujo /hotfix
hotfix:   corrección urgente P1/P2 del flujo /hotfix (RCA → fix mínimo)
security: remediación de un hallazgo de /security-review
perf:     mejora de rendimiento sin cambio funcional (flujos /performance-audit-*)
refactor: cambio sin impacto funcional
test:     solo tests, sin cambios de funcionalidad
docs:     solo documentación (README, docstrings, guías, configuración IA)
chore:    mantenimiento (deps, config, herramientas)
release:  cierre de versión → «release: vX.Y.Z - <resumen>» (/version-closure)
```

Scope opcional entre paréntesis con el módulo afectado: `fix(dump): …`, `perf(bulk): …`.

**Ejemplo**:
```
feat: añadir soporte para exportación Parquet en bulk/

- Añade bulk_export_to_parquet() en bulk/crud.py
- Tests en tests/unit/bulk/test_export_parquet.py
- Actualiza docstring y ejemplos en docs/api/bulk.md
```

---

## Flujo de trabajo

Para cambios no triviales:

```text
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

Para auditorías o PR reviews, prioriza hallazgos verificables:
- bug o regresión;
- contrato público roto;
- prueba faltante en comportamiento modificado;
- documentación obsoleta que pueda inducir uso incorrecto.

No mezcles feature, hotfix y refactor salvo que el usuario lo pida explícitamente.
Si detectas instrucciones heredadas de otro proyecto, corrígelas o márcalas como
deuda técnica con ruta exacta.

### Directrices para Futuras IAs — sección obligatoria en VERSION

Cuando cierres una sesión (fase VERSION o `/version-closure`), puebla la sección
`## Directrices para Futuras IAs` del `TRACEABILITY.md` de la sesión con los hechos
descubiertos que una IA futura necesitaría para no repetir análisis:

- Puntos canónicos (módulo/archivo) que centralizan una responsabilidad.
- Decisiones de diseño tomadas y su justificación breve.
- Patrones con nombre (alias P-A, re-exportadores, etc.) establecidos en la sesión.
- Lecciones aprendidas de herramientas o técnicas (p.ej. cobertura de `oldString`).

Usar formato: `**[área]**: <hecho verificable>`. El template está en
`.ai/sessions/TEMPLATE/TRACEABILITY.md`.

---

## Gobernanza de plataformas IA

| Archivo | Plataforma | Propósito |
|---|---|---|
| `.github/SHARED_INSTRUCTIONS.md` | Copilot, Claude, Gemini, Codex, Cursor | Fuente canónica: arquitectura, calidad, comandos, documentación |
| `CLAUDE.md` | Claude Code | Especialización: slash commands, hooks, settings.json (importa SHARED con `@`) |
| `.github/copilot-instructions.md` | GitHub Copilot Chat | Especialización: agentes VS Code, reglas Copilot |
| `GEMINI.md` | Gemini Code Assist | Especialización: flujo y comandos rápidos |
| `.cursorrules` | Cursor | Especialización: estándar de ejemplos de código (snippets) |
| `AGENTS.md` (raíz) | Codex | Especialización: entry point fino; guía en `docs/guides/codex_guide.md` |
| `.github/AGENTS.md` | Todas | Registro de agentes, prompts y slash commands |
| `.github/DOCUMENTATION_STANDARD.md` | Todas | Canónico documental: arquetipos y flujo de agentes de documentación |
| `.github/instructions/*.instructions.md` | Copilot (por ruta); resto por referencia | Reglas por tipo de archivo |
| `.github/prompts/bootstrap_ai_config.prompt.md` | Todas | Trasladar esta configuración IA a otro proyecto (modelo PULL) |
| `.ai/*.md` | Todas | Contexto persistente: producto, arquitectura |
| `.ai/sessions/TEMPLATE/` | Todas | Plantilla canónica de artefactos de sesión |

**Regla de oro**: Edita SHARED_INSTRUCTIONS.md primero. Luego sincroniza solo las
especializaciones afectadas (`CLAUDE.md`, `.github/copilot-instructions.md`, `GEMINI.md`,
`.cursorrules`, `AGENTS.md`) y, si cambian agentes, prompts o slash commands, `.github/AGENTS.md`.

**Checklist de sincronización** (único; los entry points remiten aquí):

- [ ] Ninguna regla común está copiada en un entry point: solo referencias de una línea a este fichero
- [ ] Rutas relativas y existentes (enlaces resueltos desde la carpeta del fichero que los contiene)
- [ ] Sin términos, módulos ni rutas de otros proyectos
- [ ] Tabla de gobernanza actualizada y fechas «Actualizado» al día en los ficheros tocados
- [ ] Revisión con Config Reviewer (`/config-review` en Claude Code)

---

*Actualizado: 2026-09-25*
