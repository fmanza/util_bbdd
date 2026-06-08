# TRACEABILITY

## Session metadata
- id: 2026-06-07-guides-standard
- fecha: 2026-06-07 / 2026-06-08
- rama: develop
- skill: refactor + documentation
- fase: IMPLEMENT + AUDIT_CODE

## Prompt issued

```
1. Lee pyproject.toml, README.md, CLAUDE.md y .github/SHARED_INSTRUCTIONS.md.
   Genera la guía de incorporación para desarrolladores usando .github/prompts/onboarding_dev.prompt.md.
   Guarda en docs/ONBOARDING_DEV.md. Actualiza mkdocs.yml si la página es nueva.

2. docs\ONBOARDING_DEV.md deberia pertener a un apartado de Guías dentro de la documentación
   y el nombre debería venir en minúsculas, todas las guías deberían estar en una carpeta única.

3. Revisa y Actualiza la documentación en los dos proyectos para la documentación de las guías.
   Las guías tienen su propio apartado, el nombre del fichero siempre minúsculas para toda la
   documentación, las guías tienen su propia carpeta, revisar el contenido mínimo que debe tener
   la carpeta de guías.

4. Revisa y Actualiza la documentación IA en los dos proyectos para la documentación de las guías.
   Añade lo que consideres mejor para tener unas guías de calidad.
```

## Context supplied

- `pyproject.toml` — versión, dependencias, extras
- `README.md` — descripción, instalación, uso
- `CLAUDE.md` — slash commands, flujo de trabajo
- `.github/SHARED_INSTRUCTIONS.md` — arquitectura 3 niveles, comandos, convenciones
- `.github/prompts/onboarding_dev.prompt.md` — plantilla Arquetipo 7
- `docs/*.md` — guías existentes antes de reorganización
- `mkdocs.yml` — configuración de navegación

## AI output summary

- Creado `.github/prompts/onboarding_dev.prompt.md` (Arquetipo 7, plantilla con dominio slot)
- Creada `docs/guides/onboarding_dev.md` (11 secciones, comandos verificados contra pyproject.toml)
  - §5 y §6 "No aplica" (librería, sin servidor)
  - Verificación one-liner: `ruff check && mypy && pytest -q`
- Creada carpeta `docs/guides/` como única ubicación de guías
- Movidas 18 guías de `docs/` raíz a `docs/guides/`, todas renombradas a minúsculas
- Renombrados 3 ficheros raíz: ARCHITECTURE.md → architecture.md, INSTALLATION.md → installation.md, ROADMAP.md → roadmap.md
- Actualizadas todas las referencias cruzadas en docs/ y mkdocs.yml (sed batch + Edit manual)
- Corregidos enlaces a `.ai/*.md` en onboarding (fuera de docs/ → texto plano para --strict)
- Actualizado `mkdocs.yml`: sección Guías con subcarpeta guides/, paths en minúsculas
- Actualizado `docs/index.md`, `docs/legacy-versions.md`, `docs/downloads.md`, `docs/examples/` — referencias a guías movidas
- Actualizado `.github/DOCUMENTATION_STANDARD.md`:
  - §3.3 ubicación: `docs/guides/` + nota minúsculas
  - §3.6 ubicaciones: INSTALLATION.md → installation.md, ARCHITECTURE.md → architecture.md
  - §3.7 ubicación unificada a `docs/guides/onboarding_dev.md`
  - §3.8 nuevo: "Estándar de la Sección Guías" (convenio nombres, conjunto mínimo, nav mkdocs.yml, cuándo actualizar)
  - §4.2 nav snapshot actualizado con paths guides/
  - §6 item 2 ubicaciones fijas: docs/guides/ + nota
- Actualizado `.github/SHARED_INSTRUCTIONS.md`: añadida subsección "Convención de nombres en docs/" (minúsculas, guides/, conjunto mínimo)

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Prompt Arquetipo 7 | `.github/prompts/onboarding_dev.prompt.md` | creado |
| Guía de incorporación | `docs/guides/onboarding_dev.md` | creado |
| Carpeta guías | `docs/guides/` (18 ficheros) | creado / reorganizado |
| DOCUMENTATION_STANDARD.md | `.github/DOCUMENTATION_STANDARD.md` | actualizado (§3.3/3.6/3.7/3.8/4.2/6) |
| SHARED_INSTRUCTIONS.md | `.github/SHARED_INSTRUCTIONS.md` | actualizado (convención nombres) |
| mkdocs.yml | `mkdocs.yml` | actualizado |
| docs/index.md | `docs/index.md` | actualizado (3 enlaces) |
| docs/legacy-versions.md | `docs/legacy-versions.md` | actualizado |
| docs/downloads.md | `docs/downloads.md` | actualizado |
| docs/examples/exception_handling.md | `docs/examples/exception_handling.md` | actualizado |
| docs/examples/async_concurrent_queries.md | `docs/examples/async_concurrent_queries.md` | actualizado |

## Directrices para Futuras IAs

- **[guides/]**: Todas las guías viven exclusivamente en `docs/guides/`. Nunca en `docs/` raíz. Nombre siempre en minúsculas con guiones bajos.
- **[docs/ nombres]**: Todos los `.md` en `docs/` usan minúsculas (architecture.md, installation.md, roadmap.md). En Windows, `git mv --force` es necesario para renombrar entre mayúsculas/minúsculas ya que el filesystem es case-insensitive.
- **[conjunto mínimo guides]**: `onboarding_dev.md` (Arquetipo 7, 11 secciones) + `troubleshooting.md` son obligatorios. Ver §3.8 en DOCUMENTATION_STANDARD.md.
- **[onboarding util_bbdd]**: §5 "Infraestructura Local" y §6 "Ejecutar la aplicación" dicen "No aplica" — util_bbdd es librería pura sin servidor.
- **[enlaces --strict]**: Links a ficheros fuera de `docs/` (como `.ai/*.md`, `.github/*.md`) deben ser texto plano, no links markdown. MkDocs --strict los rechaza.
- **[cross-references]**: Al mover ficheros entre dirs, actualizar todos los links relativos. Desde `guides/` hacia `functional/` usar `../functional/`. Desde `guides/` hacia `guides/` usar ruta directa sin prefijo.

## Veredicto final

Veredicto: CLOSED
Pendientes al cierre:
- Renombrado case en Windows (ARCHITECTURE.md→architecture.md etc.) puede necesitar `git mv --force` en el commit.
- No hay tests de docs (no aplica para librería sin servidor de documentación en CI local).
