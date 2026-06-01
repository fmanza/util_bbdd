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

## Comandos de Desarrollo Rápidos

```bash
python -m ruff check src tests      # Linting
python -m ruff format src tests     # Formato
python -m mypy src                  # Type-checking
python -m pytest                    # Ejecución de tests
mkdocs serve                        # Previsualizar documentación
```

---

*Actualizado: 2026-05-11*
