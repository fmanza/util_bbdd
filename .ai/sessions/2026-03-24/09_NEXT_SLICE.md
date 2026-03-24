# PLAN

## decision
- estado: diferida a post-cierre de v0.6.1
- veredicto: no incluir esta slice en el lote previo al cierre de release actual
- motivo operativo: mejora precisión heurística, pero no corrige un bug bloqueante ni una incompatibilidad contractual del estado ya validado

## objetivo
- preparar la siguiente slice funcional posterior a v0.6.1 para endurecer la clasificación visual de tablas puente complejas sin romper el contrato actual de `GraphNode.visual_type`
- reducir falsos negativos y falsos positivos entre `association` y `entity` en esquemas con PK sustituta, índices únicos compuestos o columnas auxiliares de auditoría

## rutas afectadas
- src/util_bbdd/analysis/base.py
- tests/unit/test_analysis_graph_document.py
- opcional: src/util_bbdd/doc/html_generator.py si se decide exponer notas adicionales de heurística

## server/client
- no aplica

## componentes implicados
- `DatabaseRelationshipGraphBase`
- `GraphNode.visual_type`
- metadatos de PK, FK y restricciones únicas
- batería de tests sintéticos de análisis

## tipos necesarios
- no se requiere un nuevo enum
- como máximo, helpers privados para señales heurísticas adicionales

## impactos en auth o roles
- ninguno

## riesgos
- clasificar como `association` una entidad relacional compleja con varias FKs
- endurecer demasiado la heurística y degradar diagramas existentes
- introducir consultas extra de metadatos si no se reutilizan las rutas ya disponibles

# AUDIT_PLAN

## riesgos funcionales
- la semántica visual actual ya es útil; una mejora apresurada puede mover diagramas correctos a una clasificación peor
- hay que distinguir claramente entre tabla puente pura, tabla puente enriquecida y entidad con varias dependencias

## riesgos técnicos
- el modelo actual solo necesita señales mínimas reutilizables: PK, FK, columnas y restricciones únicas
- conviene evitar reglas por motor salvo que la evidencia del repositorio lo justifique
- la heurística debe seguir siendo cacheable y barata dentro de `build_graph_document`

## riesgos de seguridad
- sin cambios nuevos de superficie

## simplificaciones posibles
- usar una combinación de señales simples:
  - PK compuesta subconjunto de FKs
  - UNIQUE compuesta subconjunto de FKs
  - presencia de PK sustituta pero con par relacional único dominante
  - tolerancia explícita para columnas auxiliares como timestamps o usuario de auditoría

# IMPLEMENT

## cambios por archivo

### src/util_bbdd/analysis/base.py
- introducir helpers privados para señales de tabla puente enriquecida
- separar mejor columnas relacionales, columnas técnicas y columnas de negocio reales
- soportar el caso de PK sustituta con UNIQUE compuesta sobre FKs como candidato a `association`

### tests/unit/test_analysis_graph_document.py
- añadir casos para:
  - tabla puente con PK sustituta y UNIQUE compuesta sobre FKs
  - tabla con varias FKs pero identidad de negocio propia que debe seguir siendo `entity`
  - tabla autorreferenciada con columnas auxiliares que debe seguir siendo `hierarchy`

## explicación breve
- la heurística actual ya cubre el caso simple y el caso de PK compuesta
- el siguiente salto útil no es otro cambio visual, sino mejorar la precisión sobre tablas puente reales frecuentes en modelos normalizados

# AUDIT_CODE

## bugs potenciales
- confundir columnas técnicas con columnas de negocio si se usan solo contadores brutos
- sobredetectar `association` cuando una entidad tiene varias FKs pero ciclo de vida propio

## edge cases
- PK sustituta `id` + UNIQUE(`fk_a`, `fk_b`)
- tabla puente con tres FKs y una columna de estado
- tabla de auditoría con dos FKs y múltiples columnas operativas
- tablas sin PK explícita pero con UNIQUE compuesto relacional

## performance
- reutilizar metadatos ya disponibles o cacheados
- no introducir traversal adicional del grafo

## seguridad
- sin cambios de superficie

## tipado
- mantener `TableVisualType` sin cambios

## deuda técnica
- mientras no exista una taxonomía semántica explícita del modelo, la clasificación seguirá siendo aproximada

# VERSION

## commit message
- docs(v0.6.1): prepare bridge-table heuristic hardening slice

## changelog
- no actualizar todavía; solo preparación de slice

## impacto
- deja acotado el siguiente incremento útil de precisión sin abrir nuevos frentes de renderer o UI

## decisión de entrada
- esta slice queda preparada pero fuera del corte actual de v0.6.1
- solo debe adelantarse si aparece evidencia real en una base de prueba o en un reporte de usuario que justifique tratarla como corrección necesaria antes de release

## rollback
- eliminar este artefacto de sesión si se decide no seguir esta línea

## pruebas sugeridas
- pytest tests/unit/test_analysis_graph_document.py -q
- prueba manual con una tabla puente con PK sustituta y UNIQUE compuesto
