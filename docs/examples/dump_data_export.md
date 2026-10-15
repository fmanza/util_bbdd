# Ejemplo: Volcado de Datos entre Motores

## 1. Contexto del Ejemplo

Copia todos los datos de un esquema PostgreSQL a un esquema SQL Server respetando automáticamente el orden de las FKs, limpiando el destino antes de cargar y generando un informe Excel de auditoría.

Resuelve el caso de actualizar un entorno de analítica con datos de producción (full refresh): tablas, FKs, columnas omitidas y errores quedan documentados en el informe Excel al finalizar.

## 2. Implementación de Referencia

```python
--8<-- "examples/dump_data_export.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`DumpConfig.chunk_size`**: filas por lectura del origen (default 5000; el ejemplo usa 1000). En destinos MariaDB/MySQL con filas grandes (`TEXT`/`JSON`), reducirlo si un lote supera `max_allowed_packet`.
- **`truncate_target=True`**: vacía el destino antes de cargar en orden inverso topológico (respetando FKs). Con `False`, los datos se añaden al existente (modo append); riesgo de duplicados si las PKs ya existen.
- **`SyncDatabaseManager.get_sqlalchemy_engine()`**: para destino MariaDB, usar este método en lugar de `create_engine()` directamente, ya que incluye automáticamente `pool_pre_ping=True` y `pool_recycle=3600` para evitar `Server has gone away`.
- **Best-effort**: un fallo en una tabla no detiene el volcado. Revisar el informe Excel para identificar las tablas con `ERROR` o `MISSING_TARGET`.

```python
# Volcado cross-engine con SyncDatabaseManager (MariaDB destino)
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.dump import DumpConfig, DumpOrchestrator
from pathlib import Path

dst_mgr = SyncDatabaseManager("mariadb", {
    "host": "replica-server", "user": "writer",
    "password": "secret", "database": "replica_db",
})
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_mgr.get_sqlalchemy_engine(),  # pool_pre_ping incluido
    chunk_size=500,
    output_dir=Path("reports"),
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/dump_data_export.py

# Ejecución (requiere engines de origen y destino accesibles, con las tablas ya creadas en el destino; verificado contra el banco)
python docs/examples/dump_data_export.py
```

El informe Excel `reports/dump_report_<timestamp>.xlsx` contiene hojas de Auditoría Tablas, Tablas Faltantes y Columnas Inexistentes, y, si aplican, Índices (con `manage_indexes=True`), Auditoría Bulk (con `bulk_audit_path`) y Secuencias PK (con `sync_pk_sequences=True`, el valor por defecto). La última hoja, Condiciones del motor, recoge siempre la verificación de `EngineReadinessAdvisor` del origen y del destino.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Volcado entre Esquemas](../functional/dump_data_export.md) — 7 fases del volcado y palancas de rendimiento
- **Referencia técnica**: [Orquestador de Volcado](../api/dump.md) — API de `DumpConfig`, `DumpOrchestrator` y `DumpResult`
- **Referencia técnica**: [Generador de Reportes](../api/dump_reporter.md) — estructura del informe Excel de auditoría
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — inserción básica sin volcado completo
