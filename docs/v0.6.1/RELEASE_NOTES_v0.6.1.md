# v0.6.1 - Notas de Release

## Estado
- versión objetivo: v0.6.1
- estado: release cerrada
- fecha: 2026-03-24
- alcance: diagramas relacionales, semántica visual y rendimiento de generación documental

## Resumen
La línea de trabajo de v0.6.1 refuerza la legibilidad de los diagramas relacionales y hace explícita la semántica que ya consume la documentación HTML y Word.

Las mejoras ya integradas y validadas en `develop` se concentran en tres bloques:

1. Experiencia visual del detalle HTML.
2. Reutilización de análisis entre superficies documentales.
3. Tipología visual heurística de tablas en los diagramas.

## Mejoras documentadas

### UX HTML de diagramas
- Pestañas por dirección y nivel con metadatos más explícitos.
- Controles de zoom, ajuste, reset y paneo sobre el contenedor HTML del SVG.
- Leyenda visual con dirección, tipo de tabla, cardinalidad y tipo de relación soportado.
- Política explícita de exclusión de vistas del diagrama enriquecido actual.

### Reutilización Word y HTML
- La misma corrida multi-formato puede compartir una única instancia de `GraphvizRelationshipGraphExt`.
- Word reutiliza el `GraphDocument` ya construido cuando necesita resumen textual y render gráfico sobre la misma tabla.

### Tipología visual de tablas
- `entity`: azul pastel.
- `association`: verde pastel.
- `hierarchy`: naranja pastel.

La clasificación visual se calcula desde `analysis/base.py` y se expone como parte del nodo del grafo para que cualquier renderer futuro pueda reutilizarla.

## Regla heurística actual

### Jerarquía
- tabla con FK autorreferenciada.

### Asociación
- tabla con al menos dos FKs y bajo peso de columnas de negocio; o
- tabla con PK compuesta basada en columnas FK, incluso si existen algunas columnas adicionales.

### Entidad
- caso general restante.

## Importante
La tipología visual es una ayuda de lectura del diagrama. No representa una taxonomía absoluta del modelo de datos y puede requerir ajuste posterior en esquemas híbridos o muy dependientes del motor.

## Validación de release
- `ruff check src tests`: OK
- `python -m build`: OK
- `pytest`: `543 passed, 0 failed`
- `python -m mypy src`: `110 errores en 37 archivos`

## Baseline de tipado
El resultado de mypy no introduce un bloqueo nuevo de v0.6.1. Corresponde al baseline histórico actual del proyecto y se mantiene fuera del gate funcional de esta release.

## Validación focalizada previa
- batería focalizada posterior a Slice F: `17 passed`
- validación previa acumulada de las slices relacionadas: `34 passed`

## Riesgos abiertos no bloqueantes
- algunos esquemas complejos pueden seguir confundiendo tabla puente enriquecida con entidad relacional compleja
- la política de vistas deberá revisarse si `analysis` modela vistas como nodos reales del grafo
- si el modelo expone más tipos de relación además de `FK`, la leyenda HTML deberá ampliarse

## Referencias
- `README.md`
- `CHANGELOG.md`
- `.ai/sessions/2026-03-24/06_DESIGN.md`
- `.ai/sessions/2026-03-24/08_NEXT_SLICE.md`
