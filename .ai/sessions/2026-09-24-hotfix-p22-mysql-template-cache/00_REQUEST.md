# REQUEST

## Session metadata
- id: 2026-09-24-hotfix-p22-mysql-template-cache
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase solicitada: RCA → FIX → AUDIT_CODE → VERSION

## Solicitud original saneada
Surgido durante la verificación de P-04 (respuesta "si" a "¿Sigo con P-04?"). No es una petición explícita del usuario: es un fallo de corrupción de datos encontrado al verificar, y se corrige en un commit propio antes de reanudar P-04.

## Objetivo operativo de esta sesión
- Evitar que `MySQLMultiRowInsertStrategy` inserte filas en otra tabla con las mismas columnas.

## Restricciones explícitas
- Hotfix mínimo; P-04 queda apartado en `git stash` hasta cerrar este fix.

## Resultado esperado
- Fix en la clave de caché con tests de regresión unitarios y de integración.
