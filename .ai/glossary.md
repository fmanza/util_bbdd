# 📚 Glossary - util_bbdd

## Core Concepts

Paquetes, capas y niveles (Foundation, Servicios, Especialización): `.ai/architecture.md` § Capas; la fuente
ejecutable es `LAYER` en `scripts/gen_arquitectura_capas.py`. No se repiten aquí para que no diverjan.

## Key Terms

- **Types**: Aliases unificados (RowOrNone, Rows, QueryParams)
- **Protocols**: Contratos (ConnectionLike, PoolLike, QueryResultLike)
- **Motor**: Engine/dialect de BD (MariaDB, PostgreSQL, Oracle, etc.)
- **Pool**: Conjunto de conexiones reutilizables
- **Manager**: API pública sync o async para operaciones
- **Query Registry**: Registro centralizado de SQL con versiones
- **Metadata Cache**: Esquema en caché con TTL
- **Audit Trail**: CSV con user, timestamp, operación, delta
- **GraphDocument**: Modelo intermedio del grafo con nodos, aristas, niveles y resumen de niveles ocultos
- **DiagramSummary Payload**: Contrato compartido que resume profundidad visible, niveles por sentido y ayudas de navegación para HTML y Word
- **DiagramLegend Payload**: Contrato compartido con leyenda visual de dirección, cardinalidad, tipo de tabla y tipo de relación
- **LevelDirection**: Sentido del recorrido relacional: `incoming`, `outgoing` o `both`
- **Relation Graph**: Grafo de FK/PK con soporte multinivel y agrupación por nivel

## Abbreviations

- **BD**: Base de Datos
- **CRUD**: Create, Read, Update, Delete
- **FK**: Foreign Key
- **PK**: Primary Key
- **TTL**: Time To Live
- **ORM**: Object-Relational Mapping
- **Core**: SQLAlchemy Core (usado aquí; no ORM)
- **RCA**: Root Cause Analysis
