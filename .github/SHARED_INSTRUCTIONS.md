# Instrucciones Compartidas: Copilot Chat + Claude Code

Configuración unificada de arquitectura y flujos para ambas plataformas.
Cada plataforma especializa según contexto (agentes, hooks, offline).

---

## Rol esperado

Actúa como senior de ingeniería de software especializado en:
- Arquitectura Python multibase
- Refactors sin duplicación
- Diseño de APIs sync/async
- Testing con pytest sin servicios externos
- Metadatos multi-motor
- Generación documental y mantenimiento de librerías

---

## Proyecto: util_bbdd

Librería Python para **operaciones de base de datos y documentación automática**.

**Motores soportados**: MariaDB, Oracle, PostgreSQL, SQLite, SQL Server, HSQLDB
**Requisitos**: Python 3.12+
**Versión actual**: 0.6.7.dev0

### Funcionalidades principales
- CRUD masivo desde DataFrames con auditoría CSV
- Introspección de metadatos: schemas, tablas, columnas, PK/FK, índices, vistas
- Generación de documentación: Word, Excel, Markdown (portable, Mermaid-compatible), HTML/Jinja2
- Análisis de relaciones y grafos multinivel
- Gestión de conexiones con pool singleton, soporte async por motor
- Comparativa de esquemas y generación de instrucciones SQL para nivelación

---

## Arquitectura (3 niveles)

```
src/util_bbdd/
  # ── Level 1: Foundation ────────────────────────────────────────────────
  _core/           # Tipos base, excepciones, contratos (Protocols/ABC), constantes
  core/            # Capacidades por motor — detecta soporte async y features

  # ── Level 1 support (no importar desde Level 2+) ──────────────────────
  _drivers/        # Validators y driver checking
                   #   validator.py         — DatabaseTypeValidator
                   #   driver_validator.py  — DriverValidator
                   #   _config_loader.py    — carga JSON de configuración

  # ── Level 2: Services ──────────────────────────────────────────────────
  connection/      # Pool singleton, factory, adaptadores por motor
  query/           # Registry, resolver, DatabaseQueries multi-motor
  executors/       # Ejecutores (base, sync, async)
  metadata/        # Fetcher → normalizer → builder → cache → manager
  results/         # Tipos (RowOrNone, Rows) y normalización
  factory/         # Pool, SQLAlchemy engines (sync/async)
  validators/      # Validadores adicionales

  # ── Level 3: Specialization ────────────────────────────────────────────
  bulk/            # CRUD masivo, auditoría, normalización SQL
  analysis/        # Grafos multinivel (Graphviz, Matplotlib)
  comparar/        # Comparador motor-agnóstico vía SQLAlchemy Inspector
  doc/             # Generadores HTML/Excel/Word + plantillas Jinja2
  managers/        # SyncDatabaseManager, AsyncDatabaseManager (APIs públicas)
```

**Regla de imports:** Level 1 → Level 2 → Level 3; nunca al revés.
**Agregar motor nuevo:** fichero en `connection/motors/` sin tocar flujos base.

---

## Principios fundamentales

### Multibase (CRÍTICO)
- No asumir un único motor: evita SQL específico salvo que esté encapsulado por adaptadores
- SQL "crudo" solo en adaptadores aislados por motor (p.ej. `postgres.py`, `mysql.py`, `sqlite.py`)
- No inventar metadatos: obtenerlos por introspección o recibirlos como parámetro

### SOLID operativo
- **SRP** — cada clase/módulo tiene una razón de cambio dominante; separa extracción, normalización, render, persistencia
- **OCP** — nuevo motor/formato → adaptador nuevo, sin editar flujos base
- **LSP** — implementaciones sync/async y por motor respetan contratos comunes
- **ISP** — interfaces pequeñas por responsabilidad; no contratos todo-en-uno
- **DIP** — orquestación depende de `Protocol`/`ABC` y factorías, no de implementaciones concretas

### Patrones recomendados
- `Strategy` — variación por motor y formato
- `Abstract Factory` / `Factory Method` — creación de conexiones y adaptadores
- `Adapter` — encapsular diferencias entre drivers
- `Template Method` — flujo base con hooks por motor/formato
- `Facade` — entrada simple para orquestar extracción + comparativa + render
- `Builder` — documentos complejos (Word/Excel/HTML/Markdown)
- `Repository` / `Query Object` — encapsular consultas sin filtrar SQL
- `Data Mapper` — mapear filas/tablas a modelos de dominio desacoplados del motor
- `Identity Map` — cache coherente dentro de una ejecución

### OOP obligatorio
- **Diseño exclusivamente con clases.** No crear funciones sueltas a nivel de módulo en ficheros de clase
- Transformaciones sin estado: `@staticmethod` dentro de la clase que las utiliza
- Constantes privadas de una clase: `ClassVar` en la propia clase
- Funciones/constantes a nivel de módulo: solo en ficheros de utilidades genuinamente compartidas (p.ej. `_base.py`)

### Gestión de estado y logging

#### Logging obligatorio en clases
Toda clase con lógica de negocio debe gestionar logging para rastrear estado, eventos de ciclo de vida y errores:

```python
# ✅ CORRECTO: Logger privado en cada clase
import logging

class MyService:
    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def do_something(self, data: dict) -> dict:
        self.logger.debug(f"Iniciando procesamiento con {len(data)} elementos")
        try:
            result = self._compute(data)
            self.logger.info(f"✅ Procesamiento exitoso: {len(result)} resultados")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error durante procesamiento: {e}", exc_info=True)
            raise
```

**Requisitos:**
- Importar `import logging` al inicio del módulo
- Instanciar `self.logger = logging.getLogger(__name__)` en `__init__()` o `__post_init__()` (si dataclass)
- Usar niveles apropiados: `debug()` (rastreo interno), `info()` (eventos normales), `warning()` (anómalos), `error()` (fallos)
- Incluir `exc_info=True` en handlers de error para stack trace completo
- **NO usar**: `print()`, loggers globales sin tipado, setup de logging en librerías

**Para módulos utilities sin clases:**
```python
# ✅ CORRECTO: Logger a nivel de módulo en utils
logger: logging.Logger = logging.getLogger(__name__)

def helper_function(x: int) -> int:
    logger.debug(f"Procesando x={x}")
    return x * 2
```

#### Variables globales: Prohibición de mutable módulo-level
Todas las variables globales DEBEN ser inmutables o pertenecer a clases:

```python
# ✅ PERMITIDO: Constantes inmutables
PARAMETER_PATTERN: str = r"\{(\w+)\}"
DEFAULT_TIMEOUT: int = 30
MAX_RETRIES: int = 3

# ✅ PERMITIDO: ClassVar (pertenecen a la clase)
class ConnectionPool:
    MAX_CONNECTIONS: ClassVar[int] = 10
    _instances: ClassVar[dict[str, ConnectionPool]] = {}

# ✗ PROHIBIDO: Mutable módulo-level
query_cache: dict[str, Any] = {}  # ❌ Global mutable
initialized_loggers: list[str] = []  # ❌ Global mutable
current_config: dict = {}  # ❌ Global mutable

# ✓ CORRECTO: Inyectar en clases o usar factory
class QueryService:
    def __init__(self, cache: dict[str, Any] | None = None):
        self.cache = cache or {}  # Instancia, no global
        self.logger: logging.Logger = logging.getLogger(__name__)
```

**Anti-patrones detectados:**
- Variables globales mutables que cambian estado en runtime
- Singletons implementados vía módulo-level (usar factory pattern explícito instead)
- Lazy loading con asignación global (usar lazy property o factory method)

### Anti-patrones a evitar
- God class que mezcle conexión, introspección, normalización y render
- `if/elif` por motor distribuidos fuera de adaptadores
- Renderizadores acoplados a SQL/driver o a estado de conexión
- Excepciones genéricas (`Exception`); usar jerarquía de `_core/exceptions.py`
- Aplicar patrones por moda sin justificar complejidad
- Funciones sueltas a nivel de módulo en ficheros de clase

### Estilo y calidad
- Tipado completo (typing)
- Docstrings en todo código público
- Excepciones específicas (no genéricas)
- Evitar dependencias nuevas sin justificar
- Nunca credenciales en ejemplos
- Sanitizar/escapar identificadores SQL o usar parametrización

---

## Flujo de trabajo estructurado

**Secuencia obligatoria para cambios no triviales:**

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

**Nunca empieces por código si no se ha definido el objetivo.**

### Políticas por tipo de tarea

| Tarea | Política |
|---|---|
| `new_feature` | Prohibido refactorizar |
| `hotfix` | Solo fix mínimo. Prohibido refactorizar y optimizar |
| `refactor` | Sin cambios funcionales. API pública estable salvo justificación explícita |
| `security_review` | Hallazgos verificables, ordenados por severidad, con remediación accionable |

### Forma de trabajar general
- Devuelve primero PLAN
- Después devuelve AUDIT_PLAN
- Implementa por rutas, módulos, clases o utilidades pequeñas
- No introduzcas conceptos server/client salvo que realmente existan en el repositorio
- Propón tests mínimos cuando el cambio lo requiera (unitarios + integración)
- Señala riesgos: seguridad, validación, migraciones, compatibilidad
- Antes de aplicar backward compatibility, confirmar explícitamente si se mantiene enfoque OO-only
- Evita cambios masivos sin plan y rollback
- Contrasta siempre la solicitud con el código real aportado
- No inventes módulos, clases, endpoints, tests inexistentes
- Si falta contexto crítico, decláralo como supuesto explícito
- No mezcles feature, hotfix y refactor en una sola ejecución
- Si toca arquitectura, justifica patrón elegido y alternativa descartada en PLAN y AUDIT_PLAN

---

## Quality bar

- Toda propuesta indica **archivos afectados**
- Toda implementación incluye **estrategia de pruebas**
- Toda auditoría emite **veredicto explícito**
- Toda incertidumbre queda **etiquetada como supuesto o dato faltante**
- Toda propuesta de arquitectura declara **impacto en SOLID** y justifica el patrón aplicado
- Toda regla aplicada tiene **criterio de entrada/salida** (cuándo usarlo y cuándo no)

---

## Formato de commits

Usar [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     nueva funcionalidad
fix:      corrección de bug
refactor: cambio sin impacto funcional
test:     solo tests
docs:     solo documentación
chore:    mantenimiento (deps, config, CI)
```

---

## Gobernanza de plataformas duales

### Sincronización Copilot Chat ↔ Claude Code

- **SHARED_INSTRUCTIONS.md** ← fuente de verdad para arquitectura, flujos, SOLID, patrones
- **copilot-instructions.md** ← especialización Copilot Chat (agentes, prompts)
- **CLAUDE.md** ← especialización Claude Code (slash commands, offline, settings)

### Referencias clave
- Agentes: [`.github/AGENTS.md`](.github/AGENTS.md) — 11 agentes (Plan Architect, Config Reviewer, etc.)
- Mapeo plataformas: [`.github/INTEGRATION_MAP.md`](.github/INTEGRATION_MAP.md) — gobernanza y sincronización
- Instrucciones por área: [`.github/instructions/`](.github/instructions/)
- Documentación del proyecto: [`docs/v0.6.7/INDEX.md`](docs/v0.6.7/INDEX.md)

---

## Contexto adicional

### Configuración de tools
- **Copilot Chat**: [`.github/copilot-instructions.md`](.github/copilot-instructions.md)
- **Claude Code**: [`CLAUDE.md`](CLAUDE.md), [`.claude/README.md`](.claude/README.md)
- **Prompts**: [`.github/prompts/`](.github/prompts/) — 9 prompts por tipo de tarea

### Documentación y sesiones
- Arquitectura extendida: [`.ai/architecture.md`](.ai/architecture.md)
- Sesiones previas: [`.ai/sessions/`](.ai/sessions/)
- Guía uso Claude Code: [`docs/examples/claude_code_usage_complete_example.md`](docs/examples/claude_code_usage_complete_example.md)
- Plan v0.6.7: [`docs/v0.6.7/CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md`](docs/v0.6.7/CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md)

---

*Actualizado: 2026-04-18 — Config Reviewer audit*
