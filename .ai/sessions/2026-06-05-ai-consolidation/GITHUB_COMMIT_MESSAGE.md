# Commit message — 2026-06-05-ai-consolidation

```
chore(ai): consolidar .ai/ en documentos sintéticos + archivar sesiones históricas

Reorganización completa de .ai/ para que las IAs futuras puedan tomar decisiones
a partir del menor número de archivos posible, sin pérdida de información.

Cambios:
- Añade .ai/CURRENT_STATE.md: estado vivo del proyecto (versión, trabajo activo,
  migración Zenical, motores, calidad).
- Añade .ai/DECISIONS_LOG.md: 15 decisiones arquitectónicas con alternativas
  descartadas, razón e impacto actual (período Mar–Jun 2026).
- Añade .ai/sessions/SESSIONS_DIGEST.md: tabla comprimida de todas las sesiones
  (~65 archivadas + 21 activas).
- Mueve ~65 sesiones (Mar-03 a May-28) a .ai/doc_old/sessions/ (gitignored).
- Mueve 5 docs Zenical de raíz .ai/ a doc_old/ (ANALYSIS_*, PLAN_*, ZENICAL_*).
- Actualiza .ai/sessions/INDEX.md con nota de reorganización y referencias.

Resultado: 201 archivos → 56 activos en git + 148 en doc_old/ (disco).
```
