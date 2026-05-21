# Migración DDL Oracle como origen

## Objetivo

Migrar la estructura completa de un schema Oracle a MariaDB, SQL Server o PostgreSQL: generar el
script DDL y, opcionalmente, aplicarlo directamente contra el servidor destino.

## Requisitos

- `util_bbdd` instalado con el extra de Oracle (`cx_Oracle` u `oracledb`)
- Conexión Oracle con permisos de lectura sobre `ALL_TABLES`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`,
  `ALL_INDEXES` y `ALL_VIEWS`
- Opcional: conexión al motor destino activa para ejecución directa

---

## Oracle → MariaDB

### Caso 1 — Generar el script SQL y guardarlo en disco

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@host:1521/SERVICE",
)

planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_spanish2_ci",
    number_fallback="DOUBLE",
)

plan = planner.plan(connection=oracle_manager, schema="VENTAS")
print(format_plan_text(plan))

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Resultado esperado — extracto del script MariaDB

```sql
CREATE TABLE `CLIENTES` (
  `ID` BIGINT NOT NULL AUTO_INCREMENT,
  `NOMBRE` VARCHAR(200),
  `FECHA_ALTA` DATETIME, -- AVISO: DATE Oracle contiene hora; usar DATETIME en MariaDB
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish2_ci;

CREATE TABLE `PEDIDOS` (
  `ID` BIGINT NOT NULL AUTO_INCREMENT,
  `CLIENTE_ID` BIGINT,
  `IMPORTE` DECIMAL(10,2),
  PRIMARY KEY (`ID`),
  CONSTRAINT `FK_PEDIDOS_CLIENTES` FOREIGN KEY (`CLIENTE_ID`) REFERENCES `CLIENTES` (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish2_ci;
```

### Caso 2 — Aplicar directamente en MariaDB

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner

oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@ora-host:1521/SERVICE",
)
mariadb_manager = SyncDatabaseManager(
    connection_string="mariadb+mariadbconnector://user:pass@maria-host:3306/ventas_nueva",
)

planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
)
plan = planner.plan(connection=oracle_manager, schema="VENTAS")

if plan.error_count == 0:
    plan.execute(target_connection=mariadb_manager)
else:
    print(f"Hay {plan.error_count} errores. Revisar el plan antes de aplicar.")
    for w in plan.warnings:
        if w.severity == "ERROR":
            print(f"  ERROR en {w.table}: {w.message}")
```

---

## Oracle → SQL Server

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@host:1521/SERVICE",
)

planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
)

plan = planner.plan(connection=oracle_manager, schema="VENTAS")
print(format_plan_text(plan))

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Extracto del script SQL Server

```sql
CREATE TABLE [CLIENTES] (
  [ID] BIGINT NOT NULL IDENTITY(1,1),
  [NOMBRE] NVARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
  [FECHA_ALTA] DATETIME2,
  PRIMARY KEY ([ID])
);

CREATE TABLE [PEDIDOS] (
  [ID] BIGINT NOT NULL IDENTITY(1,1),
  [CLIENTE_ID] BIGINT,
  [IMPORTE] DECIMAL(10,2),
  PRIMARY KEY ([ID])
);

ALTER TABLE [PEDIDOS]
  ADD CONSTRAINT [FK_PEDIDOS_CLIENTES] FOREIGN KEY ([CLIENTE_ID]) REFERENCES [CLIENTES] ([ID]);
```

---

## Oracle → PostgreSQL

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@host:1521/SERVICE",
)

planner = MigrationPlanner(
    source_engine="oracle",
    target_engine="postgresql",
    pg_schema="ventas",   # opcional; emite SET search_path = ventas;
)

plan = planner.plan(connection=oracle_manager, schema="VENTAS")
print(format_plan_text(plan))

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Extracto del script PostgreSQL

```sql
SET search_path = ventas;

CREATE TABLE "CLIENTES" (
  "ID" BIGSERIAL NOT NULL,
  "NOMBRE" VARCHAR(200),
  "FECHA_ALTA" TIMESTAMP,
  PRIMARY KEY ("ID")
);

CREATE TABLE "PEDIDOS" (
  "ID" BIGSERIAL NOT NULL,
  "CLIENTE_ID" BIGINT,
  "IMPORTE" NUMERIC(10,2),
  PRIMARY KEY ("ID"),
  CONSTRAINT "FK_PEDIDOS_CLIENTES" FOREIGN KEY ("CLIENTE_ID") REFERENCES "CLIENTES" ("ID")
);
```

---

## Generar reporte Markdown del plan

```python
from util_bbdd import MigrationPlanner
from util_bbdd.migrate import format_plan_markdown

planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
plan = planner.plan(connection=oracle_manager, schema="HR")

report = format_plan_markdown(plan)
with open(plan.suggested_filename(suffix="report", ext="md"), "w", encoding="utf-8") as f:
    f.write(report)
```

El reporte incluye: resumen de totales, tabla de avisos por severidad y listado de columnas con
tipos origen y destino.

---

## Notas de operación

- El script generado no requiere desactivar `FOREIGN_KEY_CHECKS` (MariaDB) ni `NOCHECK` (SQL Server):
  las FKs circulares se emiten como `ALTER TABLE` al final
- Los comentarios `-- AVISO:` del DDL son SQL válido y no afectan la ejecución
- Columnas de tipo `ROWID`/`UROWID` quedan comentadas en el script y no se crean en el motor destino
- Para collation español moderno en MariaDB: `utf8mb4_spanish2_ci`; tradicional: `utf8mb4_spanish_ci`
