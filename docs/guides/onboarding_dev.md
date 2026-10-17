# util_bbdd — Guía de Incorporación para Desarrolladores

**Audiencia**: desarrolladores Python que contribuyen o extienden la librería  
**Tiempo estimado**: 20–40 minutos para tener el entorno operativo

---

## 1. Prerequisitos del Entorno

| Herramienta | Versión mínima | Verificar con | Notas |
|---|---|---|---|
| Python | 3.12 | `python --version` | 3.12, 3.13 o 3.14 soportados. En Windows: `py --version` |
| Git | 2.x | `git --version` | Necesario para clonar y gestionar ramas |
| pip | 23.x | `pip --version` | Incluido con Python 3.12+ |
| Acceso a GitHub | — | `git ls-remote https://github.com/fmanza/util.git HEAD` | Requerido para la dependencia privada `util` (ver §4) |
| Graphviz (binario `dot`) | — | `dot -V` | **Opcional** — solo para `analysis/` (grafos). El paquete Python `graphviz>=0.20` va en el extra `.[analysis]` |

> **Sin Docker ni BD externa**: los tests unitarios usan SQLite en memoria (`:memory:`) y corren sin servicios externos. Los de integración contra motores reales se saltan si no hay URLs del banco (ver §8 › Tests).

---

## 2. Obtener el Código

```bash
# Clonar el repositorio
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd

# Cambiar a la rama principal de desarrollo
git checkout develop
```

**Dependencia privada `util`**: `pyproject.toml` declara `util @ git+https://github.com/fmanza/util.git@develop`. Para instalarla, pip necesita acceso de lectura a `fmanza/util` en GitHub.

```bash
# Verificar acceso (HTTPS con token o SSH configurado)
git ls-remote https://github.com/fmanza/util.git HEAD

# Si usas SSH
ssh -T git@github.com
```

Si el acceso falla, solicita permiso al propietario del repositorio o configura un token personal de GitHub con scope `repo`.

---

## 3. Configurar el Entorno de Desarrollo

```bash
# 1. Crear entorno virtual (recomendado — aísla las dependencias del sistema)
python -m venv venv

# 2. Activar el entorno virtual
#    Windows (PowerShell): si el script se bloquea (política "Restricted" por defecto), ejecuta antes:
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
#    Linux / macOS
source venv/bin/activate

# 3. Actualizar pip
python -m pip install --upgrade pip
```

No se requieren ficheros `.env` ni credenciales locales para el entorno de desarrollo básico. Para documentación local añade el extra `docs` (ver §4).

---

## 4. Primera Instalación de Dependencias

```bash
# Instalar la librería + dependencias de desarrollo (modo editable)
pip install -e ".[dev]"
```

El flag `-e` instala en modo editable: los cambios en `src/` se reflejan sin reinstalar.

**Extras disponibles**:

| Extra | Comando | Incluye |
|---|---|---|
| Desarrollo | `pip install -e ".[dev]"` | pytest, pytest-cov, pytest-asyncio, aiosqlite, ruff, mypy, build, stubs de tipos (pandas, networkx, PyMySQL, openpyxl), sqlglot, psycopg2-binary, black, isort |
| Documentación | `pip install -e ".[docs]"` | zensical, mkdocs-material, mkdocstrings |
| Drivers por motor | `pip install -e ".[postgresql]"` / `".[mariadb]"` / `".[mysql]"` | psycopg 3 + psycopg-pool + asyncpg / mariadb + aiomysql / pymysql + aiomysql |
| Migración DDL (vistas) | `pip install -e ".[migrate]"` | sqlglot |
| Grafos (Graphviz) | `pip install -e ".[analysis]"` | graphviz >= 0.20 |
| Grafos (Matplotlib) | `pip install -e ".[analysis-matplotlib]"` | matplotlib, networkx |
| SVG→PNG en Word | `pip install -e ".[doc-svg]"` | cairosvg >= 2.7 |
| Entorno de referencia | `pip install -e ".[dev,docs]"` | El que usan los recuentos de tests y mypy (`SHARED_INSTRUCTIONS.md`) |

**Errores frecuentes en la instalación**:

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `ERROR: Could not find a version that satisfies the requirement util` | Sin acceso al repositorio privado `fmanza/util` | Configurar token HTTPS (`GH_TOKEN`) o clave SSH para GitHub |
| `Could not build wheels for util` | pip no puede resolver el VCS dependency | Usar `pip install --upgrade pip` y asegurar Git en PATH |
| `ModuleNotFoundError: No module named 'aiosqlite'` | Solo se instaló `pip install -e .` sin extras | Reinstalar con `pip install -e ".[dev]"` |
| Error de SSL / proxy corporativo | Proxy bloqueando PyPI o GitHub | `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[dev]"` |
| `oracledb: failed to load native libraries` | Modo thick intentado sin Oracle Instant Client | util_bbdd usa thin mode por defecto; sin Instant Client es suficiente |

---

## 5. Infraestructura Local (Base de Datos / Servicios)

*No aplica para el desarrollo básico — los tests unitarios usan SQLite en memoria (`:memory:`); no se requiere base de datos, contenedor Docker ni ningún servicio externo. Para los tests de integración y los benchmarks contra motores reales hay un banco de contenedores opcional: `scripts/bench_env.example.sh` (o `.ps1`) exporta sus URLs.*

---

## 6. Ejecutar la Aplicación en Local

*No aplica para este proyecto — es una librería Python, no una aplicación con servidor. Para verificar que funciona, ejecuta los tests (ver §10) o importa el paquete en un script:*

```python
from util_bbdd import SyncDatabaseManager

# SQLite en memoria: cero configuración, cero dependencias externas
manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"},
    use_pool=False,
)
print(manager.get_tables())  # []
manager.close()
```

---

## 7. Mapa del Código

El código fuente está en `src/util_bbdd/` con una **arquitectura de 3 niveles**. Las dependencias fluyen hacia abajo: cada nivel se divide en capas numeradas y un paquete importa solo de paquetes de capas de número menor (Level 3 de Level 2, de Level 1 y de las capas inferiores de Level 3; Level 2 de Level 1 y de las capas inferiores de Level 2). La tabla de capas está en `.ai/architecture.md` § Capas.

```
src/util_bbdd/
│
│  # ── Level 1: Abstracciones internas (Foundation) ──────────────────────
├── _core/              # Jerarquía canónica de excepciones (DatabaseException raíz)
├── _drivers/           # Detección de drivers instalados y validación de motores
├── core/               # capabilities.py — capacidades por motor (async, features)
│
│  # ── Level 2: Capas de acceso (Services) ─────────────────────────────
├── audit/              # Auditoría común de bulk, dump y migrate (AuditEvent, AuditSink, CSV heredado)
├── connection/         # build_conn_params(); adaptadores y pools por motor
├── executors/          # Ejecutores sync y async (SyncQueryExecutor, AsyncQueryExecutor)
├── factory/            # SQLAlchemy engine factory (sync/async)
├── metadata/           # Introspección de esquemas (tablas, columnas, DDL, caché)
├── query/              # QueryRegistry, QueryResolver — queries nombradas en JSON
├── results/            # Tipos de retorno: Row, Rows, RowOrNone
├── validators/         # Validación de parámetros de queries antes de ejecución
│
│  # ── Level 3: Especialización (Domain Logic) ─────────────────────────
├── managers/           # API pública: SyncDatabaseManager, AsyncDatabaseManager
├── bulk/               # CRUD masivo desde DataFrame; AuditManager
├── analysis/           # Grafos de relaciones entre tablas (Graphviz)
├── comparar/           # SchemaComparator, SchemaDiff, reporters (SQL/HTML/Word/Excel/MD)
├── doc/                # Generación de documentación de BD (HTML, Word, Excel, Jinja2)
├── dump/               # DumpOrchestrator — volcado de datos entre esquemas/motores
├── migrate/            # MigrationPlanner — migración DDL entre motores
│
│  # ── Módulos raíz ─────────────────────────────────────────────────────
├── __init__.py         # API pública canónica — punto de entrada recomendado (13 símbolos)
├── exceptions.py       # Módulo público de excepciones (re-exporta _core/exceptions.py)
├── async_utils.py      # maybe_await() — helper transparente sync/async
├── models.py           # Modelos de datos compartidos
├── docs_build_plugin.py  # Plugin de build de la documentación (ZIP offline)
└── data/               # database_types.json, sql_queries.json (datos empaquetados)
```

**Regla de imports crítica**: Level 2 NO importa de Level 3; Level 1 NO importa de Level 2 ni Level 3; un paquete importa solo de capas de número menor y los de una misma capa son independientes (lo vigila `tests/unit/test_architecture_import_rules.py`). `async_utils.py` y `models.py` cuentan como Level 1: no importan nada de la librería. El punto de entrada recomendado para código externo es `from util_bbdd import <Clase>`.

**Dónde mirar primero según la tarea**:

| Tarea | Empezar por |
|---|---|
| Añadir soporte para un nuevo motor | `connection/<motor>/`, `metadata/<motor>/`, `validators/<motor>_validator.py` |
| Modificar CRUD masivo | `bulk/crud.py`, `bulk/_execution/` |
| Nuevo formato de reporte de comparación | `comparar/reporters/` |
| Nueva sección en documentación de BD generada | `doc/infrastructure/renderers/`, `doc/templates/` |
| Añadir query nombrada | Fichero JSON propio (`queries_file`); el empaquetado `data/sql_queries.json` está vacío desde ADR-003 |
| Cambiar comportamiento de conexión | `connection/`, `factory/` |

---

## 8. Convenciones y Herramientas de Calidad

Todas las convenciones están configuradas en `pyproject.toml`. No uses opciones ni flags fuera de los listados aquí.

### Formato de código

```bash
# Aplicar formato automáticamente (compatible Black, line-length=120, quotes dobles)
python -m ruff format src tests
```

### Lint

```bash
# Verificar errores de lint (reglas: E, W, F, I, B, C4, UP — E501 ignorado)
python -m ruff check src tests

# Aplicar correcciones automáticas donde sea posible
python -m ruff check src tests --fix
```

### Type-checking

```bash
# Verificar tipos estáticos
python -m mypy src tests/unit/test_protocol_conformance.py
```

Configurado en `pyproject.toml [tool.mypy]`: Python 3.12, `warn_return_any`, `check_untyped_defs`. Los drivers externos (oracledb, openpyxl, psycopg, asyncpg, etc.) tienen `ignore_missing_imports = true`; `docs_build_plugin.py` (plugin de MkDocs) está excluido. El segundo argumento verifica, con firmas incluidas, que las implementaciones reales cumplen los Protocols que sustituyen a un import de capa superior (Regla #6, `docs/architecture.md`); `mypy src` por sí solo no lo cubre.

### Tests

```bash
# Suite completa (sin BD externas — SQLite en memoria)
python -m pytest

# Con informe de cobertura HTML
python -m pytest tests/ --cov=src/util_bbdd --cov-report=html
# Informe generado en: htmlcov/index.html

# Módulo concreto
python -m pytest tests/unit/bulk/ -v
```

Tests de integración (que sí requieren BD reales) están en `tests/integration/`, marcados con `pytest.mark.integration`; sin las URLs del banco se saltan. En CI corren en el workflow `integration.yml` (nocturno y manual), no en el de cada push. Para ejecutarlos en local: `source scripts/bench_env.example.sh` (con `UTIL_BBDD_BENCH_PASSWORD` definida) y `python -m pytest`. Los de HSQLDB necesitan además Java: define `JAVA_HOME` (el cliente JDBC lo usa para arrancar la JVM).

Los ejemplos de `docs/examples/` también se ejecutan en los tests (`tests/unit/test_docs_examples.py` y, contra el banco, `tests/integration/test_docs_examples_engines.py`): un cambio de API que rompa un ejemplo hace fallar la suite.

### Docstrings

Google-style obligatorio en clases y métodos públicos:

```python
def contar_filas(self, tabla: str, schema: str | None = None) -> int:
    """Cuenta las filas de una tabla.

    Args:
        tabla: Nombre de la tabla.
        schema: Nombre del esquema. Si None, usa el esquema por defecto.

    Returns:
        Número de filas.
    """
```

### Conventional Commits

```
feat:     nueva funcionalidad
fix:      corrección de bug
hotfix:   corrección urgente P1/P2 (flujo /hotfix)
security: remediación de un hallazgo de seguridad
perf:     mejora de rendimiento sin cambio funcional
refactor: cambio sin impacto funcional
test:     solo tests
docs:     solo documentación
chore:    mantenimiento (deps, config, herramientas)
release:  cierre de versión (release: vX.Y.Z - <resumen>)
```

Scope opcional con el módulo: `fix(dump): …`. Lista canónica: `.github/SHARED_INSTRUCTIONS.md` § «Formato de commits».

---

## 9. Flujo de Trabajo Git

### Estrategia de ramas

| Rama | Propósito |
|---|---|
| `main` | Releases estables — no se trabaja directamente aquí |
| `develop` | Integración continua — **rama base para todos los PRs** |
| `feat/<nombre>` | Nueva funcionalidad |
| `hotfix/<descripcion>` | Fix urgente |
| `refactor/<area>` | Refactor sin cambio funcional |

### Flujo estándar para una feature

```bash
# 1. Partir desde develop actualizado
git checkout develop
git pull origin develop

# 2. Crear rama de feature
git checkout -b feat/nombre-funcionalidad

# 3. Desarrollar, formatear y verificar antes de cada commit
python -m ruff format src tests
python -m ruff check src tests
python -m pytest -q

# 4. Commitear con Conventional Commits
git commit -m "feat: descripción concisa del cambio"

# 5. Push y abrir PR hacia develop
git push origin feat/nombre-funcionalidad
```

### Flujo para cambios no triviales

El proyecto usa un ciclo estructurado con asistentes IA (ver `CLAUDE.md`):

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

### Checklist pre-PR

```bash
python -m ruff format src tests    # Sin cambios pendientes
python -m ruff check src tests     # Sin errores de lint
python -m mypy src tests/unit/test_protocol_conformance.py   # Sin errores de tipos
python -m pytest -q                # Suite completa sin fallos
```

---

## 10. Verificación del Entorno

Ejecuta estos comandos en orden. Si todos producen el output esperado, el entorno está completamente operativo.

| Verificación | Comando | Output esperado |
|---|---|---|
| Python versión correcta | `python --version` | `Python 3.12.x` (o 3.13 / 3.14) |
| Paquete instalado | `python -c "from importlib.metadata import version; print(version('util_bbdd'))"` | La versión de `pyproject.toml` (p. ej. `3.0.3`) |
| Manager sync funciona | `python -c "from util_bbdd import SyncDatabaseManager; m = SyncDatabaseManager(db_type='sqlite', conn_params={'database': ':memory:'}); print(m.get_tables()); m.close()"` | `[]` |
| ruff sin errores | `python -m ruff check src tests` | Sin output (sin errores) |
| mypy sin errores | `python -m mypy src tests/unit/test_protocol_conformance.py` | `Success: no issues found in N source files` |
| Tests pasan | `python -m pytest -q` | `N passed` sin fallos |

### Verificación rápida en una línea

```bash
python -m ruff check src tests && python -m mypy src tests/unit/test_protocol_conformance.py && python -m pytest -q
```

Si este comando termina con código 0 y sin errores, el entorno está operativo.

### Verificación de documentación (opcional — requiere extra `docs`)

```bash
pip install -e ".[docs]"
zensical build --strict   # el del CI; mkdocs build --strict es equivalente
```

Output esperado: `No issues found`.

---

## 11. Recursos y Referencias

### Documentación del proyecto

- [Documentación online](https://fmanza.github.io/util_bbdd/) — generada con Zensical / MkDocs Material
- [Instalación](../installation.md) — guía de instalación completa
- [Arquitectura del sistema](../architecture.md) — arquitectura detallada del sistema
- [Programación asíncrona](async_guide.md) — patrones y drivers async
- [Conexión y Drivers por Motor](connection_guide.md) — conexión por motor y troubleshooting
- [Excepciones](exceptions.md) — jerarquía de excepciones canónica
- [Migración a la API 3.0](api_3_0_migration.md) — de 2.x a 3.0 (opciones de `BulkCrud` y `ParallelBulkLoader` en paquetes)
- [Migración a la API 1.0](api_1_0_migration.md) — de 0.x a 1.0 (imports desde la raíz y submódulos públicos)
- [Guía de Migración v0.6.3](migration_guide.md) — histórica, para código anterior a v0.6.3
- [Ejemplos](../examples/example_connect_introspect.md) — casos de uso por funcionalidad (punto de entrada recomendado para explorar la API)

### Contexto IA del proyecto

Estos ficheros son la fuente canónica para asistentes de código (no están publicados en el sitio; léelos desde el repositorio local):

- `.ai/product.md` — descripción del producto y objetivos
- `.ai/architecture.md` — arquitectura persistente
- `.ai/glossary.md` — glosario de términos técnicos del dominio
- `.github/SHARED_INSTRUCTIONS.md` — reglas canónicas para todos los asistentes IA
- `CLAUDE.md` — slash commands y flujos para Claude Code

### Contribución y reporte de problemas

- [Issues en GitHub](https://github.com/fmanza/util_bbdd/issues) — bugs y feature requests
- Contacto: fmanzano.trabajo@gmail.com

---

*Guía revisada para util_bbdd v3.0.3 · Verificada: 2026-10-17 · Arquetipo 7 — Onboarding Desarrolladores*
