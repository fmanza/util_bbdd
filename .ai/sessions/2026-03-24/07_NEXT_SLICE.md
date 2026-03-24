# PLAN

## objetivo
- preparar la siguiente slice funcional de v0.6.1 como una mejora de rendimiento medible en la generación de diagramas cuando una misma ejecución produce más de un formato documental
- reutilizar el caché ya existente de `GraphDocument` en `analysis/base.py` sin introducir un segundo sistema de caché paralelo

## rutas afectadas
- src/util_bbdd/doc/database_documentation.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/word_generator.py
- tests/unit/test_database_documentation.py
- tests/unit/test_doc_generators_helpers.py
- opcional si se separa el builder compartido: nuevo test unitario focalizado en la construcción del generador de grafos

## server/client
- no aplica

## componentes implicados
- `DatabaseDocumentation` como orquestador de salida multi-formato
- `HtmlGenerator` y `WordGenerator` como consumidores del generador de grafos
- `GraphvizRelationshipGraphExt` como punto único de construcción del `GraphDocument`
- caché ya existente `_graph_document_cache_by_context` en `src/util_bbdd/analysis/base.py`

## tipos necesarios
- no se requiere un nuevo modelo de dominio para esta slice
- como máximo, un helper interno o parámetro opcional para inyectar un `graph_generator` ya construido en los generadores documentales

## impactos en auth o roles
- ninguno

## riesgos
- acoplar demasiado `DatabaseDocumentation` con detalles internos de render si el generador compartido no se pasa por una interfaz mínima
- introducir divergencia de configuración si Word y HTML dejan de construir el generador con exactamente las mismas opciones
- sobredimensionar la slice con refactor adicional cuando el objetivo real es solo reutilizar estado ya calculado en una misma ejecución

# AUDIT_PLAN

## riesgos funcionales
- si la inyección opcional del generador no mantiene el fallback actual, podría romper ejecuciones que solo producen un formato
- si el generador compartido conserva estado no esperado más allá del caché del documento, podría aparecer contaminación entre tablas o formatos

## riesgos técnicos
- hoy `HtmlGenerator` y `WordGenerator` duplican la construcción de `GraphvizRelationshipGraphExt`; la slice debe eliminar la duplicidad mínima necesaria sin abrir un refactor transversal
- el caché actual es por instancia, así que no hay beneficio real entre formatos mientras cada generador cree su propia instancia
- mover la construcción a `DatabaseDocumentation` exige mantener el mismo contrato de opciones (`columns`, `cardinality`, `max_depth`, `direction`, `dpi`)

## riesgos de seguridad
- no se detectan riesgos nuevos relevantes; la slice no cambia consultas SQL ni expone nuevas entradas externas
- revisar únicamente que la reutilización del generador no altere el flujo de inyección de enlaces SVG ni el escapado HTML existente

## simplificaciones posibles
- no crear un caché nuevo en `src/util_bbdd/metadata/cache.py`
- no modificar `analysis/base.py` mientras `_graph_document_cache_by_context` siga cubriendo el caso de reutilización intra-ejecución
- no cambiar contratos de `GraphDocument`, `HiddenLevelsSummary` ni payload HTML en esta slice

# IMPLEMENT

## cambios por archivo

### src/util_bbdd/doc/database_documentation.py
- añadir un helper privado para resolver si hace falta un `graph_generator` compartido
- construir una única instancia de `GraphvizRelationshipGraphExt` cuando `include_diagrams` sea verdadero y la ejecución vaya a producir Word y HTML
- pasar esa instancia a los generadores de salida que la acepten

### src/util_bbdd/doc/html_generator.py
- permitir recibir un `graph_generator` opcional en `generate_document`
- mantener el comportamiento actual como fallback si no se inyecta ninguno
- conservar intacta la lógica de render, SVG e índices

### src/util_bbdd/doc/word_generator.py
- permitir recibir un `graph_generator` opcional en `generate_document`
- mantener el fallback actual si no se proporciona
- seguir reutilizando el `GraphDocument` ya calculado dentro del propio flujo Word

### tests/unit/test_database_documentation.py
- validar que en una ejecución multi-formato con diagramas se comparte la misma instancia del generador entre Word y HTML
- validar que en ejecución de un único formato el comportamiento sigue siendo compatible

### tests/unit/test_doc_generators_helpers.py
- validar que Word y HTML siguen aceptando `graph_generator=None` y construyen el suyo cuando procede

## código
- no implementar todavía en este paso; esta slice queda preparada y acotada para la siguiente ejecución

## explicación breve
- la mejora de rendimiento natural ya no está en crear otro caché, porque ese caché ya existe en `analysis/base.py`
- el problema real es de alcance de instancia: Word y HTML no comparten hoy el mismo `GraphvizRelationshipGraphExt`, así que no comparten su caché
- la siguiente slice debe resolver exactamente ese punto y nada más

# AUDIT_CODE

## bugs potenciales
- diferencia de opciones entre `_build_graph_generator` de Word y HTML: Word ya pasa `render_dpi`, HTML no
- riesgo de regresión si el parámetro opcional se añade sin mantener compatibilidad posicional en las firmas públicas

## edge cases
- ejecuciones con solo `word`
- ejecuciones con solo `html`
- ejecuciones con `include_diagrams = false`
- tablas por documento en Word mayores que 1, donde la misma instancia debe seguir siendo válida durante todos los chunks

## performance
- beneficio esperado solo cuando la misma ejecución genera más de un formato con diagramas
- no promete mejorar tiempos de una ejecución exclusivamente HTML o exclusivamente Word
- puede reducir recomputación de `GraphDocument` y de lookups asociados a relaciones dentro de una misma corrida

## seguridad
- sin cambios funcionales de superficie en consultas, archivos o entradas de usuario

## tipado
- conviene tipar el parámetro opcional compartido como `GraphvizRelationshipGraphExt | None` si no rompe el estilo del módulo

## deuda técnica
- sigue existiendo duplicidad de builder entre Word y HTML; esta slice puede reducirla, pero no debe forzar una extracción mayor si no aporta valor inmediato

# VERSION

## commit message
- docs(v0.6.1): prepare shared graph generator performance slice

## changelog
- no actualizar todavía; solo preparación de slice

## impacto
- deja decidido el siguiente objetivo implementable sin mezclarlo con refactor amplio ni con nuevas features visuales

## rollback
- eliminar el artefacto de sesión y revertir futuras decisiones asociadas si se decide no seguir esta línea

## pruebas sugeridas
- pytest tests/unit/test_database_documentation.py tests/unit/test_doc_generators_helpers.py -q
- prueba manual generando Word+HTML con diagramas activados y comparando logs de construcción del grafo
