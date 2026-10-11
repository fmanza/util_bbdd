# Ejemplo: Migración DDL Oracle → MariaDB / SQL Server / PostgreSQL

## 1. Contexto del Ejemplo

Genera automáticamente el script DDL de un schema Oracle para ejecutarlo en MariaDB, MySQL, SQL Server o PostgreSQL, adaptando tipos de datos, autoincremento y FKs circulares al dialecto destino.

Resuelve la pregunta "¿cómo paso mi estructura Oracle a otro motor sin reescribir el DDL a mano?" de forma reproducible: cada decisión de conversión queda registrada como aviso con nivel de severidad.

## 2. Implementación de Referencia

```python
--8<-- "examples/migrate_oracle_mariadb.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`MigrationPlanner.plan()`**: lee los metadatos del owner en las vistas `ALL_*` de Oracle, una consulta por tipo de objeto (ADR-003): el usuario debe ver los objetos del schema. Transforma tipos y genera el plan. No modifica la BD origen.
- **`plan.error_count`**: verificar antes de `plan.execute()`. Si hay errores de severidad `ERROR`, el script generado puede tener columnas comentadas o tipos inválidos que requieren revisión manual.
- **`number_fallback`**: controla el tipo destino para columnas `NUMBER` Oracle sin precisión explícita. Default `"DOUBLE"`; `"DECIMAL(38,10)"` o `"DECIMAL(18,4)"` si se requiere exactitud numérica.
- **FKs circulares**: las dependencias circulares se emiten como `ALTER TABLE ADD CONSTRAINT` al final del script, haciendo el DDL ejecutable en orden sin desactivar comprobaciones.

Para Oracle → SQL Server:

```python
planner = MigrationPlanner(
    source_engine="oracle", target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",
)
```

Para Oracle → PostgreSQL:

```python
planner = MigrationPlanner(
    source_engine="oracle", target_engine="postgresql",
    pg_schema="hr",  # emite SET search_path = hr;
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/migrate_oracle_mariadb.py

# Ejecución (requiere servidor Oracle con el schema HR u otro schema accesible; verificado contra el banco)
# Sustituir credenciales antes de ejecutar
python docs/examples/migrate_oracle_mariadb.py
```

El script DDL se guarda con nombre sugerido por `plan.suggested_filename()` (`<schema>_<origen>_to_<destino>.sql`, p. ej. `hr_oracle_to_mariadb.sql`).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Migración Oracle como Origen](../functional/migrate_oracle_mariadb.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [API Migración Oracle](../api/migrate_oracle_mariadb.md) — API de `MigrationPlanner`, transformadores y emitters
- **Ejemplos relacionados**: [Migración MariaDB](migrate_mariadb_source.md) — patrón equivalente con origen MariaDB
