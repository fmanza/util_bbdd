# Instrucciones para Gemini Code Assist — util_bbdd

Este fichero proporciona especialización para Gemini Code Assist al trabajar con el repositorio `util_bbdd`.

---

## ⚠️ Contexto previo obligatorio

Lee **primero**:
- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura TIMELOG, SOLID, calidad, comandos, documentación, flujo de trabajo, Conventional Commits. **Esta es la base.**
- **Este fichero** — Especialización para Gemini Code Assist únicamente.

---

## Flujo de Trabajo Recomendado

Para cambios estructurados, sigue el ciclo de vida definido en el proyecto:

1. **PLAN**: Analizar el objetivo, alcance y riesgos. Contrastar con el código real antes de proponer cambios.
2. **AUDIT_PLAN**: Verificar la viabilidad del plan y detectar expansiones de alcance no deseadas.
3. **IMPLEMENT**: Ejecutar los cambios aplicando los estándares de calidad del proyecto.
4. **AUDIT_CODE**: Revisión técnica independiente (bugs, edge cases, contratos, cobertura).
5. **VERSION**: Cierre de versión, actualización de CHANGELOG y documentación de rollback.

---

## Estándares de Código y Calidad

Al generar código para este proyecto, asegúrate de cumplir con:

- **Python 3.12+**: Uso de características modernas de Python.
- **Tipado Estricto**: Todas las funciones y métodos deben tener type hints completos. Pasar `mypy --strict`.
- **Calidad y Estilo**: Seguir las reglas de `ruff`.
- **F-Strings**: Usar exclusivamente f-strings para interpolación de cadenas.
- **Logging**: Usar el logger configurado por módulo (ej: `logger: logging.Logger = logging.getLogger(__name__)`).
- **SOLID & TIMELOG**: Seguir los principios de diseño definidos en las instrucciones compartidas.
- **Manejo de Errores**: Usar la jerarquía de excepciones basada en `DatabaseException` (ver `util_bbdd._core.exceptions`).

---

## Sincronización de Instrucciones IA

Si se modifican reglas comunes o flujos, actualiza los ficheros en este orden:

1. **`.github/SHARED_INSTRUCTIONS.md`** (Fuente canónica)
2. **`.github/copilot-instructions.md`** (Especialización Copilot)
3. **`CLAUDE.md`** (Especialización Claude Code)
4. **`GEMINI.md`** (Este fichero)

**Validación**: Verifica que no haya duplicación de contenido entre `SHARED_INSTRUCTIONS.md` y las especializaciones, y que todas las rutas sean relativas y portables.

---

## Bootstrap de configuración IA a otro proyecto

Para replicar este sistema de instrucciones IA (Claude / Gemini / Copilot / Cursor / Codex) en otro proyecto,
incluso de **otro lenguaje y arquitectura**, usa el prompt
[`bootstrap_ai_config.prompt.md`](.github/prompts/bootstrap_ai_config.prompt.md).

**Método y dirección — modelo PULL**: se invoca **desde el proyecto destino**, apuntando a este repo
como plantilla de solo lectura; el lenguaje/arquitectura del destino es un **parámetro**. Capas:
**A** copiar verbatim · **B** copiar + reescribir dominio · **C** regenerar analizando el destino ·
**D** excluir. Detalle completo en el propio prompt.

---

## Comandos de Desarrollo Rápidos

```bash
python -m ruff check src tests      # Linting
python -m ruff format src tests     # Formato
python -m mypy src                  # Type-checking
python -m pytest                    # Ejecución de tests
zensical serve                      # Previsualizar documentación (por defecto, lee mkdocs.yml)
mkdocs serve                        # Previsualizar documentación (recíproco, mismo mkdocs.yml)
python scripts/build_docs_zip.py    # Generar ZIP offline con SHA256 checksums
```

---

## 📦 Descarga de Documentación Offline

Util_bbdd ofrece **documentación en ZIP offline** con búsqueda integrada, SHA256 checksums y auto-publicación en GitHub Releases.

### Características

✅ **Página de descargas**: https://fmanza.github.io/util_bbdd/downloads/  
✅ **ZIP comprimido**: ~2.5 MB (150+ archivos HTML)  
✅ **SHA256 Checksum**: Validación de integridad  
✅ **Auto-publicar**: GitHub Release automático en cada push  
✅ **Búsqueda offline**: `search_index.json` incluido en ZIP  

### Generación y Distribución

- **Local**: `python scripts/build_docs_zip.py` genera ZIP en `dist/`
- **CI/CD**: `.github/workflows/docs-zip-release.yml` auto-publica releases
- **Validación**: `sha256sum -c dist/*.sha256` (Linux/Mac) o PowerShell (Windows)

### Para otros proyectos

El sistema es reutilizable mediante bootstrap. Ver `.github/prompts/bootstrap_ai_config.prompt.md`
(sección "📦 Descarga de Documentación Offline") con matriz de equivalencias para múltiples lenguajes.

---

*Actualizado: 2026-06-05*
