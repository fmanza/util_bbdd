# PROMPT RÁPIDO: Análisis de Reutilización y Mantenibilidad (Bulk + Dump)

## 🎯 Objetivo
Analizar `src/util_bbdd/bulk/` y `src/util_bbdd/dump/` como arquitecto Python senior para identificar:
1. Código duplicado o casi duplicado
2. Patrones reutilizables no extraídos
3. Violaciones de SOLID
4. Mejoras de mantenibilidad

## 📚 Contexto obligatorio
Antes de analizar, lee:
1. `.github/SHARED_INSTRUCTIONS.md` — Arquitectura del proyecto
2. `.ai/architecture.md` — Visión de 3 niveles
3. `.ai/CURRENT_STATE.md` — Estado actual, versiones, deuda técnica

## 🔍 Búsqueda permitida
✅ Consulta internet para best practices en:
  - Refactoring Python y patrones de diseño
  - SQLAlchemy ORM/Core
  - Batch processing y paralelismo en BD
  - Type hints y protocolos Python

## 📊 Entrega esperada
Markdown con 9 secciones:
1. **Ejecutivo** — Hallazgos principales (3-5 puntos)
2. **Duplicación** — Tabla: Localización | Patrón | Líneas | Candidato a Extraer | Beneficio | Riesgo
3. **Violaciones SOLID** — SRP | OCP | LSP | ISP | DIP
4. **Patrones Reutilizables** — (Strategy, Factory, etc.)
5. **Análisis de Mantenibilidad** — Por módulo (complejidad, cobertura, docs, type hints)
6. **Propuestas de Refactoring** — Top 5 ordenadas por beneficio/esfuerzo
7. **Comparativa Antes/Después** — Código ejemplo de refactorings principales
8. **Roadmap** — Fase 1 (horas) | Fase 2 (1-2 días) | Fase 3 (1+ semana)
9. **Referencias** — Commits, issues, decisiones pasadas

## ⚠️ Restricciones
- ✅ Análisis estático (sin ejecutar código)
- ❌ No hagas cambios de código en esta sesión
- ❌ Mantén compatibilidad Python ≥3.12

## 🚀 Invocación directa
```
Lee .github/prompts/code_reusability_architecture.prompt.md

Objetivo: Analizar bulk/ y dump/ para reutilización de código y mantenibilidad.

Alcance: src/util_bbdd/bulk/ (5-10 archivos, ~2K LOC)
         src/util_bbdd/dump/ (5-7 archivos, ~1K LOC)

Contexto: .ai/architecture.md, .ai/CURRENT_STATE.md, .github/SHARED_INSTRUCTIONS.md

Entrega el informe de 9 secciones con ejemplos de código en los refactorings.
```
