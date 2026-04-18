# Instrucciones para Claude Code

Este fichero proporciona guía a Claude Code cuando trabaja con código de util_bbdd.

---

## ⚠️ Notas importantes

**Lea primero**: [`.github/SHARED_INSTRUCTIONS.md`](.github/SHARED_INSTRUCTIONS.md) para arquitectura, SOLID, patrones, flujos y políticas comunes a ambas plataformas.

Esta página contiene **solo especificidades de Claude Code**. Todo lo demás está centralizado en SHARED_INSTRUCTIONS.md.

---

## Slash commands disponibles

Usa estos comandos para activar flujos estructurados:

- `/new-feature` — nueva funcionalidad (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)
- `/hotfix` — corrección acotada de bug
- `/refactor` — refactor sin cambios funcionales
- `/audit-code` — auditoría técnica independiente
- `/security-review` — revisión de seguridad
- `/tech-debt` — inventario de deuda técnica
- `/maturity-assessment` — evaluación de madurez del repositorio
- `/version-closure` — cierre de versión y release notes

Detalles: [`.claude/commands/`](.claude/commands/) (8 slash commands especializados).

---

## Configuración de Claude Code

### Hooks y PostToolUse

Lee [`.claude/README.md`](.claude/README.md) para:
- `settings.json` — configuración de hooks (ruff, mypy, pytest)
- `settings.local.json` — personalización local (offline mode, hooks deshabilitados)

### Comandos de desarrollo

```bash
python -m ruff check src tests       # lint
python -m ruff format src tests      # format
python -m mypy src                   # type-check
python -m pytest                     # todos los tests
python -m pytest tests/path/test_x.py::TestClass::test_name  # test específico
python -m build                      # build package
```

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

## Validación local: Logging y Variables Globales

Cuando ejecutes `/hotfix`, `/refactor`, o `/audit-code`:

### Post-fix checklist automático (ruff)

```bash
python -m ruff check src tests --select=ARG,F,E401  # Detecta imports no usados, shadowing
python -m mypy src --strict  # Detecta logger sin tipado
```

### Validación manual recomendada

1. **Logging**: Grep para encontrar clases sin logger
   ```bash
   # Buscar clases que podrían no tener logger
   grep -r "class.*:" src/ --include="*.py" | grep -v "logger"
   ```

2. **Globales mutables**: Detectar lists/dicts globales
   ```bash
   # Encontrar variables mutables a nivel de módulo
   grep -E "^\s*[a-z_]+ = (\[\]|\{\})" src/**/*.py
   ```

### Política de logging por tipo de comando

**En `/hotfix`:**
- **Prohibido refactorizar logging** — solo fix del bug reportado
- **Permitido añadir logging** si es esencial para debug del hotfix específico
- **Requerido loguear** cambios de estado en cache o conexiones afectadas

**En `/refactor`:**
- **Requerido**: Añadir logging a clases nuevas o que lo necesiten
- **Recomendado**: Mejorar nivel de detalle en logging existente
- **Prohibido**: Cambiar lógica de logging central (factory, niveles globales)

**En `/audit-code`:**
- **Verificar**: Cada clase con lógica tiene `self.logger: logging.Logger`
- **Verificar**: Logger instanciado en `__init__` o `__post_init__`
- **Reportar**: Métodos sin logs que deberían tenerlos (mutación de estado)

### Checklist pre-push

Antes de hacer push, valida localmente:

```python
# ✅ Clase correcta
class MyService:
    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def critical_method(self):
        self.logger.info("Iniciando operación crítica")
        try:
            result = self._do_work()
            self.logger.info("✅ Operación completada")
            return result
        except Exception as e:
            self.logger.error("❌ Error en operación", exc_info=True)
            raise

# ✗ Variables globales mutables prohibidas
my_cache: dict = {}  # ❌ No
MY_CACHE: ClassVar[dict] = {}  # ✅ Sí (en clase)
```

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

### Auditar Dependencias Externas

```bash
# Revisar settings.json
cat .claude/settings.json | grep -i "github\|sonar\|pypi\|api"

# Revisar comandos específicos
grep -r "github.*search\|sonarqube" .claude/commands/

# Revisar en código fuente
grep -r "requests\|urllib\|httpx" src/ | head -10
```

---

## Gobernanza de plataformas duales

### Sincronización Copilot Chat ↔ Claude Code

- **SHARED_INSTRUCTIONS.md** ← fuente de verdad para arquitectura, flujos, SOLID
- **copilot-instructions.md** ← especialización Copilot Chat
- **CLAUDE.md** ← especialización Claude Code

### Referencias clave
- Agentes: [`.github/AGENTS.md`](.github/AGENTS.md)
- Integración: [`.github/INTEGRATION_MAP.md`](.github/INTEGRATION_MAP.md)
- Configuración local: [`.claude/README.md`](.claude/README.md)
- Guía completa: [`docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md`](docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md)

---

*Actualizado: 2026-04-18 — Config Reviewer audit*
