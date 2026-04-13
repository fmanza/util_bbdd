# Prompt: documentation_review (Python library)

## Devuelve en este orden
1. PLAN
2. AUDIT_PLAN
3. AUDIT_CODE (auditoría de documentación)
4. VERSION

## Revisar
- README y entry points de documentación
- Docstrings en APIs públicas (cobertura, claridad, ejemplos)
- Ejemplos existentes (correctness, completitud, actualización)
- Guías técnicas (arquitectura, onboarding, troubleshooting, migraciones)
- Documentación de instalación y compatibilidad de motores
- Changelog y release notes
- Cross-references y linkability
- Consistencia de lenguaje y tone

## Criterios por severidad

### Nivel 1: Crítico
- README sin descripción clara o sin quick start
- Módulos públicos sin docstrings
- APIs sin type hints o sin documentación de parámetros/return/excepciones
- Ejemplos rotos u obsoletos
- Instalación no documentada

### Nivel 2: Alto
- Features principales sin ejemplos
- Documentación de arquitectura incompleta o sin diagramas
- Guías de troubleshooting ausentes
- Incompatibilidades entre motores no aclaradas
- Errores no documentados

### Nivel 3: Recomendado
- Ejemplos avanzados no cubiertos
- Edge cases sin ejemplificar
- Performance tips no documentados
- Integración con herramientas sin guía

## Reglas
- Diferencia gaps críticos (bloquean uso) de mejoras recomendadas.
- NO inventes documentación que no existe; reporta dónde falta.
- Prioriza por impacto en onboarding y seguridad.
- Incluye ubicación exacta de archivos/módulos.
- Sugiere formato y contenido mínimo para cerrar gaps.
- Etiqueta claramente ejemplos faltantes y ubicación sugerida.
- Verifica ejemplos en `docs/examples/` y docstrings en módulos `__init__.py` y archivos públicos.
