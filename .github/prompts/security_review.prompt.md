# Prompt: security_review (Python library)

Auditoría de seguridad independiente. Hallazgos verificables, ordenados por severidad.
Agente: Security Reviewer.

## Inputs requeridos
- **Áreas**: rutas o módulos (p.ej. `src/util_bbdd/doc/`, `src/util_bbdd/analysis/`)
- **Foco**: riesgos a priorizar (secretos, SQL injection, exposición de datos…) o `todo`

Si falta alguno, decláralo como supuesto explícito.

## Devuelve en este orden

### PLAN
- alcance de la revisión
- archivos y módulos analizados

### AUDIT_PLAN
- hipótesis de riesgo priorizadas

### AUDIT_CODE
- hallazgos por severidad (crítico / alto / medio / bajo)
- evidencia concreta (`archivo:línea`)
- remediación accionable por hallazgo
- supuestos y datos faltantes etiquetados
- **Veredicto:** los hallazgos críticos bloquean el merge hasta su remediación verificada

### VERSION
- commit message si hay cambios (`security: <descripción>`)
- checklist de validación post-remediación

## Revisar
- validación de inputs
- SQL injection y parametrización
- manejo de credenciales y secretos
- fuga de información en logs y errores
- superficies de ataque por configuración o documentación generada
- contratos sync/async y manejo de recursos

## Reglas
- Prioriza hallazgos verificables y no mezcles confirmados con hipótesis.
- No rebajes severidad sin justificarla.
