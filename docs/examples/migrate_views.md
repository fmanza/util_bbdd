# Ejemplo: Migración de Vistas (PostgreSQL → MySQL)

## 1. Contexto del Ejemplo

El SQL de una vista está escrito en el dialecto de su motor: copiarlo tal cual a otro motor suele fallar. Con
`view_strategy="transpile"`, `MigrationPlanner` reescribe cada vista al dialecto destino con sqlglot y deja un aviso
para revisarla; `MigrationPlan.validate_views()` comprueba después que el SQL resultante es válido en el destino.

El ejemplo lee un schema PostgreSQL con una vista que usa `ILIKE` (que MySQL no tiene), la migra a MySQL y la valida.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_views.py"
```

## 3. Explicación del Código

- **Estrategia**: `"transpile"` exige sqlglot (extra `util_bbdd[migrate]`) y lanza `ImportError` sin él. `"auto"`, la
  opción por defecto, reescribe si sqlglot está instalado y si no copia la vista sin reescribir, con el aviso
  `VIEW_NOT_REWRITTEN`.
- **Avisos por vista**: están en `vista.warnings`. Para filtrarlos, usa `code` (`VIEW_REWRITTEN`,
  `VIEW_NOT_REWRITTEN`, `VIEW_EXTERNAL_REFERENCE`…), no el texto.
- **Validación según el destino**: con MySQL, MariaDB u Oracle es sintáctica con sqlglot (`method="syntax"`) y no
  necesita conexión. Con PostgreSQL o SQL Server es transaccional: hay que pasar la conexión al destino
  (`plan.validate_views(destino)`), crea las tablas y vistas en una transacción y la deshace.
- **Revisión manual**: el DDL marca las vistas reescritas con `-- NOTE: requires manual review`. Aquí `ILIKE` pasa a
  `LOWER(...) LIKE LOWER(...)`, equivalente salvo por la collation del destino.

## 4. Ejecución y Pruebas

```bash
# sqlglot para la reescritura de vistas
pip install "util_bbdd[migrate] @ git+https://github.com/fmanza/util_bbdd.git@v4.3.0"

# Validación sintáctica
python -m py_compile docs/examples/migrate_views.py

# Ejecución contra un PostgreSQL accesible (sin UTIL_BBDD_EXAMPLE_URL explica cómo configurarla)
export UTIL_BBDD_EXAMPLE_URL="postgresql+psycopg://reader:secret@pg-host:5432/ventas"
export UTIL_BBDD_EXAMPLE_SCHEMA="ventas"  # opcional; por defecto public
python docs/examples/migrate_views.py
```

Resultado con el schema de `tests/integration/test_docs_examples_engines.py`: una tabla `zz_ex_clientes` y una vista
`zz_ex_clientes_a` con `WHERE nombre ILIKE 'a%'`.

```text
Vista zz_ex_clientes_a: SELECT zz_ex_clientes.`id` AS `id`, zz_ex_clientes.`nombre` AS `nombre` FROM `zz_ex_clientes` AS zz_ex_clientes WHERE (LOWER(zz_ex_clientes.`nombre`) LIKE LOWER('a%'))
  INFO VIEW_REWRITTEN: SQL de la vista reescrito de PostgreSQL a MySQL (sqlglot); revisar que la semántica se conserva (NULL, collation, redondeos)
Validación zz_ex_clientes_a [syntax]: válida
Script guardado en: zz_ex_views_views_mysql.sql
```

El script DDL se guarda como `<schema>_views_mysql.sql`, con las tablas y las vistas. Ese test lo ejecuta contra el
banco del proyecto.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración de vistas](../functional/migrate_views.md) — qué se reescribe y qué no
- **Referencia técnica**: [API Vistas](../api/migrate_views.md) — estrategias, códigos de aviso y validación
- **Guía**: [Migración DDL entre motores § 3.5](../guides/ddl_migration_guide.md) — paso a paso
- **Ejemplos relacionados**: [Migración PostgreSQL (origen)](migrate_postgresql_source.md) — tablas de PostgreSQL a
  MariaDB
