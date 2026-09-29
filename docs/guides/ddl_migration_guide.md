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
- Un `SyncDatabaseManager` **activo** del motor origen con permisos de lectura sobre sus catálogos de metadatos (p. ej. en Oracle: `ALL_TABLES`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_INDEXES`, `ALL_VIEWS`).
- El nombre del **schema/owner** a migrar (sensible a mayúsculas en Oracle; en SQL Server es el `TABLE_SCHEMA`, p. ej. `dbo`).
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
    charset="utf8mb4",                  # solo aplica a destino MariaDB (por defecto)
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
nombre = plan.suggested_filename()          # p. ej. hr_oracle_to_mariadb_20260604.sql
with open(nombre, "w", encoding="utf-8") as f:
    f.write(ddl)
```

Para aplicarlo directamente en el destino (tras revisar los avisos, ver §4):

```python
# target = SyncDatabaseManager("mariadb", {...})
plan.execute(target_connection)             # ejecuta sentencia a sentencia
```

### 3.5 Vistas: reescritura al dialecto destino

El SQL de cada vista se reescribe al dialecto destino con [sqlglot](https://github.com/tobymao/sqlglot), una
dependencia **opcional**:

```bash
pip install "util_bbdd[migrate]"
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
  `CONNECT BY PRIOR a = b`, con `LEVEL`, `SYS_CONNECT_BY_PATH` y `CONNECT_BY_ROOT`) y el generador
  `FROM dual CONNECT BY LEVEL <= n` en una CTE recursiva, con un aviso `WARNING` «VIEW (jerarquía)» sobre el límite de
  recursión del destino y los ciclos;
- lleva un aviso `INFO` de revisión y, si el origen o el destino es Oracle, un `WARNING` de semántica: en Oracle la
  cadena vacía es `NULL` y `||` ignora los `NULL`.

Una vista que no se puede reescribir de forma fiable se copia **sin reescribir** con un aviso `WARNING` que dice el
motivo: `CONNECT BY` fuera del subconjunto convertible (`NOCYCLE`, `ORDER SIBLINGS BY`, joins, condiciones `PRIOR`
múltiples, `CONNECT_BY_ISLEAF`…), `ROWNUM` fuera de un límite de filas (en la lista de columnas o junto a un `ORDER BY` de la misma consulta),
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
| Stored procedures sin traducir | Las rutinas se emiten *verbatim* (pass-through) con aviso | Revisa y adapta manualmente la sintaxis al dialecto destino |
| Vistas sin reescribir | sqlglot no instalado, `view_strategy="passthrough"` o construcción sin traducción fiable (aviso `VIEW (sin reescribir)`) | `pip install "util_bbdd[migrate]"`; si persiste, adapta esa vista a mano |
| Vista reescrita con otro resultado | Semántica distinta entre motores (Oracle: cadena vacía = `NULL`) | Revisa los avisos `VIEW (semántica Oracle)` y los datos con cadenas vacías |
| FKs a tablas fuera del schema migrado | Referencias externas excluidas del script | Gestiona esas FKs manualmente tras la migración |
| Identificadores demasiado largos | Superan el límite del motor destino | Se truncan con sufijo hash determinista; cada truncado queda como aviso |
| Columnas `ROWID`/`UROWID` (Oracle) | Sin equivalente en el destino | Se omiten con un comentario SQL explicativo en su lugar |

Para un script completo por motor origen, ver los ejemplos de migración
([Oracle](../examples/migrate_oracle_mariadb.md), [MariaDB](../examples/migrate_mariadb_source.md),
[SQL Server](../examples/migrate_sqlserver_source.md), [PostgreSQL](../examples/migrate_postgresql_source.md)).
