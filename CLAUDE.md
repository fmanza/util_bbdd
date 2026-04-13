# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Rol

Actúa como senior de ingeniería de software especializado en arquitectura Python, APIs sync/async, metadatos multi-motor, generación documental y mantenimiento de librerías.

## Proyecto

`util_bbdd` es una librería Python para **operaciones de base de datos y documentación automática** (MariaDB, Oracle, PostgreSQL, SQLite, SQL Server, HSQLDB). Requiere Python 3.12+. Versión en desarrollo: `0.6.7.dev0`.

Funcionalidades principales:
- CRUD masivo desde DataFrames con auditoría CSV
- Introspección de metadatos: schemas, tablas, columnas, PK/FK, índices
- Generación de documentación (Word, Excel, Markdown, HTML con Jinja2)
- Análisis de relaciones y grafos multinivel
- Gestión de conexiones con pool singleton, soporte async por motor

---

## Comandos de desarrollo

```bash
python -m ruff check src tests       # lint
python -m ruff format src tests      # format
python -m mypy src                   # type-check
python -m pytest                     # all tests
python -m pytest tests/path/test_x.py::TestClass::test_name  # single test
python -m build                      # build package
```

---

## Arquitectura (3 niveles)

```
src/util_bbdd/
  # ── Level 1: Foundation ────────────────────────────────────────────────
  _core/           # Tipos base, excepciones (DatabaseException y derivadas), contratos (Protocols/ABC), constantes
  core/            # Capacidades por motor (capabilities.py) — detecta soporte async y features

  # ── Level 1 support (no importar desde Level 2+) ──────────────────────
  _drivers/        # Implementación canónica de validators y driver checking
                   #   validator.py         — DatabaseTypeValidator: valida motores desde database_types.json
                   #   driver_validator.py  — DriverValidator: detecta disponibilidad de drivers Python
                   #   _config_loader.py    — carga y tipado del JSON de configuración de motores

  # ── Level 2: Services ──────────────────────────────────────────────────
  connection/      # Pool singleton, factory, configuración; motors/ con adaptadores por motor
  query/           # registry, resolver, DatabaseQueries (wrapper de conveniencia multi-motor)
  executors/       # QueryExecutorBase (abstract), sync_query_executor, async_query_executor
  metadata/        # fetcher → normalizer → builder → cache → manager; providers sync/async; mariadb/
  results/         # tipos (RowOrNone, Rows) y normalización de respuestas
  factory/         # pool_factory, sqlalchemy_engine_factory, async_sqlalchemy_engine_factory
  validators/      # validadores adicionales

  # ── Level 3: Specialization ────────────────────────────────────────────
  bulk/            # CRUD masivo (crud.py), auditoría (audit.py), normalización SQL
  analysis/        # grafos multinivel (base.py, graphviz.py, graphviz_ext.py, matplotlib_graph.py)
  comparar/        # comparación motor-agnóstica de esquemas vía SQLAlchemy Inspector
                   # SchemaComparator.compare(source, target) → SchemaDiff (frozen dataclasses)
                   # Extensible vía _ROUTINE_FETCHERS y _DDL_STRIP_RULES (OCP)
  doc/             # generadores HTML/Excel/Word + plantillas Jinja2 en templates/
  managers/        # SyncDatabaseManager y AsyncDatabaseManager (APIs públicas de alto nivel)
```

**Regla de imports:** el flujo va siempre Level 1 → 2 → 3; nunca al revés.

Para agregar un motor nuevo: añadir un archivo en `connection/motors/` sin tocar los flujos base.

### Async por motor

PostgreSQL, SQLite, MariaDB, Oracle y SQL Server tienen soporte async. HSQLDB es sync-only; las factorías async lanzan error explícito.

---

## Reglas críticas

### Multibase
- No asumir un único motor. SQL crudo solo en adaptadores aislados por motor (p.ej. `motors/postgres.py`).
- No inventar metadatos: obtenerlos por introspección o recibirlos como parámetro.

### SOLID operativo
- **SRP**: separa extracción, normalización, render y persistencia.
- **OCP**: nuevo motor/formato → adaptador nuevo, sin editar flujos base.
- **LSP**: implementaciones sync/async y por motor deben respetar contratos comunes y semántica de errores.
- **ISP**: interfaces pequeñas por responsabilidad; evitar contratos todo-en-uno para introspección y render.
- **DIP**: la orquestación depende de `Protocol`/`ABC` y factorías, no de implementaciones concretas.

### Patrones aplicados en esta librería
`Strategy` (variación por motor/formato) · `Abstract Factory` (conexiones) · `Adapter` (diferencias de driver) · `Template Method` (flujo base con hooks) · `Facade` (orquestación en managers) · `Builder` (documentos complejos) · `Identity Map` (caché de metadatos dentro de una ejecución)

### Anti-patrones a evitar
- God class que mezcle conexión, introspección, normalización y render.
- `if/elif` por motor distribuidos fuera de los adaptadores.
- Excepciones genéricas (`Exception`); usar jerarquía de `_core/exceptions.py`.

---

## Flujo de trabajo

**Secuencia obligatoria para cambios no triviales:**

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

Nunca empieces por código si no se ha definido el objetivo.

### Políticas por tipo de tarea

| Tarea | Política |
|---|---|
| `new_feature` | Prohibido refactorizar |
| `hotfix` | Solo fix mínimo. Prohibido refactorizar y optimizar |
| `refactor` | Sin cambios funcionales. API pública estable salvo justificación explícita |
| `security_review` | Hallazgos verificables, ordenados por severidad, con remediación accionable |

### Slash commands disponibles

Usa estos comandos para activar el flujo estructurado correspondiente:

- `/new-feature` — nueva funcionalidad
- `/hotfix` — corrección acotada
- `/refactor` — refactor sin cambio funcional
- `/audit-code` — auditoría técnica
- `/security-review` — revisión de seguridad
- `/tech-debt` — inventario de deuda técnica
- `/maturity-assessment` — evaluación de madurez del repositorio
- `/version-closure` — cierre de versión

---

## Quality bar

- Toda propuesta indica archivos afectados.
- Toda implementación incluye estrategia de pruebas.
- Toda auditoría emite veredicto.
- Toda incertidumbre queda etiquetada como supuesto o dato faltante.
- Toda propuesta de arquitectura declara impacto en SOLID y justifica el patrón aplicado.

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

## Contexto adicional

### Configuración de Claude Code
- Configuración: [`.claude/README.md`](.claude/README.md) — hooks, settings.json, settings.local.json
- Slash commands: [`.claude/commands/`](.claude/commands/) — 8 flujos especializados
- Equivalencia Copilot Chat: [`docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md`](docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md)

### Documentación del proyecto
- Instrucciones detalladas (SOLID, patrones, estilo): [`.github/copilot-instructions.md`](.github/copilot-instructions.md)
- Arquitectura extendida: [`.ai/architecture.md`](.ai/architecture.md)
- Sesiones y decisiones previas: [`.ai/sessions/`](.ai/sessions/)
- Instrucciones por área: [`.github/instructions/`](.github/instructions/) (python, architecture, tests, render, introspection)
- Guía de uso de Claude Code: [`docs/examples/claude_code_usage_complete_example.md`](docs/examples/claude_code_usage_complete_example.md)

### Plan de Mejora v0.6.7
- Índice general: [`docs/v0.6.7/INDEX.md`](docs/v0.6.7/INDEX.md)
- Plan detallado: [`docs/v0.6.7/CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md`](docs/v0.6.7/CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md)
- Resumen ejecutivo: [`docs/v0.6.7/EXECUTIVE_SUMMARY.md`](docs/v0.6.7/EXECUTIVE_SUMMARY.md)
- Checklist de implementación: [`docs/v0.6.7/IMPLEMENTATION_CHECKLIST.md`](docs/v0.6.7/IMPLEMENTATION_CHECKLIST.md)

### Gobernanza de Plataformas Duales
- Integración Claude Code ↔ Copilot Chat: [`.github/INTEGRATION_MAP.md`](.github/INTEGRATION_MAP.md) — gobernanza, sincronización, responsables
- Registro de agentes: [`.github/AGENTS.md`](.github/AGENTS.md) — 10 agentes disponibles, herramientas, flujos y matriz de relaciones
- Guía Documentation Reviewer: [`docs/DOCUMENTATION_REVIEWER_GUIDE.md`](docs/DOCUMENTATION_REVIEWER_GUIDE.md) — cuándo y cómo invocar auditoría documental

---

## Ejecución Offline

### Propósito

Documentar qué comandos y flujos de Claude Code funcionan **sin acceso a internet** y cuáles requieren conexión. Esencial para trabajo en:
- Máquinas sin internet
- CI/CD local (GitHub Actions emulado)
- Entornos restringidos (corporativo, airgap)

---

### Qué Funciona Offline ✅

**Herramientas locales (no requieren internet):**
- ✅ `ruff check src tests` — lint (dependencias instaladas localmente)
- ✅ `ruff format src tests` — format automático
- ✅ `mypy src` — type-checking (SQLAlchemy type stubs necesarios pero locales)
- ✅ `pytest tests/` — ejecución de tests unitarios e integración (con SQLite `:memory:`)
- ✅ `python -m build` — build del paquete

**Flujos de Claude Code sin dependencias externas:**
- ✅ `/hotfix` — análisis local, puede ejecutar ruff/mypy/pytest post-fix
- ✅ `/refactor` — análisis local, validación local
- ✅ `/audit-code` — análisis estático local (sin SonarQube)
- ✅ `/tech-debt` — clasificación local, sin APIs externas

**Comandos de desarrollo (CLI local):**
```bash
python -m ruff check src tests --quiet                           # offline ✅
python -m mypy src --no-error-summary                            # offline ✅
python -m pytest tests/ -q                                       # offline ✅ (SQLite local)
python -m pytest tests/ --cov=src --cov-report=term-missing     # offline ✅
python -m build                                                  # offline ✅
```

---

### Qué Requiere Internet ❌

**Servicios/APIs externos:**
- ❌ `GitHub search` — para encontrar issues/PRs relevantes (requiere API GitHub)
- ❌ `SonarQube` — análisis de seguridad + cobertura remote
- ❌ `GitHub Copilot Chat` (`@copilot`) — integración online de Copilot
- ❌ Descargas de dependencias nuevas (`pip install`) — requiere PyPI o índice custom
- ❌ Conexiones a BDs remotas (PostgreSQL remoto, Oracle remoto, etc.)

**Flujos que necesitan acceso:**
- ❌ `/security-review` — si incluye SonarQube (puede degenedar a análisis local)
- ❌ `/maturity-assessment` — si busca issues/PRs abiertos (puede usar snapshot local)

---

### Modo Offline: Configuración

#### Opción 1: Desabilitar Hooks Lentos (recomendado)

Crea `.claude/settings.local.json` en tu máquina (ignored en `.gitignore`):

```json
{
  "PostToolUse": [
    {
      "description": "ruff check (obligatorio)",
      "command": "python -m ruff check src tests --quiet",
      "optional": false
    }
  ]
}
```

Esto desabilita `mypy` y `pytest --collect-only` que podrían ralentizar sesión offline.

**Verificación:**
```bash
cat .claude/settings.local.json
# Debe listar solo ruff como obligatorio
```

#### Opción 2: Ejecutar Comandos sin Hooks

Si no quieres editar settings.json, simplemente no invoques comandos que necesiten internet:

**SÍ usar offline:**
- `/hotfix` — análisis local + local fix
- `/refactor` — análisis local + local changes
- `/audit-code` — análisis estático local

**NO usar offline (requieren internet o degradarán):**
- `/security-review` — requiere SonarQube (si falla, desabilitar en settings.local.json)
- `/maturity-assessment` — busca issues (puede omitirlo)

#### Opción 3: Fallback para Tools Faltantes

Si una herramienta no funciona offline (p.ej., SonarQube), Claude Code reportará error. Alternativa:

```json
{
  "PostToolUse": [
    {
      "description": "ruff check",
      "command": "python -m ruff check src tests --quiet 2>&1 || true",
      "optional": true
    }
  ]
}
```

La parte `|| true` ignora fallos (no bloquea sesión si herramienta no está disponible).

---

### Ejemplo: Sesión Offline Completa

**Escenario**: Estásdev en avión sin WiFi, quieres hacer `/hotfix` rápido.

**Step 1: Preparar configuración local**
```bash
# Crear settings local
cat > .claude/settings.local.json <<EOF
{
  "PostToolUse": [
    {
      "description": "ruff check",
      "command": "python -m ruff check src tests --quiet",
      "optional": false
    }
  ]
}
EOF
```

**Step 2: Ejecutar  `/hotfix` sin internet**
```text
/hotfix

Bug: ConnectionPool no recicla conexiones después de timeout
Rutas: src/util_bbdd/connection/pool.py, tests/integration/test_pool_recycling.py
```

Claude Code:
1. ✅ Lee el input (offline)
2. ✅ Emite PLAN (análisis local)
3. ✅ Emite AUDIT_PLAN (evaluación local)
4. ✅ Ejecuta `ruff check` (hook local)
5. ✅ Emite IMPLEMENT (cambios propuestos)
6. ✅ Ejecuta `ruff check` nuevamente
7. ✅ Emite AUDIT_CODE (análisis local)
8. ✅ Emite VERSION (commit message)

**Result**: Hotfix completado offline, sin internet.

**Step 3: Limpiar config local**
```bash
rm .claude/settings.local.json  # O dejar para futuras sesiones offline
```

---

### Limitaciones Conocidas Offline

1. **GitHub search no disponible** → No puedes buscar related issues. Workaround: busca localmente en `.ai/sessions/` o docs/
2. **SonarQube no disponible** → `/security-review` se degrada a análisis estático local. Workaround: usar `/audit-code` instead.
3. **PyPI no accesible** → No puedes descargar deps nuevas. Workaround: pre-instala en venv preparado.
4. **Copilot Chat offline** → No funciona Copilot Chat offline (requiere API). Claude Code SÍ funciona offline.

---

### Monitorización: Detectar Dependencias Externas

Si necesitas auditar qué comandos o hooks requieren internet:

```bash
# Revisar settings.json
cat .claude/settings.json | grep -i "github\|sonar\|pypi\|api"

# Revisar comandos específicos
grep -r "github.*search\|sonarqube" .claude/commands/

# Revisar en código fuente
grep -r "requests\|urllib\|httpx" src/ | head -10
```

Si encuentras dependencia externa nueva, agregar a sección "Qué requiere internet" de este archivo.

---

### Referencias

- [`.claude/README.md`](.claude/README.md) — Configuración de hooks (settings.json, settings.local.json)
- [`.claude/TESTING_GUIDE.md`](.claude/TESTING_GUIDE.md) — Cómo correr tests offline determinísticamente
- [`.github/INTEGRATION_MAP.md`](.github/INTEGRATION_MAP.md) — Gobernanza entre plataformas
