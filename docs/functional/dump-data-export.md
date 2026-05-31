# Volcado de Datos entre Esquemas

## Objetivo de negocio

`DumpOrchestrator` copia todos los datos de un esquema/base de datos origen a un esquema/base de datos destino, respetando automáticamente el orden de carga impuesto por las claves foráneas, gestionando constraints por motor y generando un informe Excel de auditoría al finalizar.

Casos de uso típicos:

- Refrescar un entorno de pruebas con datos de producción (PostgreSQL → PostgreSQL)
- Migrar datos durante un cambio de motor (Oracle → SQL Server)
- Sincronizar un esquema de réplica o analítica (MariaDB → PostgreSQL)
- Restaurar un subconjunto de tablas desde un backup en vivo

---

## Precondiciones

| Requisito | Detalle |
|---|---|
| Engines activos | Ambos engines SQLAlchemy deben poder conectarse antes de llamar a `run()` |
| Esquemas existentes | Las tablas destino deben existir (el módulo no aplica DDL, solo datos) |
| Permisos de lectura | El usuario origen necesita SELECT sobre todas las tablas a volcar |
| Permisos de escritura | El usuario destino necesita INSERT, DELETE/TRUNCATE y permisos de constraint management |
| Python 3.12+ | Requerido por `util_bbdd` |

---

## Flujo de las 6 fases

```mermaid
flowchart TD
    A([Inicio]) --> B[Fase 1: Inspección]
    B --> C[Fase 2: Análisis FK]
    C --> D[Fase 3: Deshabilitar constraints]
    D --> E{truncate_target?}
    E -- Sí --> F[Fase 4: Limpiar destino]
    E -- No --> G
    F --> G[Fase 5: Carga best-effort]
    G --> H[Fase 6: Rehabilitar constraints]
    H --> I[Generar informe Excel]
    I --> Z([DumpResult])

    style A fill:#4472C4,color:#fff
    style Z fill:#92D050,color:#333
    style D fill:#ED7D31,color:#fff
    style H fill:#ED7D31,color:#fff
```

### Fase 1 — Inspección

Introspección de origen y destino mediante SQLAlchemy `Inspector`. Se calcula un `SchemaDiff` que identifica tablas y columnas presentes en origen pero ausentes en destino.

### Fase 2 — Análisis topológico

Se detectan las dependencias de clave foránea entre las tablas a volcar. El orden de carga se calcula con el **algoritmo de Kahn** (topological sort):

- Las tablas sin dependencias se cargan primero.
- Las tablas con dependencias circulares (ciclos FK) se detectan y se cargan **al final**, marcadas como `in_cycle=True` en el resultado.
- Las tablas del origen que no existen en el destino se excluyen de la carga y se reportan como `missing_target`.

### Fase 3 — Desactivación de constraints

Antes de la carga, las constraints del destino se desactivan para evitar violaciones de integridad durante la inserción masiva. El método varía por motor:

| Motor | Estrategia |
|---|---|
| **SQL Server** | `ALTER TABLE t NOCHECK CONSTRAINT ALL` (catalog-level, persiste entre conexiones) |
| **MariaDB/MySQL** | `event.listen(engine, "connect", SET FOREIGN_KEY_CHECKS=0)` + `dispose()` del pool (cross-connection safe) |
| **PostgreSQL** | `ALTER TABLE t DISABLE TRIGGER ALL` (catalog-level, requiere OWNER o SUPERUSER) |
| **Oracle** | `DISABLE CONSTRAINT` por constraint individual; filtra automáticamente constraints de sistema (`SYS_C%`) |
| **Otros motores** | No-op con advertencia en el log |

### Fase 4 — Limpieza del destino

Si `truncate_target=True` (por defecto), las tablas destino se vacían antes de la carga, en **orden inverso al topológico** para respetar FKs.

| Motor | SQL usado | Motivo |
|---|---|---|
| **SQL Server** | `DELETE FROM tabla` | TRUNCATE es rechazado aunque las FKs estén en NOCHECK |
| **Todos los demás** | `TRUNCATE TABLE tabla` | Más rápido, no genera log de transacción |

### Fase 5 — Carga best-effort

Las tablas se cargan en el orden topológico calculado. Para cada tabla:

1. Se calculan las **columnas comunes** (intersección case-insensitive entre origen y destino).
2. Se leen los datos en chunks (`chunk_size`, por defecto 5 000 filas).
3. Se insertan mediante `bulk_crud.bulk_insert_from_df()`.
4. Si una tabla falla, se registra el error y **se continúa** con la siguiente (best-effort).

Las tablas sin columnas comunes se marcan como `skipped` sin lanzar error.

### Fase 6 — Rehabilitación de constraints

Al salir del contexto `ConstraintManager` (incluso si se lanzó una excepción durante la carga), las constraints se reactivan. Si una constraint no puede reactivarse (p.ej., datos que infringen la restricción), se registra como `failed` en el informe sin detener el proceso.

---

## Reglas de negocio

- **Solo datos, nunca DDL.** Si una tabla existe en origen pero no en destino, se informa como `missing_target` y se omite.
- **Columnas faltantes se saltan.** Si una columna existe en origen pero no en destino, se omite de la SELECT y se informa como columna omitida (`skipped_columns`).
- **Columnas adicionales en destino se ignoran.** Solo se mapean columnas presentes en ambos extremos.
- **La comparación de nombres de tabla es case-insensitive.** Necesario para interoperabilidad entre motores: PostgreSQL devuelve `orders` (lowercase), MariaDB puede devolver `ORDERS` (uppercase). Ambos se reconocen como la misma tabla. Si dos tablas del destino colisionan al normalizar el case, se emite un `WARNING` y se usa el primer nombre encontrado.
- **La comparación de nombres de columna es case-insensitive.** Necesario para interoperabilidad Oracle (UPPERCASE) ↔ PostgreSQL (lowercase). El `INSERT` usa siempre el nombre canónico del motor destino.
- **Los errores de tabla no detienen el volcado.** Cada tabla es independiente; se registra el error y se continúa.
- **`enable_all()` siempre se ejecuta.** El `ConstraintManager` actúa como context manager y garantiza la rehabilitación aunque la carga falle.
- **El informe Excel se genera siempre**, incluso si hubo errores parciales.

---

## Límites y exclusiones

| Límite | Detalle |
|---|---|
| No aplica DDL | Si la tabla no existe en destino, no se crea automáticamente |
| No soporta secuencias/identidades | Las columnas IDENTITY/AUTOINCREMENT del destino no se resetean |
| Sin transacción global | Cada tabla se inserta en su propia transacción; no hay rollback global |
| Constraint management solo en 4 motores | SQL Server, MariaDB, PostgreSQL, Oracle. Otros: no-op con warning |
| El informe Excel usa openpyxl | Requiere la dependencia `openpyxl` instalada |
| `truncate_target=False` (modo append) | Puede generar duplicados si los datos ya existen en destino |
| MariaDB/MySQL — pool recomendado | El engine destino MariaDB debe crearse con `pool_pre_ping=True` y `pool_recycle=3600` para evitar `Server has gone away`. `SyncDatabaseManager.get_sqlalchemy_engine()` los incluye por defecto. |
| MariaDB/MySQL — `max_allowed_packet` | Tablas con columnas `TEXT`/`BLOB`/`JSON` extensas requieren `chunk_size` reducido (≤ 500) o aumentar `max_allowed_packet` en el servidor. |

---

## Auditoría en bulk.audit

Cuando `DumpConfig.bulk_audit_path` apunta a un fichero CSV de `util_bbdd.bulk.audit`, el volcado integra dos niveles de auditoría:

| Nivel | Qué registra | Dónde se consulta |
|---|---|---|
| **Por lote INSERT** | Tabla, motor, filas, tiempo por chunk | CSV en `bulk_audit_path`; también en `DumpResult.audit_summary` |
| **Por tabla** | Estado, filas origen/destino, columnas omitidas, errores | `DumpResult.table_results` + informe Excel |

Al terminar el volcado, `DumpResult.audit_summary` contiene las métricas agregadas del CSV filtradas al rango temporal del volcado (lotes INSERT realizados desde que comenzó `run()`). Si `bulk_audit_path` es `None` o el CSV no tiene entradas del volcado actual, `audit_summary` es `None`.

El CSV de `bulk.audit` puede acumular operaciones de múltiples volcados y otras operaciones bulk. El filtrado temporal garantiza que `audit_summary` solo refleja este volcado concreto.

---

## Informe Excel de auditoría

El volcado genera automáticamente un fichero `.xlsx` en `output_dir` con tres hojas:

### Hoja 1 — Auditoría Tablas

| Columna | Contenido |
|---|---|
| Tabla | Nombre de la tabla |
| Posición Carga | Orden topológico asignado |
| FK Circular | `Sí` si la tabla pertenece a un ciclo FK |
| Filas Origen | COUNT(*) en origen antes de la carga |
| Filas Destino Antes | COUNT(*) en destino antes de la carga |
| Filas Destino Después | COUNT(*) en destino tras la carga |
| Estado | `SUCCESS`, `ERROR`, `SKIPPED`, `MISSING_TARGET` |
| Columnas Omitidas | Columnas presentes en origen pero ausentes en destino |
| Error | Mensaje de error si aplica |

Al pie de la hoja se añade una sección con constraints que no pudieron rehabilitarse (`failed` o `unverified`).

### Hoja 2 — Tablas Faltantes

Lista de tablas presentes en el origen que no existen en el destino. Incluye el motivo y la acción sugerida (crear la tabla en destino con el DDL del origen).

### Hoja 3 — Columnas Inexistentes

Lista de columnas presentes en el origen pero ausentes en el destino, agrupadas por tabla.

---

## Ver también

- [API Técnica — Volcado de Datos](../api/dump.md)
- [Ejemplo ejecutable — Volcado PostgreSQL → SQL Server](../examples/dump_data_export.md)
- [Comparador de Esquemas](schema-comparison.md) — para analizar diferencias antes de volcar
