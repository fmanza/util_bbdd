# Migración DDL

`MigrationPlanner` traduce el esquema de un motor a DDL de otro y devuelve un `MigrationPlan`. Referencia curada por
motor de origen: [Oracle](migrate_oracle_mariadb.md), [MariaDB](migrate_mariadb_source.md),
[SQL Server](migrate_sqlserver_source.md), [PostgreSQL](migrate_postgresql_source.md), [MySQL](migrate_mysql.md) y
[vistas](migrate_views.md).

---

## MigrationPlanner

::: util_bbdd.migrate.planner.MigrationPlanner
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## MigrationPlan

::: util_bbdd.migrate.ir.models.MigrationPlan
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## MigrationWarning

::: util_bbdd.migrate.ir.models.MigrationWarning
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
