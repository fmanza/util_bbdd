# Migración SQL Server como Origen

## 1. Descripción General

Genera automáticamente el script SQL de creación de estructura (DDL) de un schema SQL Server completo, listo para ejecutarse en Oracle, MariaDB o PostgreSQL. Cubre tablas, columnas, claves primarias, claves foráneas, índices, vistas y tipos de datos, adaptando cada elemento a las reglas del motor destino.

El flujo de trabajo es idéntico al de otros motores origen: extraer metadatos desde `INFORMATION_SCHEMA` y catálogos del sistema (`sys.indexes`, `sys.sql_modules`) → transformar tipos → emitir DDL ordenado por dependencias.

**Precondiciones:**

- Conexión activa al schema SQL Server origen compatible con el gestor de BD
- Driver Python compatible: `pymssql` (param style `%(name)s`) o pyodbc con wrapper
- El parámetro `schema` corresponde a `TABLE_SCHEMA` en SQL Server (habitualmente `'dbo'`)
- La conexión debe apuntar a la base de datos correcta

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Tipos MAX (char_length = -1) | SQL Server usa `-1` como sentinel para `VARCHAR(MAX)`, `NVARCHAR(MAX)` y `VARBINARY(MAX)` | Sin detección, el tipo LOB no se genera correctamente en el destino |
| Columnas IDENTITY detectadas via sys | La detección de columnas IDENTITY usa `COLUMNPROPERTY` del catálogo del sistema | Sin detección, la columna se genera sin autoincremento en el destino |
| Vistas reescritas al destino | El SQL de las vistas se reescribe al dialecto destino con sqlglot (ver [reescritura de vistas](migrate_views.md)); sin sqlglot se emite sin traducir | Aviso de revisión por cada vista |
| `VIEW_DEFINITION` puede truncarse | En versiones SQL Server < 2019, las definiciones de vista largas pueden truncarse a 4000 chars | Vistas largas generarán DDL incompleto; verificar manualmente |
| FKs circulares al final del script | Las dependencias circulares se emiten como `ALTER TABLE ADD CONSTRAINT` al final | El script completo es ejecutable en orden sin desactivar comprobaciones de FK |

## 3. Casos de Uso

### Flujo principal

```mermaid
flowchart TD
    PL["Planificador\n(source='sqlserver')"]
    EX["Extractor SQL Server\n(INFORMATION_SCHEMA\nsys.indexes)"]
    TR_OR["Transformador → Oracle"]
    TR_MB["Transformador → MariaDB"]
    TR_PG["Transformador → PostgreSQL"]
    EM["Generadores DDL\n(por motor destino)"]
    OUT["Plan de Migración\n.emit_ddl() → .sql\n.execute(target)"]

    PL --> EX
    EX --> TR_OR & TR_MB & TR_PG
    TR_OR & TR_MB & TR_PG --> EM
    EM --> OUT
```

### Flujos alternativos

**Stored procedures y funciones:** El módulo extrae el cuerpo T-SQL desde `sys.sql_modules` verbatim con un aviso de revisión manual. La sintaxis T-SQL (variables `@`, `TOP`, `NOLOCK`, `GETDATE()`) no se traduce automáticamente.

**Tipos geoespaciales:** `GEOGRAPHY` y `GEOMETRY` se mapean a tipos de texto con severidad ERROR en el plan de avisos, indicando que requieren revisión manual para conversión espacial.

**Límites y exclusiones:**

- Solo soporta SQL Server como motor origen (destinos: Oracle, MariaDB, PostgreSQL)
- No migra filas de datos, solo la estructura (DDL)
- No soporta columnas computadas, UDTs, tipos alias ni tablas temporales
- Las vistas se reescriben con sqlglot (extra `util_bbdd[migrate]`); sin él, se copian sin reescribir ([reescritura de vistas](migrate_views.md))
- Para pyodbc se necesita un wrapper que adapte el param style `%(name)s` → `?`

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| IDENTITY | Mecanismo de autoincremento en SQL Server; equivale a `AUTO_INCREMENT` (MariaDB), `SERIAL` (PostgreSQL) o `SEQUENCE+TRIGGER` (Oracle) |
| T-SQL | Dialecto SQL propietario de SQL Server con extensiones propias (`@variables`, `TOP`, `NOLOCK`, `GETDATE()`) |
| Pass-through | Estrategia que emite el código fuente de rutinas (y de vistas sin sqlglot o con `view_strategy="passthrough"`) sin modificarlo, con aviso de revisión manual |
| `sys.sql_modules` | Vista del catálogo interno de SQL Server que expone el código fuente de procedimientos, funciones y vistas |
