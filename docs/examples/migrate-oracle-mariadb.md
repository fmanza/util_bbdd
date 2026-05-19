# Migración DDL Oracle → MariaDB

## Objetivo

Migrar la estructura completa de un schema Oracle a MariaDB: generar el script DDL y, opcionalmente, aplicarlo directamente contra el servidor destino.

## Requisitos

- `util_bbdd` instalado con el extra de Oracle (`cx_Oracle` o `oracledb`)
- Conexión Oracle con permisos de lectura sobre `ALL_TABLES`, `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS` e `ALL_INDEXES`
- Opcional: conexión MariaDB activa para ejecución directa

## Caso 1 — Generar el script SQL y guardarlo en disco

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner
from util_bbdd.migrate import format_plan_text

# 1. Conexión Oracle existente
oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@host:1521/SERVICE",
)

# 2. Crear el planificador
planner = MigrationPlanner(
    charset="utf8mb4",
    collation="utf8mb4_spanish2_ci",   # español moderno (RAE post-1994)
    number_fallback="DOUBLE",           # NUMBER sin precisión → DOUBLE
)

# 3. Ejecutar el plan (extrae, transforma, consolida avisos)
plan = planner.plan(connection=oracle_manager, schema="VENTAS")

# 4. Revisar avisos antes de aplicar
print(format_plan_text(plan))

# 5. Guardar el script con nombre canónico (ej: ventas_oracle_to_mariadb.sql)
with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
```

### Resultado esperado — `ventas_mariadb.sql` (extracto)

```sql
CREATE TABLE `CLIENTES` (
  `ID` BIGINT NOT NULL AUTO_INCREMENT,
  `NOMBRE` VARCHAR(200),
  `FECHA_ALTA` DATETIME -- AVISO: DATE Oracle contiene hora; usar DATETIME en MariaDB,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish2_ci;

CREATE TABLE `PEDIDOS` (
  `ID` BIGINT NOT NULL AUTO_INCREMENT,
  `CLIENTE_ID` BIGINT,
  `IMPORTE` DECIMAL(10,2),
  PRIMARY KEY (`ID`),
  CONSTRAINT `FK_PEDIDOS_CLIENTES` FOREIGN KEY (`CLIENTE_ID`) REFERENCES `CLIENTES` (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish2_ci;

CREATE INDEX `IDX_PEDIDOS_FECHA` ON `PEDIDOS` (`FECHA_PEDIDO`);
```

## Caso 2 — Aplicar directamente en MariaDB

```python
from util_bbdd import SyncDatabaseManager, MigrationPlanner

oracle_manager = SyncDatabaseManager(
    connection_string="oracle+cx_oracle://user:pass@ora-host:1521/SERVICE",
)
mariadb_manager = SyncDatabaseManager(
    connection_string="mariadb+mariadbconnector://user:pass@maria-host:3306/ventas_nueva",
)

planner = MigrationPlanner(charset="utf8mb4", collation="utf8mb4_unicode_ci")
plan = planner.plan(connection=oracle_manager, schema="VENTAS")

# Solo aplicar si no hay errores críticos
if plan.error_count == 0:
    plan.execute(target_connection=mariadb_manager)
else:
    print(f"Hay {plan.error_count} errores. Revisar el plan antes de aplicar.")
    for w in plan.warnings:
        if w.severity == "ERROR":
            print(f"  ERROR en {w.table}: {w.message}")
```

## Caso 3 — Generar reporte Markdown del plan

```python
from util_bbdd import MigrationPlanner
from util_bbdd.migrate import format_plan_markdown

planner = MigrationPlanner()
plan = planner.plan(connection=oracle_manager, schema="HR")

report = format_plan_markdown(plan)
with open(plan.suggested_filename(suffix="report", ext="md"), "w", encoding="utf-8") as f:
    f.write(report)
```

El reporte incluye: resumen de totales, tabla de avisos por severidad y listado de columnas con tipos origen y destino.

## Caso 4 — Ajustar NUMBER sin precisión a DECIMAL

Útil cuando se necesita exactitud contable en lugar de punto flotante:

```python
planner = MigrationPlanner(
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
    number_fallback="DECIMAL(18,4)",   # en vez del DOUBLE por defecto
)
plan = planner.plan(connection=oracle_manager, schema="CONTABILIDAD")
print(plan.emit_ddl())
```

## Notas de operación

- El script generado no requiere desactivar `FOREIGN_KEY_CHECKS`: las FKs circulares se emiten como `ALTER TABLE` al final
- Los comentarios `-- AVISO:` del DDL son SQL válido (comentarios de línea) y no afectan la ejecución
- Columnas de tipo `ROWID`/`UROWID` quedan comentadas en el script y no se crean en MariaDB
- Para collation español moderno usar `utf8mb4_spanish2_ci`; para español tradicional (ch y ll como letras propias) usar `utf8mb4_spanish_ci`
