# REQUEST

## Session metadata
- id: 2026-09-24-hotfix-p19-json-double-encoding
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase solicitada: RCA → FIX → AUDIT_CODE → VERSION

## Solicitud original saneada
"si", en respuesta a: "¿Hago el commit y paso al `/hotfix` de P-19?"

## Objetivo operativo de esta sesión
- Corregir P-19: `bulk_update_from_df` guarda las columnas JSON serializadas dos veces y `None` como el literal JSON `null` (MySQL `JSON`, PostgreSQL `JSONB`).
- Verificar el supuesto de alcance en otros motores y rutas.

## Restricciones explícitas
- Hotfix: fix mínimo en la causa raíz, sin refactorizar ni optimizar.
- Las tablas sin columnas JSON deben ejecutar exactamente las mismas sentencias que antes.

## Resultado esperado
- Fix con test que reproduzca el fallo sin servidor y regresión de integración contra motores reales.
