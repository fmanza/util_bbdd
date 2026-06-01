# REQUEST

## Session metadata
- id: 2026-06-01e-sonarqube-pylance-fixes
- fecha: 2026-06-01
- rama: develop
- skill: hotfix
- fase solicitada: AUDIT_CODE (remediar diagnósticos de SonarQube y Pylance)

## Solicitud original saneada
Resolver diagnósticos reportados por SonarQube e herramientas de análisis estático:
- SonarQube python:S1244 (comparación directa de floats)
- Pylance reportArgumentType (argumentos incompatibles con protocolos)
- SonarQube python:S7503 (funciones async sin operaciones asincrónicas)

## Objetivo operativo de esta sesión
1. Arreglar comparación de float en test_normalize.py:120 (S1244)
2. Actualizar firma de normalize_oracle_type para aceptar `str | None` (Pylance)
3. Agregar métodos faltantes a mocks de test_postgresql_adapter_parity_mariadb.py (Pylance)
4. Agregar await asyncio.sleep(0) en funciones async de mocks (S7503)

## Restricciones explícitas
- Solo remediar diagnósticos reportados por herramientas
- No refactorizar ni cambiar lógica funcional
- Mantener compatibilidad backward en firmas públicas

## Resultado esperado
- ✅ Todos los diagnósticos de SonarQube python:S1244 resueltos
- ✅ Todos los diagnósticos de Pylance reportArgumentType en archivos objetivo resueltos
- ✅ Todos los diagnósticos de SonarQube python:S7503 resueltos
- ✅ Sesión documentada en .ai/sessions/ con traceabilidad completa
- ✅ Mensaje de commit (Conventional Commits) listo para GitHub
