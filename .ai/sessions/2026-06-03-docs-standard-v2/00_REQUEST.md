# REQUEST

## Session metadata
- id: 2026-06-03-docs-standard-v2
- fecha: 2026-06-03
- rama: develop
- skill: refactor / new_feature (documentación)
- fase solicitada: PROMPT → PLAN + AUDIT_PLAN → IMPLEMENT (8 fases)

## Solicitud original saneada

1. Generar un prompt para homogenizar la documentación MkDocs basándose en una propuesta
   de arquetipos estructurados con apartados estrictos.
2. Proponer mejoras sobre la propuesta del usuario: soporte multi-lenguaje (Java detectable),
   arquetipos según estándares de industria, enlace obligatorio Referencia Técnica ↔ Ejemplos,
   navegación de exactamente 7 secciones (Inicio, Instalación, Documentación Funcional,
   Referencia Técnica, Guías, Ejemplos, Arquitectura).
3. Entregar PLAN y AUDIT_PLAN de la propuesta.
4. IMPLEMENT con decisiones: C1 (posponer §4 Criterios de Aceptación hasta validación QA);
   C6 (verificar anchors con grep antes de renumeración de guías).
5. Diagnosticar y corregir por qué Autodoc (mkdocstrings) no documentaba todo el API de
   "Bulk Operations".
6. Diagnosticar y corregir por qué Autodoc no documentaba todo el API del módulo "dump".
7. Actualizar `.ai/sessions` y preparar mensaje para subir código a GitHub.

## Objetivo operativo de esta sesión

- Adoptar el estándar documental v2: 5 arquetipos × 5 secciones, navegación de 7 secciones.
- Establecer enlace bidireccional obligatorio entre `docs/api/` (§5 Ejemplos) y
  `docs/examples/` (§5 Referencias).
- Corregir la cobertura autodoc de los módulos `bulk` y `dump`.
- Dejar instrucciones IA que impidan recaer en los mismos errores de autodoc.

## Restricciones explícitas

- C1: NO rellenar §4 Criterios de Aceptación con contenido derivado; queda pendiente de QA.
- C6: verificar anchors con grep antes de renumerar secciones de guías.
- Solo documentación e instrucciones IA; sin cambios de código de funcionalidad.
- `mkdocs build --strict` debe pasar con 0 errores y 0 warnings al cerrar cada fase.

## Resultado esperado

- Carpeta `.ai/sessions/2026-06-03-docs-standard-v2/` con artefactos de trazabilidad.
- `mkdocs build --strict` limpio.
- Mensaje de commit Conventional Commits listo para subir a GitHub.
