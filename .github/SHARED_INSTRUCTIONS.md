# Instrucciones Compartidas: Copilot Chat + Claude Code + Codex

Configuración unificada para trabajar en `util_bbdd` con asistentes de código.
Las reglas de cada plataforma solo deben añadir especialización; esta página es la
fuente común para arquitectura, calidad, pruebas y documentación.

---

## Rol esperado

Actúa como senior de ingeniería Python especializado en:
- Extracción y exportación de tiempos desde GitLab (TIMELOG core).
- Herramientas CLI con `argparse` y APIs programáticas simples.
- Operaciones seguras de filesystem con `pathlib`, `shutil` y validación explícita.
- Procesamiento de datos con pandas y generación de reportes (Excel, CSV, JSON).
- Testing determinista con pytest sin servicios externos.
- Documentación de librerías Python con MkDocs.

---

## Proyecto: util_bbdd

`util_bbdd` es una librería Python para extraer, procesar y exportar tiempos de trabajo
desde GitLab, generando reportes en Excel, CSV y JSON para auditoría y análisis de proyectos.

**Versión canónica**: consultar `pyproject.toml` antes de cerrar releases.
**Python**: `>=3.12` según `pyproject.toml`.

### Capacidades principales (TIMELOG)
- **Extracción de tiempos**: lee timelogs de GitLab vía GraphQL.
- **Análisis de issues**: recopila datos de issues, milestones e incidentes.
- **Cálculo de métricas**: tiempo estimado vs. gastado, porcentaje de ejecución.
- **Exportación múltiple**: Excel (con formato), CSV, JSON.
- **Configuración flexible**: filtros por proyecto, fechas, equipos.

---

## Arquitectura real (TIMELOG Core)

```text
src/util_bbdd/
  timelog/              # Core: time tracking export and reporting
    time_utils.py       # Parsing de tiempo (mo, w, d, h, m)
    calendar.py         # Cálculo de semanas (ISO, fiscal)
    project_loader.py   # Listado y filtrado de proyectos GitLab
    load_gitlab.py      # Conexión y configuración GitLab
    issue_helpers.py    # Metadatos de issues e incidentes
    excel_formatter.py  # Formato Excel
    crear_csv.py        # Export CSV
    crear_json.py       # Export JSON
    __init__.py         # API pública del módulo
  common/               # Shared utilities
    decimal_utils.py    # Redondeo y conversión de Decimals
    __init__.py
  core/                 # Placeholder (futuro)
  utils/                # Placeholder (futuro)
export_gitlab_time.py   # Main CLI for timelog export
```

### Responsabilidades por módulo (TIMELOG)

| Módulo | Responsabilidad |
|---|---|
| `timelog/` | Extracción de tiempos, análisis de issues, exportación |
| `common/` | Utilidades compartidas (decimal, conversiones) |
| `export_gitlab_time.py` | CLI principal: carga config, exporta a Excel/CSV/JSON |

### API pública recomendada

```python
from util_bbdd import (
    parse_time_spent,
    parse_date,
    listar_proyectos_filtrados,
    FormatearExcel,
    convertir_decimales_a_float,
)

# Ejemplo de uso programático
time_config = {"hours_per_day": 8, "days_per_week": 5}
spent = parse_time_spent("1h 30m", time_config)  # Decimal en segundos
```

### CLI actual

```bash
python src/export_gitlab_time.py
```

📌 Consultar `src/export_gitlab_time.py` para configuración via `src/conf/gitlab.toml` (unifica credenciales + filtros por conexión).

---

## Principios de diseño

### Operaciones de filesystem
- Usa `pathlib.Path` para rutas.
- Valida existencia de archivos de configuración GitLab.
- Lee archivos TOML de configuración de forma segura.
- Escribe archivos Excel, CSV y JSON en directorio de salida.
- No sobrescribas archivos sin validación explícita.

### Procesamiento de datos
- Usa `pandas.DataFrame` para manipular datos de issues y timelogs.
- Redondea `Decimal` con precisión controlada via `safe_decimal_round`.
- Convierte `Decimal` a `float` para exportación Excel via `convertir_decimales_a_float`.
- Valida fechas con `es_fecha_valida` y `parse_date`.
- Parsea tiempo gastado con `parse_time_spent` (soporta mo, w, d, h, m).

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
- En `export_gitlab_time.py` (CLI), configura logging basado en nivel INFO.
- En servicios (`timelog/`, `common/`), pasa logger como parámetro si es necesario.
- En handlers de error inesperado, usa `exc_info=True`.
- Evita `print()` en servicios; se permite en CLI para resúmenes de usuario.

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
python -m mypy src
python -m pytest
python -m build
mkdocs build
```

### Estrategia de tests
- Funciones de `timelog/`: tests unitarios sin red (mock pandas, decimal ops).
- Funciones de `common/`: tests de conversión y validación.
- `export_gitlab_time.py`: probar parseo de config, construcción de queries, transformación de datos.
- No depender de red ni GitLab real; mock `gitlab.Gitlab` cuando sea necesario.
- Fixtures en `tests/conftest.py` para datos de prueba (timelogs, issues mock).

### Documentación obligatoria

#### Cuándo es CRÍTICA (bloquea PRs)

- ✅ Nueva clase pública → docstring Google-style + ejemplo
- ✅ Cambio de API pública → actualizar guías en `docs/`
- ✅ Refactor con breaking changes → guía de migración en CHANGELOG.md
- ✅ Antes de cerrar versión → `mkdocs build` sin errores ni links rotos
- ✅ Cambios en instrucciones IA → sincronizar todos los ficheros afectados
- ✅ Nuevo archivo generado o copiado → actualizar README y/o docs de uso
- ✅ Cambio de CLI → actualizar ejemplos en README, `docs/` y `.ai/runtime.md`
- ✅ **Nueva versión (VERSION)** → revisar `.github/instructions/sync.instructions.md`
  para validar que CHANGELOG.md y COMPATIBILITY.md están sincronizados

#### MkDocs — cuándo actualizar

- ✅ Módulo o clase pública nueva → entrada en `mkdocs.yml` bajo `nav:`
- ✅ Página nueva, movida o eliminada en `docs/` → actualizar `mkdocs.yml`
- ✅ Reorganización funcional/técnica/ejemplos → validar que `nav:` mantiene apartados separados
- ✅ Ejecutar `mkdocs serve` localmente antes de publicar
- ✅ Verificar que `mkdocs build` pase sin warnings

#### Estándar de generación documental

- Usa MkDocs con Material for MkDocs como salida estática de referencia.
- Usa Mermaid.js para diagramas de flujo, secuencia o clases cuando aporte claridad.
- Unifica creación y actualización: busca primero documentación existente y actualízala si es el punto de entrada correcto.
- Para documentación de proyecto completo, revisa README, `docs/`, `docs/examples/`, docstrings públicos, prompts/agentes IA y `mkdocs.yml`.
- Separa claramente documentación funcional, técnica y ejemplos.
- No inventes capacidades, módulos, APIs, salidas, reglas ni dependencias. Si falta información, márcala como pendiente de verificación.
- No uses ejemplos heredados de otros repositorios: valida nombres de proyecto, rutas, clases y tests contra el árbol real antes de documentarlos.
- No uses un único prompt masivo; divide en mapeo funcional, técnica, ejemplos, Mermaid y revisión final.
- Excluye por el momento generación de documentación mediante APIs externas.

#### Estándar: Docstrings Google-style

```python
class TimeLogger:
    """Registrador de tiempos de trabajo desde GitLab.

    Extrae timelogs via GraphQL y aplica filtros de fecha y proyecto.

    Attributes:
        gitlab_client (gitlab.Gitlab): Cliente GitLab autenticado.
        logger (logging.Logger): Logger de instancia.

    Example:
        >>> logger = TimeLogger(gl_client)
        >>> timelogs = logger.get_timelogs(project_id=42, start="2026-01-01")
        >>> print(len(timelogs))
        15
    """
```

### Formato de commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     nueva funcionalidad (dentro de scope, no refactor)
fix:      corrección de bug (hotfix, RCA → fix mínimo)
refactor: cambio sin impacto funcional
test:     solo tests, sin cambios de funcionalidad
docs:     solo documentación (README, docstrings, guías)
chore:    mantenimiento (deps, config, herramientas)
```

**Ejemplo**:
```
feat: extraer timelogs por rango de fechas en timelog/time_utils.py

- Añade función parse_date_range() con validación
- Tests en tests/unit/timelog/test_time_utils.py
- Actualiza docstring y ejemplos en README
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

---

## Gobernanza de plataformas IA

| Archivo | Plataforma | Propósito |
|---|---|---|
| `.github/SHARED_INSTRUCTIONS.md` | Copilot, Claude, Codex | Fuente canónica: arquitectura, calidad, comandos |
| `.github/copilot-instructions.md` | GitHub Copilot Chat | Especialización: agentes VS Code, reglas Copilot |
| `CLAUDE.md` | Claude Code | Especialización: slash commands, hooks, settings.json |
| `.github/AGENTS.md` | Copilot/Claude | Registro de agentes especializados |
| `.ai/*.md` | Todas | Contexto persistente: producto, arquitectura |

**Regla de oro**: Edita SHARED_INSTRUCTIONS.md primero. Luego sincroniza solo las
especializaciones afectadas (copilot-instructions.md y/o CLAUDE.md).

---

*Actualizado: 2026-05-14*
