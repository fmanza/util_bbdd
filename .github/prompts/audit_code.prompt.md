# Prompt: audit_code (Python library)

Auditoría técnica de código con veredicto final. Modo lectura: no edita código.
Agente: Code Auditor.

## Inputs requeridos
- **Archivos a revisar**: rutas completas o globs (p.ej. `src/util_bbdd/metadata/`)
- **Contexto**: qué cambió recientemente o por qué se audita
- **Foco**: bugs, seguridad, tipado, tests o todo

Si no se especifican archivos, detente.

## Devuelve en este orden

### PLAN
- alcance
- archivos analizados

### AUDIT_PLAN
- riesgos funcionales
- riesgos técnicos
- riesgos de seguridad

### AUDIT_CODE
- bugs potenciales (`archivo:línea`)
- edge cases
- contratos públicos sync/async
- compatibilidad y migraciones
- performance
- seguridad (SQL injection, credenciales, inputs)
- tipado (`Any` sueltos, anotaciones que faltan)
- tests faltantes o insuficientes
- deuda técnica
- **Veredicto:** `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`

### VERSION
- commit message si hay cambios derivados (`fix:` o `refactor:`)
- pruebas sugeridas (casos no cubiertos)

## Reglas
- Señala evidencias concretas por archivo y línea.
- Diferencia hallazgos confirmados de hipótesis.
