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

**Documentación (mkdocs-material):**

```bash
pip install -e ".[docs]"             # instalar deps de docs (requiere internet la 1ª vez)
mkdocs serve                         # servidor local → http://127.0.0.1:8000
mkdocs build                         # genera site/ estático (validación local)
mkdocs gh-deploy                     # publica en GitHub Pages (requiere git push)
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
- **Verificar**: Todos los strings con parámetros usan f-strings (no `.format()`, `%`, ni concatenación)

### Checklist: F-Strings OBLIGATORIOS

**Bloquea PR si:**
- ✗ String con parámetros usa `.format()`: `"Processing {} records".format(count)` ❌
- ✗ String con parámetros usa `%` formatting: `"Expected %s rows" % expected` ❌
- ✗ String con parámetros usa concatenación: `"Table " + name + " (" + str(rows) + ")"`  ❌

**Requiere:**
- ✅ F-string para todo string con parámetros: `f"Processing {count} records"`
- ✅ F-string en logging: `logger.info(f"Records: {len(data)}, timeout: {timeout}s")`
- ✅ F-string en mensajes de error: `error_msg = f"Expected {expected} rows, got {actual}"`

**Permite (strings sin parámetros):**
- ✅ Strings estáticos: `"Inicializando conexión"`
- ✅ Docstrings con ejemplos
- ✅ Constantes documentales

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
- ✅ `mkdocs serve` — servidor local de documentación (requiere `.[docs]` instalado)
- ✅ `mkdocs build` — genera `site/` estático y valida links internos

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
mkdocs serve                                                     # offline ✅ (deps ya instaladas)
mkdocs build                                                     # offline ✅
```

---

### Qué Requiere Internet ❌

**Servicios/APIs externos:**
- ❌ `GitHub search` — para encontrar issues/PRs relevantes (requiere API GitHub)
- ❌ `SonarQube` — análisis de seguridad + cobertura remote
- ❌ `GitHub Copilot Chat` (`@copilot`) — integración online de Copilot
- ❌ Descargas de dependencias nuevas (`pip install`) — requiere PyPI o índice custom
- ❌ `pip install -e ".[docs]"` — instalación inicial de mkdocs-material (requiere PyPI)
- ❌ `mkdocs gh-deploy` — publicación en GitHub Pages (requiere red + git push)
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

1. **GitHub search no disponible** → No puedes buscar related issues. Workaround: busca localmente en `.ai/sessions/` (sesiones de trabajo) o `docs/` (documentación viva) o `docs/archive/plan-legacy/` (planes históricos de PRs)
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

## Documentación Obligatoria

### Cuándo la Documentación es CRÍTICA

**Siempre obligatorio:**
- ✅ Nueva clase o función pública → docstring + ejemplo en docstring
- ✅ Cambio de API pública → actualizar guías + ejemplo de migración
- ✅ Refactor con breaking changes → docstring de deprecación + guía de actualización
- ✅ Reporters/generación de salida → documentar formato + ejemplo de uso
- ✅ Módulo nuevo → entry en `mkdocs.yml` + ejemplo básico

**Por comando (`/` prefix):**

#### `/new-feature`
```
REQUERIDO:
  1. Docstring: Google-style (Args, Returns, Raises, Example)
  2. Ejemplo: Mínimo 1 en docstring, 1+ en docs/examples/ si es complejo
  3. mkdocs: Agregar entry en API_REFERENCE.md o módulo correspondiente
  4. Commit: Incluir "docs:" si cambio es en API pública
```

#### `/refactor`
```
REQUERIDO si:
  - Es refactor de API pública: docstring mejorado + deprecación (si aplica)
  - Es refactor de clase/función: ejemplo actualizado (si es obsoleto)
```

#### `/hotfix`
```
OPCIONAL pero RECOMENDADO:
  - Si el bug fue por código confuso: mejorar docstring
  - Si el fix cambia comportamiento: actualizar ejemplo
```

#### `/audit-code`
```
VERIFICAR:
  - Docstrings: 100% en código modificado
  - Ejemplos: Si es API nueva, debe tener ejemplo
  - mkdocs: Sin links rotos, indices actualizados
  - Deprecación: Si hay breaking change, tiene guía de migración
```

---

### Estándares de Docstrings (Obligatorio)

**Formato:** Google-style (recomendado por PEP 257)

**Estructura mínima:**
```python
class MyService:
    """Descripción breve de la clase en 1-2 líneas.

    Descripción detallada (opcional, 3+ párrafos si es complejo):
    - Comportamiento
    - Use cases
    - Contratos

    Attributes:
        attr1 (str): Descripción de atributo
        attr2 (int): Descripción

    Example:
        Ejemplo minimalista de uso (2-4 líneas):

        >>> service = MyService()
        >>> result = service.do_something()
        >>> print(result)
        'expected_output'
    """

    def public_method(self, param1: str, param2: int) -> dict[str, Any]:
        """Breve descripción de qué hace.

        Detalles adicionales (si es ambiguo).

        Args:
            param1: Descripción de param1
            param2: Rango o restricción (ej: "debe ser > 0")

        Returns:
            dict[str, Any]: Descripción de estructura retornada

        Raises:
            ValueError: Cuándo se lanza y por qué
            ConnectionError: Si la conexión falla

        Example:
            >>> result = service.public_method("test", 5)
            >>> result["status"]
            'success'
        """
```

**Checklist antes de push:**
- [ ] Docstring en cada clase pública
- [ ] Docstring en cada función/método público
- [ ] Todos los parámetros listados (sin omitir)
- [ ] Return type + descripción presente
- [ ] Excepciones que lanza documentadas
- [ ] 1+ ejemplo ejecutable en cada docstring
- [ ] Ejemplo NO tiene valores hardcodeados (usar variables)
- [ ] Ejemplo coincide con código actual (no obsoleto)

---

### Ejemplos Obligatorios (Ubicación)

**En docstring (siempre):**
- Mínimo 1 ejemplo
- 2-4 líneas máximo
- Usar valores genéricos (no hardcode)

```python
# ✅ BIEN
def find_user(user_id: int) -> User | None:
    """Busca usuario por ID.

    Example:
        >>> user = find_user(123)
        >>> user.name if user else None
        'Alice'
    """
```

```python
# ❌ MAL - valores hardcodeados
def find_user(user_id: int) -> User | None:
    """Busca usuario por ID.

    Example:
        >>> user = find_user(42)  # ← hardcode, no escalable
        >>> user.name
        'John'  # ← hardcode, puede cambiar
    """
```

**En docs/examples/ (si es extenso):**
- Ejemplos >4 líneas o multi-pasos
- Casos de uso reales
- Manejo de errores

**Ejemplo de archivo:**
```
docs/examples/
  ├─ basic_usage.py
  ├─ advanced_queries.py
  ├─ error_handling.py
  └─ comparar_schemas_complete.py
```

---

### Sincronización mkdocs (Obligatorio)

**Antes de hacer push, ejecutar:**

```bash
# 1. Validar que mkdocs genera sin errores
mkdocs build

# 2. Si ves warnings de links rotos, ARREGLALO
# (mkdocs build falla si hay links internos rotos)

# 3. Verifica que tu cambio aparece en navegación
ls site/  # busca tu módulo o página

# 4. Si cambias API pública:
#    a) Actualiza docs/API_REFERENCE.md
#    b) Crea entry en mkdocs.yml si es módulo nuevo
#    c) Agrega ejemplo en docs/examples/

# 5. Commit message:
git commit -m "feat(module): Nueva clase X

Incluye mkdocs entry en API_REFERENCE.md
Ejemplos en docs/examples/module_example.py"
```

**Validación local checklist:**
- [ ] `mkdocs build` completa sin errores
- [ ] `mkdocs build` sin warnings de links rotos
- [ ] Nueva clase/función visible en `site/` bajo su módulo
- [ ] Si es módulo nuevo, hay entry en `mkdocs.yml`
- [ ] Ejemplos en docstrings son ejecutables
- [ ] Ejemplos en `docs/examples/` están comentados

---

### Ejemplos de Documentación Completa

#### Ejemplo 1: Clase Simple

```python
# _metadata_request.py
class MetadataRequestBuilder:
    """Constructor de requests para fetching de metadata (patrón: Builder).

    Centraliza la construcción de consultas de metadata, proporcionando
    una interfaz coherente e independiente del motor de BD.

    Attributes:
        None (todas las operaciones son estáticas)

    Example:
        >>> request = MetadataRequestBuilder.table_ddl(schema, table, add_params)
        >>> request.query_name
        'create_table'
        >>> request.expect_one
        True
    """

    @staticmethod
    def table_ddl(
        context_database: str,
        table_name: str,
        add_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
    ) -> MetadataFetchRequest:
        """Construye la request estándar para DDL de tabla.

        Args:
            context_database: Contexto (schema/database)
            table_name: Nombre de tabla
            add_context_params: Función para añadir parámetros de contexto

        Returns:
            MetadataFetchRequest: Request configurada para consulta DDL

        Raises:
            ValueError: Si table_name está vacío
            TypeError: Si add_context_params no es callable

        Example:
            >>> req = MetadataRequestBuilder.table_ddl("public", "users", add_params)
            >>> req.table_name
            'users'
        """
```

#### Ejemplo 2: Método que lanza excepciones

```python
class CharsetCollationParser:
    def parse_db_charset(self, db_type: str, result: tuple[Any, ...] | None) -> dict[str, Any]:
        """Parsea resultado de charset/collation de base de datos según motor.

        Args:
            db_type: Tipo de base de datos (oracle, postgresql, mariadb, etc.)
            result: Tupla con resultado de charset (puede ser None)

        Returns:
            dict[str, Any]: Diccionario con claves charset, collation, etc.
                          Retorna {} si result es None o parser no encontrado.

        Raises:
            ValueError: Si db_type no es soportado

        Example:
            >>> parser = CharsetCollationParser(logger)
            >>> charset = parser.parse_db_charset("oracle", ("UTF8", "AL16UTF16"))
            >>> charset["charset"]
            'UTF8'
        """
```

---

### Policy de Documentación por Tipo de Cambio

| Cambio | Docstring | Ejemplo | mkdocs | Migración | Commit |
|---|---|---|---|---|---|
| Nueva clase pública | ✅ Obligatorio | ✅ En docstring + docs/examples/ | ✅ Entry | N/A | `docs:` |
| Nuevo método público | ✅ Obligatorio | ✅ En docstring | ✅ Update API_REFERENCE | N/A | `docs:` |
| Función interna `_private` | ✅ Obligatorio | ⚠️ Breve | ❌ No | N/A | `docs:` |
| Breaking change | ✅ Obligatorio | ✅ Migración | ✅ Deprecation guide | ✅ Obligatorio | `docs:` |
| Bug fix | ✅ Si es confuso | ❌ No | ❌ No | N/A | `fix:` |
| Refactor interno | ✅ Mejorado | ⚠️ Si obsoleto | ❌ No | N/A | `refactor:` |

---

### Validación Pre-Push Checklist

```bash
# 1. Lint + Type + Tests (como siempre)
python -m ruff check src tests
python -m mypy src
python -m pytest

# 2. NUEVO: Validar documentación
## 2a. mkdocs build
mkdocs build

## 2b. Si cambio es en API pública:
grep -r "class.*:" src/[changed_module]/ | wc -l
# Verifica: ¿Cada clase tiene docstring?

## 2c. Si cambio es de reporters/salida:
grep -A 10 "def.*reporter" src/[changed_module]/ | grep '"""'
# Verifica: ¿Hay docstring?

# 3. Commit
git commit -m "feat(module): Cambio
docs: Actualizar API_REFERENCE (si API nueva)"
```

---

## Resumen: Obligatoriedad de Documentación

```
✅ SIEMPRE OBLIGATORIO:
  - Docstring en cada clase/función pública
  - 1+ ejemplo en docstring
  - mkdocs actualizado si cambio es en API pública

✅ POR CAMBIO:
  - Nueva clase → docstring + ejemplo + mkdocs entry
  - Cambio de firma → docstring mejorado + ejemplo actualizado
  - Breaking change → guía de migración + deprecación

❌ BLOQUEADOR EN PR:
  - Clase/función pública SIN docstring
  - Docstring sin ejemplo
  - mkdocs build fallando (links rotos)
  - Cambio de API SIN guía de migración
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

*Actualizado: 2026-04-20 — Documentación obligatoria agregada (Policy, Estándares, Checklists)*
