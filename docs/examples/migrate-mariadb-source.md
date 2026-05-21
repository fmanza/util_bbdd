# Migración DDL MariaDB como origen

## Objetivo

Migrar la estructura completa de un schema MariaDB a Oracle, SQL Server o PostgreSQL: generar el
script DDL y, opcionalmente, aplicarlo directamente contra el servidor destino.

## Requisitos

- `util_bbdd` instalado con el driver del motor destino (`cx_Oracle`/`oracledb`, `pymssql`,
  `psycopg2`/`psycopg3`)
- Conexión MariaDB con permisos de lectura sobre `INFORMATION_SCHEMA`
- Opcional: conexión al motor destino activa para ejecución directa

---

## MariaDB → Oracle

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

mariadb_manager = SyncDatabaseManager(
    connection_string="mariadb+mariadbconnector://user:pass@maria-host:3306/ventas",
)

planner = MigrationPlanner(
    source_engine="mariadb",
    target_engine="oracle",
)

plan = planner.plan(connection=mariadb_manager, schema="ventas")
print(format_plan_text(plan))

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Extracto del script Oracle

```sql
CREATE TABLE "CLIENTES" (
  "ID" NUMBER(19) NOT NULL,
  "NOMBRE" VARCHAR2(200),
  "FECHA_ALTA" DATE,
  CONSTRAINT "PK_CLIENTES" PRIMARY KEY ("ID")
);

CREATE SEQUENCE "CLIENTES_SEQ" START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE OR REPLACE TRIGGER "TRG_CLIENTES"
  BEFORE INSERT ON "CLIENTES" FOR EACH ROW
BEGIN
  IF :NEW."ID" IS NULL THEN
    SELECT "CLIENTES_SEQ".NEXTVAL INTO :NEW."ID" FROM DUAL;
  END IF;
END;
/
```

---

## MariaDB → SQL Server

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

mariadb_manager = SyncDatabaseManager(
    connection_string="mariadb+mariadbconnector://user:pass@maria-host:3306/ventas",
)

planner = MigrationPlanner(
    source_engine="mariadb",
    target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
)

plan = planner.plan(connection=mariadb_manager, schema="ventas")
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
```

---

## MariaDB → PostgreSQL

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

mariadb_manager = SyncDatabaseManager(
    connection_string="mariadb+mariadbconnector://user:pass@maria-host:3306/ventas",
)

planner = MigrationPlanner(
    source_engine="mariadb",
    target_engine="postgresql",
    pg_schema="ventas",   # opcional; emite SET search_path = ventas;
)

plan = planner.plan(connection=mariadb_manager, schema="ventas")
print(format_plan_text(plan))

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Extracto del script PostgreSQL

```sql
SET search_path = ventas;

CREATE TABLE "clientes" (
  "id" BIGSERIAL NOT NULL,
  "nombre" VARCHAR(200),
  "fecha_alta" TIMESTAMP,
  PRIMARY KEY ("id")
);
```

---

## Revisar avisos del plan

```python
from util_bbdd import MigrationPlanner
from util_bbdd.migrate import format_plan_markdown

planner = MigrationPlanner(source_engine="mariadb", target_engine="oracle")
plan = planner.plan(connection=mariadb_manager, schema="ventas")

# Reporte en texto
for w in plan.warnings:
    if w.severity in ("ERROR", "WARNING"):
        loc = f"{w.table}.{w.column}" if w.column else w.table
        print(f"[{w.severity}] {loc}: {w.message}")

# Reporte Markdown completo
report = format_plan_markdown(plan)
with open("ventas_migration_report.md", "w", encoding="utf-8") as f:
    f.write(report)
```

---

## Notas de operación

- `AUTO_INCREMENT` se convierte automáticamente según el motor destino (SEQUENCE+TRIGGER en Oracle,
  `IDENTITY(1,1)` en SQL Server, `SERIAL`/`BIGSERIAL` en PostgreSQL)
- Las vistas se incluyen en el script con el SQL original de MariaDB; revisar manualmente la
  compatibilidad de sintaxis con el motor destino
- Identificadores > 30 chars se truncan con sufijo hash en Oracle (límite Oracle 12.1)
- FKs circulares se emiten como `ALTER TABLE ADD CONSTRAINT` al final del script en todos los motores
