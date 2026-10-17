# Ejemplo: Migración MySQL → PostgreSQL

## 1. Contexto del Ejemplo

Traduce el esquema de una base MySQL (tablas, claves, índices y tipos) a un script DDL de PostgreSQL con
`MigrationPlanner`, y muestra los avisos de los tipos que no tienen equivalente directo. MySQL como origen reutiliza
las capas de MariaDB; la diferencia está en el driver de la conexión y en las versiones admitidas.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_mysql.py"
```

## 3. Explicación del Código

- **`db_type="mysql"`**: el manager se conecta con PyMySQL (extra `util_bbdd[mysql]`), no con MariaDB
  Connector/Python.
- **Avisos**: `format_plan_text(plan)` resume el plan y sus avisos. Un `ENUM` pasa a `TEXT` con un `WARNING` que
  propone `CREATE TYPE ... AS ENUM`. Los avisos `ERROR` (`plan.error_count`) impiden `plan.execute()`, no
  `emit_ddl()`.
- **`AUTO_INCREMENT`**: pasa a `SERIAL` en PostgreSQL.
- **Índices de las FK**: MySQL crea un índice por cada clave foránea; se migra como índice normal (`cliente_id`).
- **MySQL como destino**: con `target_engine="mysql"`, la collation por defecto es `utf8mb4_0900_ai_ci`; se puede
  indicar otra válida en MySQL con `collation=` (p. ej.
  `MigrationPlanner(source_engine="mariadb", target_engine="mysql", collation="utf8mb4_bin")`).

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/migrate_mysql.py

# Ejecución contra un MySQL accesible (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla)
export UTIL_BBDD_EXAMPLE_URL="mysql+pymysql://reader:secret@mysql-host:3306/ventas"
export UTIL_BBDD_EXAMPLE_SCHEMA="ventas"  # opcional; por defecto ventas
python docs/examples/migrate_mysql.py
```

Resultado con el schema de `tests/integration/test_docs_examples_engines.py` (`zz_ex_clientes` con un `ENUM` y
`zz_ex_pedidos` con una FK):

```text
======================================================================
PLAN DE MIGRACIÓN: MYSQL → POSTGRESQL
Schema origen: zz_util_bbdd_ex_mysql
Tablas: 2
Rutinas: 0
Avisos: 0 ERROR / 1 WARNING / 0 INFO
======================================================================

AVISOS:
----------------------------------------------------------------------

[WARNING]
  zz_ex_clientes.estado: ENUM mapeado a TEXT; considerar CREATE TYPE ... AS ENUM (...) para restricción de dominio
    → TEXT
    → CREATE TYPE name AS ENUM (...)

Avisos ERROR: 0
Script guardado en: zz_util_bbdd_ex_mysql_schema_postgresql.sql
```

Script generado:

```sql
CREATE TABLE "zz_ex_clientes" (
    "id" SERIAL,
    "estado" TEXT NOT NULL, -- AVISO: ENUM → TEXT; considerar CREATE TYPE AS ENUM para restricción de dominio
    CONSTRAINT "PK_zz_ex_clientes" PRIMARY KEY ("id")
);

CREATE TABLE "zz_ex_pedidos" (
    "id" INTEGER NOT NULL,
    "cliente_id" INTEGER NULL,
    CONSTRAINT "PK_zz_ex_pedidos" PRIMARY KEY ("id"),
    CONSTRAINT "zz_ex_pedidos_ibfk_1" FOREIGN KEY ("cliente_id") REFERENCES "zz_ex_clientes" ("id")
);

CREATE INDEX "cliente_id" ON "zz_ex_pedidos" ("cliente_id");
```

Ese test lo ejecuta contra el banco del proyecto.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración MySQL (origen y destino)](../functional/migrate_mysql.md) — versiones,
  casos de uso y límites
- **Referencia técnica**: [API MySQL (origen y destino)](../api/migrate_mysql.md) — parámetros y diferencias con
  MariaDB
- **Ejemplos relacionados**: [Migración MariaDB (origen)](migrate_mariadb_source.md) — el mismo patrón con MariaDB
