# Migración PostgreSQL como Origen

## 1. Descripción General

Genera automáticamente el script SQL de creación de estructura (DDL) de un schema PostgreSQL completo, listo para ejecutarse en Oracle, MariaDB o SQL Server. Cubre tablas, columnas, claves primarias, claves foráneas, índices, vistas y tipos de datos, adaptando cada elemento a las reglas del motor destino.

El flujo de trabajo es idéntico al de otros motores origen: extraer metadatos desde `INFORMATION_SCHEMA` y `pg_catalog` → transformar tipos → emitir DDL ordenado por dependencias.

**Precondiciones:**

- Conexión activa al schema PostgreSQL origen compatible con el gestor de BD
- Driver Python compatible: `psycopg2` o `psycopg3` (param style `%(name)s`)
- El parámetro `schema` corresponde a `TABLE_SCHEMA` en PostgreSQL (habitualmente `'public'`)
- La conexión debe apuntar a la base de datos correcta

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Detección de SERIAL como autoincremento | Columnas SERIAL/BIGSERIAL/SMALLSERIAL se detectan por su `COLUMN_DEFAULT` de tipo `nextval(...)` | Sin detección, la columna se genera sin autoincremento en el destino |
| `CHARACTER VARYING` sin límite → LOB | `character varying` sin longitud produce tipo LOB en el destino (CLOB, LONGTEXT o NVARCHAR(MAX)) | Posible cambio de semántica de almacenamiento; aviso incluido en el plan |
| Índices no-PK via pg_catalog | Los índices secundarios se obtienen de `pg_catalog.pg_index`, no de `INFORMATION_SCHEMA` | Sin este paso, los índices secundarios no se incluyen en el DDL generado |
| Vistas reescritas al destino | El SQL de las vistas se reescribe al dialecto destino con sqlglot (ver [reescritura de vistas](migrate_views.md)); sin sqlglot se emite sin traducir | Aviso de revisión por cada vista |
| FKs circulares al final del script | Las dependencias circulares se emiten como `ALTER TABLE ADD CONSTRAINT` al final | El script completo es ejecutable en orden sin desactivar comprobaciones de FK |

## 3. Casos de Uso

### Flujo principal

```mermaid
flowchart TD
    PL["Planificador\n(source='postgresql')"]
    EX["Extractor PostgreSQL\n(INFORMATION_SCHEMA\npg_catalog)"]
    TR_OR["Transformador → Oracle"]
    TR_MB["Transformador → MariaDB"]
    TR_SS["Transformador → SQL Server"]
    EM["Generadores DDL\n(por motor destino)"]
    OUT["Plan de Migración\n.emit_ddl() → .sql\n.execute(target)"]

    PL --> EX
    EX --> TR_OR & TR_MB & TR_SS
    TR_OR & TR_MB & TR_SS --> EM
    EM --> OUT
```

### Flujos alternativos

**Stored procedures y funciones:** El módulo extrae el cuerpo desde `INFORMATION_SCHEMA.ROUTINES` verbatim con un aviso de revisión manual. La sintaxis PL/pgSQL no se traduce automáticamente.

**Tipos sin equivalente directo:** Tipos PostgreSQL-específicos (`ARRAY`, `TSVECTOR`, `USER-DEFINED`) se mapean al tipo LOB más cercano del motor destino con severidad ERROR en el plan de avisos.

**Límites y exclusiones:**

- Solo soporta PostgreSQL como motor origen (destinos: Oracle, MariaDB, SQL Server)
- No migra filas de datos, solo la estructura (DDL)
- Los comentarios de tabla y de columna se migran (desde 0.21.0); los de vistas y rutinas, no
- Los tipos espaciales, arrays y enums se mapean a tipos de texto con aviso de severidad ERROR
- `asyncpg` usa `$1, $2, ...` como param style; requiere un wrapper para usar con este módulo

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| SERIAL / BIGSERIAL | Tipos PostgreSQL que definen columnas con autoincremento mediante una secuencia interna |
| `TABLE_SCHEMA` | Nombre del schema en PostgreSQL tal como aparece en `INFORMATION_SCHEMA.TABLES` (habitualmente `'public'`) |
| Pass-through | Estrategia que emite el código fuente de rutinas (y de vistas sin sqlglot o con `view_strategy="passthrough"`) sin modificarlo, con aviso de revisión manual |
| `pg_catalog` | Catálogo interno de PostgreSQL que expone metadatos avanzados no disponibles en `INFORMATION_SCHEMA` estándar |
