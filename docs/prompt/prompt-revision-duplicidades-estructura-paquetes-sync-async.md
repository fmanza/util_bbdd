# Prompt: Revisión Arquitectónica Compacta (sin backward compatibility)

Eres un asistente senior de arquitectura Python. Debes analizar el proyecto y entregar un plan de refactor **accionable**, con foco en:
- eliminar duplicidades (DRY + SRP),
- normalizar contratos sync/async,
- y proponer estructura de paquetes objetivo.

## 1) Alcance y restricciones (obligatorio)

Analiza `src/util_bbdd/**` excluyendo de forma estricta:
- `src/util_bbdd/bulk_crud/**`
- `src/util_bbdd/doc/**`
- `src/util_bbdd/grafos/**`

Condiciones:
- **Sin compatibilidad hacia atrás**: puedes romper imports, firmas, nombres y estructura.
- Debes listar breaking changes y una guía corta de migración.
- Sin servicios externos en validación de tests (sin DB real, sin red).
- Mantén paridad de capacidades entre sync y async.

Motores a cubrir (usar estos IDs): `sqlserver`, `mariadb`, `oracle`, `hsqldb`, `postgresql`, `sqlite`.

## 2) Qué debes evaluar

1. Inventario actual:
- paquetes/módulos relevantes (especialmente `connection`, `executors`, `validators`, `factory`),
- clases públicas sync y async,
- puntos de entrada clave.

2. Duplicidades:
- por nombre de método,
- por comportamiento equivalente,
- por responsabilidad mezclada en una misma clase.

3. Normalización de responsabilidades:
- `DatabaseQueries`: catálogo/resolución/metadata/validación estática.
- `DatabaseQueryExecutor`: ejecución runtime, fetch, timeout, errores, transacciones.
- Define contrato objetivo sync/async con paridad semántica y mínima duplicación.

4. Decisión por componente:
- refactorizar vs crear clase nueva, con criterio explícito (riesgo, claridad, tamaño de cambio).

5. Arquitectura objetivo:
- árbol de paquetes propuesto (target) alineado al repo real como punto de partida, no como supuesto.
- evitar módulos god y acoplamientos innecesarios sync/async.

## 3) Formato de salida obligatorio (Markdown)

Tu respuesta debe incluir exactamente estas secciones:

1. **Resumen Ejecutivo**
2. **Inventario Actual (excluyendo bulk_crud/doc/grafos)**
3. **Duplicidades Detectadas (tabla)**
4. **Arquitectura Objetivo de Paquetes (target tree)**
5. **Normalización DatabaseQueries vs DatabaseQueryExecutor (sync/async)**
6. **Decisiones de Refactor vs Clase Nueva**
7. **Matriz por Motor**
8. **Plan por Fases**
9. **Breaking Changes + Guía de Migración**
10. **Riesgos y Mitigaciones**
11. **Checklist de Aceptación**

### 3.1 Matriz por Motor (sección 7)

Incluye una tabla con una fila por motor (`sqlserver`, `mariadb`, `oracle`, `hsqldb`, `postgresql`, `sqlite`) y estas columnas:
- Estado actual (módulos/clases implicadas)
- Duplicidades/Problemas
- Decisión (refactor o nuevo)
- Cambios clave propuestos
- Tests de contrato (mock/fake, sin servicios externos)

## 4) Plan por fases (sección 8)

Define fases numeradas. Cada fase debe contener:
- objetivo,
- componentes/archivos a tocar,
- criterio de aceptación (pytest),
- breaking changes introducidos (si aplica).

## 5) Criterios de calidad de la respuesta

- Sin texto genérico: cada decisión debe estar conectada al código real.
- Sin duplicar secciones (evita repetir “cambios por motor” en múltiples apartados).
- Mantén precisión y brevedad: prioriza acciones concretas.

Si falta información crítica para decidir, haz máximo 3 preguntas puntuales; si no, responde completo.
