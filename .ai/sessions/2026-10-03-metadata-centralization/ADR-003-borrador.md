# ADR-003: Extracción de metadatos centralizada y por lotes en `util_bbdd.metadata`

> Borrador de la sesión `2026-10-03-metadata-centralization` (fase PLAN). Se publica en
> `docs/adr/ADR-003-metadata-centralizada.md` con el grupo A, tras aprobar el AUDIT_PLAN y las decisiones D9.

## 1. Contexto y Problema

En v0.30.0 la librería lee el diccionario de datos de los motores por **cuatro caminos** a la vez: un registry de 123
consultas en `data/sql_queries.json` (capa 4), 174 constructores de SQL repartidos por `metadata/<motor>/`, una capa de
adaptadores por motor sin ningún uso en producción y 34 llamadas a `Inspector` de SQLAlchemy en `bulk`, `dump`,
`comparar` y `connection`. El mismo dato se obtiene de hasta cinco formas (columnas de PostgreSQL), con tres estilos
de parámetros y, en el registry, con `str.format` sobre literales en lugar de bind parameters.

El contrato público (`SyncMetadataProvider`) solo tiene métodos por tabla, y los consumidores importan SQL de un motor
concreto. Resultado medido contra el banco (PostgreSQL 17, base con 5624 tablas): documentar 50 tablas cuesta 209
consultas de catálogo y 5,1 s; con 500 tablas, 2503 consultas y 70 s solo para recorrer columnas, índices, PK, FK y UK.
La consulta del registry que lee las FK de **una** tabla tarda ≈ 95 ms sea cual sea el tamaño del schema, mientras que
la consulta por schema que ya existe en `metadata/` lee las 4999 FK de un schema de 5000 tablas en 89 ms. Con 500
tablas, recorrerlas tabla a tabla cuesta en catálogo 70 s (PostgreSQL), 121 s (SQL Server) y 365 s (Oracle); leer el
mismo schema por tipo de objeto, 0,16 s, 0,22 s y 0,27 s. En Oracle, además, el SQL con literales fuerza un hard parse
por tabla: con bind variables las mismas consultas bajan de 749 a 113 ms por tabla.

Fuerzas: el usuario autoriza romper la API pública; la Regla #6 impide a `connection/` y `query/` (capa 4) importar
`metadata/` (capa 5); los consumidores de escritura (`bulk`, `dump`) necesitan objetos y tipos de SQLAlchemy.

## 2. Decisión

1. `metadata/` (capa 5) es el **único** lugar con SQL de catálogo y con reflexión `Inspector`. El SQL de catálogo de
   `data/sql_queries.json` se traslada a `metadata/<motor>/catalog.py`; `query/` conserva solo las consultas con nombre
   del usuario.
2. **Lectura por lotes**: `MetadataSource.snapshot(schema, kinds, tables)` devuelve un `SchemaSnapshot` inmutable;
   cada tipo de objeto se lee con **una consulta por schema** y se carga de forma perezosa. Los métodos por tabla de
   los managers se mantienen como fachada sobre el snapshot.
3. **Dos vistas con criterio único**: catálogo neutro (SQL propio) para leer, documentar y migrar; reflexión
   SQLAlchemy (`get_multi_*` + SQL por schema donde el dialect va tabla a tabla) solo cuando el consumidor necesita
   tipos u objetos `Table`.
4. **Un contrato por motor** (`CatalogDialect`: consulta + parseo por tipo de objeto) y **un estilo de parámetros**
   (`:nombre`, traducido al `paramstyle` del driver). Registrar un motor nuevo no toca a los consumidores.
5. **Una caché** por fuente con clave `(engine, database, schema, kind)`, *single-flight* sync/async, LRU por schema e
   invalidación explícita tras DDL propio.
6. Se retiran los adaptadores sin uso (`SourceAdapter*`/`RoutineAdapter*`, `fetch_*_sync`/`_async`), las cachés
   paralelas y la excepción de `comparar/` en la Regla #2.

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Consultas de catálogo O(tipos de objeto) por schema en lugar de O(tablas) en `doc`, `analysis`, `dump` y managers (cifras en el baseline de la sesión) |
| Ventaja | Un solo sitio por motor y objeto: soportar un motor nuevo es un módulo `catalog.py` |
| Ventaja | Bind parameters en todo el SQL de catálogo: sin `str.format` sobre literales y con reutilización de plan |
| Compromiso | Ruptura de API: `get_*` devuelven modelos tipados; `execute_query_many("obtener_tablas")` y `UpdateAutoIncrement` en `connection.mariadb` desaparecen |
| Compromiso | La primera lectura de un schema enorme trae el schema entero (válvula: `tables=`) |
| Riesgo aceptado | Diferencias de normalización entre caminos antiguos y nuevos; mitigadas con tests de caracterización por motor |
| Deuda técnica | HSQLDB sin banco: su `catalog.py` queda pendiente de verificación |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| Paquete nuevo `catalog/` | Empezar limpio | Dos paquetes con la misma responsabilidad; mover caché y contratos igualmente | Sin beneficio frente a ampliar `metadata/` |
| Solo `Inspector` de SQLAlchemy | Mantenido por terceros | Solo agrupa por schema en PostgreSQL y Oracle; no da routines, parámetros, charset ni almacenamiento | Cobertura y rendimiento insuficientes |
| Derivar tipos SQLAlchemy del snapshot neutro | Un solo backend | Reimplementar el parseo de tipos de 7 dialects | Riesgo alto en `bulk` |
| Mantener el registry JSON y añadir consultas por schema | Cambio menor | Conserva `str.format`, la capa 4 con SQL de catálogo y los caminos duplicados | No resuelve la centralización |

## 5. Estado y Revisión

**Estado:** PROPUESTO

Borrador de la fase PLAN; pendiente de AUDIT_PLAN y de las decisiones D9 (Redshift/Snowflake, forma pública de `get_*`).

Fecha de última revisión: 2026-10-03
