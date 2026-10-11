# Guía: Migración DDL entre motores

## 1. Objetivo

Generar automáticamente el script de creación de estructura (DDL) de un esquema completo de un
motor para ejecutarlo en otro, adaptando tipos, autoincremento y FKs circulares al dialecto
destino. Es un **how-to operativo**; para casos de uso y reglas de negocio por motor, ver la
documentación funcional de migración (p. ej. [Oracle como origen](../functional/migrate_oracle_mariadb.md))
y la [referencia técnica](../api/migrate_oracle_mariadb.md).

La migración produce **solo DDL** (estructura), no copia filas. Para mover los datos una vez creada
la estructura, usa la [guía de volcado de datos](dump_guide.md).

**Motores soportados** (origen ≠ destino):

| Rol | Motores |
|---|---|
| Origen | `oracle`, `mariadb`, `mysql`, `sqlserver`, `postgresql` |
| Destino | `oracle`, `mariadb`, `mysql`, `sqlserver`, `postgresql` |

## 2. Requisitos Previos

- Python 3.12+ con `util_bbdd` y el driver del motor **origen** instalado (ver [Instalación](../installation.md)).
- Un `SyncDatabaseManager` **activo** del motor origen (o un `MetadataSource`) con permiso para leer su catálogo: el
  usuario debe ver los objetos del schema (en Oracle, en las vistas `ALL_*` del owner).
- El nombre del **schema/owner** a migrar (en Oracle, en mayúsculas; en SQL Server, el schema, p. ej. `dbo`; en
  MariaDB/MySQL, la base de datos).
- Opcional: un manager del motor **destino** si se desea ejecutar el DDL directamente.

## 3. Pasos

### 3.1 Conectar al motor origen

```python
from util_bbdd.managers import SyncDatabaseManager

source = SyncDatabaseManager("oracle", {
    "host": "ora-prod", "port": 1521, "service_name": "ORCL",
    "user": "hr", "password": "<reemplazar>",
})
```

### 3.2 Configurar el planificador

`MigrationPlanner` valida la configuración en el constructor (lanza `ValueError` si el par
origen/destino no es válido). Los parámetros opcionales dependen del destino:

```python
from util_bbdd.migrate import MigrationPlanner

planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="mariadb",
    number_fallback="DOUBLE",   # tipo para NUMBER Oracle sin precisión
    charset="utf8mb4",                  # solo aplica a destino MariaDB/MySQL (por defecto)
    collation="utf8mb4_uca1400_ai_ci",  # por defecto; requiere MariaDB ≥ 10.10
)
```

Variaciones según destino:

```python
# Oracle → SQL Server
planner = MigrationPlanner(
    source_engine="oracle", target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
)

# Oracle → PostgreSQL
planner = MigrationPlanner(
    source_engine="oracle", target_engine="postgresql",
    pg_schema="hr",  # emite SET search_path = hr;
)
```

### 3.3 Generar el plan

```python
plan = planner.plan(connection=source, schema="HR")
```

`plan()` extrae los metadatos del origen, transforma los tipos al dialecto destino y consolida un
`MigrationPlan` ejecutable. **No modifica** la base de datos origen.

### 3.4 Exportar el DDL (o ejecutarlo)

```python
ddl = plan.emit_ddl()                       # script SQL completo (str)
nombre = plan.suggested_filename()          # <schema>_<origen>_to_<destino>.sql: hr_oracle_to_mariadb.sql
with open(nombre, "w", encoding="utf-8") as f:
    f.write(ddl)
```

Para aplicarlo directamente en el destino (tras revisar los avisos, ver §4):

```python
# target = SyncDatabaseManager("mariadb", {...})
plan.execute(target_connection)             # ejecuta sentencia a sentencia
```

`execute()` aplica las sentencias por una sola conexión del destino, con `commit` tras cada una (con `pg_schema`, el
`SET search_path` inicial afecta a todo el plan). Las sentencias que solo contienen comentarios (rutinas sin cuerpo,
miembros de PACKAGE) no se envían. Si una sentencia falla, lanza `DatabaseOperationError` con su posición y su
primera línea; las anteriores quedan aplicadas.

### 3.5 Vistas: reescritura al dialecto destino

El SQL de cada vista se reescribe al dialecto destino con [sqlglot](https://github.com/tobymao/sqlglot), una
dependencia **opcional**:

```bash
pip install "util_bbdd[migrate] @ git+https://github.com/fmanza/util_bbdd.git@v1.1.0"
```

El parámetro `view_strategy` decide cómo se migran las vistas:

| Valor | Comportamiento |
|---|---|
| `"auto"` (por defecto) | Reescribe con sqlglot si está instalado; si no, copia el SQL sin reescribir |
| `"transpile"` | Reescribe siempre; `ImportError` si sqlglot no está instalado |
| `"passthrough"` | Copia el SQL sin reescribir, con aviso de revisión (comportamiento hasta 0.19.0) |

```python
planner = MigrationPlanner(source_engine="mysql", target_engine="postgresql", view_strategy="auto")
```

Al reescribir, cada vista:

- usa los nombres de tablas, vistas y columnas **del plan** (con las comillas del destino) y pierde el prefijo del
  schema origen;
- traduce funciones y sintaxis del dialecto (`IFNULL`/`ISNULL`/`NVL`, concatenación, `LIMIT`/`TOP`/`FETCH FIRST`,
  funciones de fecha…) y hace explícita la aritmética de fechas (`fecha + 30` de Oracle o PostgreSQL es una suma de
  días, no un número);
- convierte construcciones propias del origen: el outer join `(+)` de Oracle en `LEFT JOIN`; `ROWNUM <= n` en
  `LIMIT`/`TOP`/`FETCH FIRST` (en el top-N con subconsulta ordenada, el límite va dentro de la subconsulta); `ILIKE`
  en `LOWER(...) LIKE LOWER(...)` hacia SQL Server; los agregados de texto (`GROUP_CONCAT`, `LISTAGG`) en
  `STRING_AGG` con el valor convertido a texto hacia PostgreSQL; los nombres de columna declarados en la cabecera de
  una vista de SQL Server (`CREATE VIEW v (a, b) AS ...`) en alias; las jerarquías simples de Oracle (`START WITH` +
  `CONNECT BY PRIOR a = b`, con `AND LEVEL <= n` opcional, `LEVEL`, `SYS_CONNECT_BY_PATH`, `CONNECT_BY_ROOT` y
  `CONNECT_BY_ISLEAF`; `NOCYCLE` y `CONNECT_BY_ISCYCLE` hacia los cuatro destinos; `ORDER SIBLINGS BY` por columnas
  de la tabla, sin el orden en SQL Server) y el generador `FROM dual CONNECT BY LEVEL <= n` en una CTE
  recursiva, con un aviso `WARNING` «VIEW (jerarquía)» sobre el límite de recursión del destino y los ciclos;
- lleva un aviso `INFO` de revisión y, si el origen o el destino es Oracle, un `WARNING` de semántica: en Oracle la
  cadena vacía es `NULL` y `||` ignora los `NULL`.

Una vista que no se puede reescribir de forma fiable se copia **sin reescribir** con un aviso `WARNING` que dice el
motivo: `CONNECT BY` fuera del subconjunto convertible (`ORDER SIBLINGS BY` por una expresión, joins, condiciones distintas de `PRIOR a = b [AND LEVEL <= n]`…), `ROWNUM` fuera de un límite de filas (en la lista de columnas o junto a un `ORDER BY` de la misma consulta),
SQL que sqlglot no analiza o no sabe generar. Las vistas que usan objetos
fuera del schema migrado se reescriben con un aviso de referencia externa.

Antes de ejecutar el plan, valida las vistas contra el destino con `plan.validate_views(destino)`:

```python
for resultado in plan.validate_views(target):   # SyncDatabaseManager (o Engine) del destino
    if not resultado.valid:
        print(resultado.view, resultado.method, resultado.error)
```

| Destino | Método | Qué comprueba |
|---|---|---|
| PostgreSQL, SQL Server | `"transaction"` | Crea las tablas del plan y cada vista en una transacción que se deshace: detecta funciones, columnas y sintaxis inválidas. No deja nada |
| MySQL, MariaDB, Oracle | `"syntax"` | El DDL confirma solo, así que únicamente analiza la sintaxis con sqlglot (`"none"` sin sqlglot) |

Con `include_tables=False` no se crean las tablas (deben existir ya en el destino). Detalle funcional y de API:
[Migración de vistas](../functional/migrate_views.md) y [API Vistas](../api/migrate_views.md).

## 4. Verificación

Antes de ejecutar, **revisa los avisos** y confirma que no hay errores de severidad `ERROR`:

```python
print(f"Avisos: {plan.error_count} ERROR / {plan.warning_count} WARNING / {plan.info_count} INFO")

for w in plan.warnings:
    if w.severity == "ERROR":
        print(f"  [{w.severity}] {w.table}.{w.column}: {w.message}")
```

Los comentarios de tablas y columnas se migran en todos los pares y llegan a la base de datos destino: `COMMENT`
en MariaDB/MySQL, `COMMENT ON` en PostgreSQL y Oracle, y la propiedad extendida `MS_Description` en SQL Server (en el
schema por defecto del usuario destino). Los de vistas se leen de PostgreSQL, SQL Server y Oracle (MySQL/MariaDB no
los admiten) y se aplican después de crear las vistas en PostgreSQL (`COMMENT ON VIEW`), Oracle (`COMMENT ON TABLE`)
y SQL Server (`MS_Description` de tipo `VIEW`); con destino MySQL/MariaDB quedan como `--` en el script, con un aviso
`COMMENT`. Los de rutinas se leen de MySQL/MariaDB (`ROUTINE_COMMENT`), SQL Server (`MS_Description`) y PostgreSQL
(sin sobrecargas: con varias funciones del mismo nombre no se asigna) y van al script como línea `-- COMMENT:`; no se
aplican como sentencia, porque las rutinas se copian tal cual del origen. Oracle no admite comentarios de rutinas.

Cada aviso (`MigrationWarning`) indica **qué** es con `category` y, cuando trata de un tipo de datos, **cuál** con
`source_type` (el tipo en el motor origen):

| `category` | Qué indica | `source_type` |
|---|---|---|
| `TYPE` | Conversión del tipo de una columna | Tipo en el origen |
| `DEFAULT` | Valor por defecto sin traducción fiable | Tipo de la columna |
| `IDENTIFIER` | Nombre truncado al límite del destino | — |
| `IDENTIFIER_CASE_COLLISION` | Nombres que solo difieren en mayúsculas | — |
| `AUTO_INCREMENT` | Autoincrementales, secuencias e identidades | Tipo de la PK, si aplica |
| `FOREIGN_KEY` | Claves foráneas (acciones no soportadas, FK aplazadas) | — |
| `INDEX` | Índices (p. ej. renombrados por colisión de nombre) | — |
| `VIEW` | Vistas (reescritura, construcciones sin traducción) | — |
| `ROUTINE` | Procedimientos, funciones y packages | — |
| `COMMENT` | Comentario recortado al límite del destino (MySQL/MariaDB 1024/2048 caracteres, Oracle 4000 bytes, SQL Server 7500 bytes), o comentario de vista que MySQL/MariaDB no pueden guardar | — |
| `TABLE` | Tabla sin columnas activas (`ERROR`: `execute()` no empieza) | — |

`target_type` es el tipo destino en `TYPE`, el nombre nuevo en `IDENTIFIER` y una etiqueta legible en el resto
(`"VIEW (reescrita)"`, `"(no body)"`…), cuyo texto puede cambiar. Para filtrar esos avisos en código, usa `code`
(desde 0.22.0): un subtipo estable dentro de la categoría. Los avisos de tipos e identificadores no llevan código
(`None`).

| `code` | `category` | Qué indica |
|---|---|---|
| `COLUMN_OMITTED` | `TYPE` | Columna sin equivalente en el destino (`ROWID`), omitida |
| `AUTO_INCREMENT_NO_SEQUENCE` | `AUTO_INCREMENT` | Oracle destino sin `SEQUENCE`/`TRIGGER` para el autoincremental |
| `FK_DEFERRED` | `FOREIGN_KEY` | FK de un ciclo, añadida con `ALTER TABLE` al final |
| `FK_ON_UPDATE_IGNORED` | `FOREIGN_KEY` | `ON UPDATE` sin equivalente en Oracle |
| `INDEX_EXPRESSION_SKIPPED` | `INDEX` | Índice sobre expresiones que no se migra (crearlo a mano) |
| `VIEW_PASSTHROUGH` | `VIEW` | Vista copiada sin reescribir por la estrategia `"passthrough"` (o sin sqlglot) |
| `VIEW_NOT_REWRITTEN` | `VIEW` | Vista sin traducción fiable, copiada sin reescribir (motivo en `message`) |
| `VIEW_REWRITTEN` | `VIEW` | Vista reescrita con sqlglot (`INFO`) |
| `VIEW_ORACLE_SEMANTICS` | `VIEW` | Cadena vacía y `NULL` en Oracle |
| `VIEW_HIERARCHY` | `VIEW` | `CONNECT BY` convertido en CTE recursiva |
| `VIEW_EXTERNAL_REFERENCE` | `VIEW` | La vista usa objetos fuera del schema migrado |
| `VIEW_HEADER_COLUMNS` | `VIEW` | Vista de SQL Server con columnas en la cabecera |
| `VIEW_DEFINITION_UNAVAILABLE` | `VIEW` | Definición no disponible (`WITH ENCRYPTION` o sin permiso) |
| `VIEW_MANUAL_REVIEW` | `VIEW` | Construcción de Oracle que la reescritura léxica no traduce |
| `VIEW_LEXICAL_REWRITE` | `VIEW` | Sustitución léxica de una función de Oracle |
| `VIEW_USER_PSEUDOCOLUMN` | `VIEW` | Pseudocolumna `USER` sustituida |
| `ROUTINE_PASSTHROUGH` | `ROUTINE` | Rutina copiada sin reescribir su cuerpo |
| `ROUTINE_NO_BODY` | `ROUTINE` | Rutina sin cuerpo disponible |
| `ROUTINE_PACKAGE_MEMBER` | `ROUTINE` | Miembro de un PACKAGE de Oracle |
| `COMMENT_TRUNCATED` | `COMMENT` | Comentario recortado al límite del destino |
| `VIEW_COMMENT_UNSUPPORTED` | `COMMENT` | Comentario de vista que MySQL/MariaDB no guardan |
| `TABLE_NO_COLUMNS` | `TABLE` | Tabla sin columnas activas (`ERROR`) |

```python
tipos = [w for w in plan.warnings if w.category == "TYPE"]
clobs = [w for w in plan.warnings if w.source_type == "CLOB"]
sin_reescribir = [w for w in plan.warnings if w.code == "VIEW_NOT_REWRITTEN"]
```

El plan es seguro de aplicar cuando `plan.error_count == 0`. Si hay errores, el DDL puede contener
columnas comentadas o tipos que requieren revisión manual; corrige el origen o el script antes de
`execute()`. Para un informe legible, usa los reporters:

```python
from util_bbdd.migrate import format_plan_text, format_plan_markdown

print(format_plan_text(plan))          # resumen de avisos por severidad
# format_plan_markdown(plan) → tabla Markdown para adjuntar a un PR
```

## 5. Variantes y Solución de Problemas

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| `ValueError` al construir `MigrationPlanner` | Par origen/destino no soportado o `source == target` | Usa motores distintos de la matriz soportada (§1) |
| `plan.error_count > 0` | Tipos sin equivalente directo en el destino | Revisa los avisos `ERROR`, ajusta `number_fallback` o edita el DDL antes de ejecutar |
| Pérdida de exactitud en `NUMBER` (Oracle) | `NUMBER` sin precisión usa el fallback por defecto (`DOUBLE`) | Usa `number_fallback="DECIMAL(38,10)"` |
| Stored procedures sin traducir | El cuerpo de las rutinas no se traduce (pass-through, aviso `ROUTINE_PASSTHROUGH`). Entre MySQL y MariaDB se crean con `execute()` (el `CREATE` se reconstruye desde `INFORMATION_SCHEMA`, sin `DEFINER`); en el resto de pares van comentadas en el script y `execute()` no las envía | Adapta manualmente las rutinas comentadas al dialecto destino. Para crear **funciones** en MySQL con el binlog activo hace falta `SUPER` o `log_bin_trust_function_creators=1` (error 1419) |
| Vistas sin reescribir | sqlglot no instalado, `view_strategy="passthrough"` o construcción sin traducción fiable (aviso `VIEW (sin reescribir)`) | Instalar el extra `migrate` (§3.5); si persiste, adapta esa vista a mano |
| Vista reescrita con otro resultado | Semántica distinta entre motores (Oracle: cadena vacía = `NULL`) | Revisa los avisos `VIEW (semántica Oracle)` y los datos con cadenas vacías |
| FKs a tablas fuera del schema migrado | Referencias externas excluidas del script | Gestiona esas FKs manualmente tras la migración |
| Identificadores demasiado largos | Superan el límite del motor destino | Se truncan con sufijo hash determinista; cada truncado queda como aviso |
| Columnas `ROWID`/`UROWID` (Oracle) | Sin equivalente en el destino | Se omiten con un comentario SQL explicativo en su lugar |

Para un script completo por motor origen, ver los ejemplos de migración
([Oracle](../examples/migrate_oracle_mariadb.md), [MariaDB](../examples/migrate_mariadb_source.md),
[SQL Server](../examples/migrate_sqlserver_source.md), [PostgreSQL](../examples/migrate_postgresql_source.md)).
