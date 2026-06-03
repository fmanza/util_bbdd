# Bulk Operations

Operaciones masivas de inserción, actualización y eliminación desde DataFrames de pandas,
con registro de auditoría automático en CSV y soporte de carga paralela por particiones.

---

## BulkCrud

Clase principal para operaciones CRUD en lote. El alias legacy `bulk_crud` sigue disponible
por compatibilidad pero la referencia canónica es `BulkCrud`.

::: util_bbdd.bulk.crud.BulkCrud
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ParallelBulkLoader

Carga masiva paralela distribuyendo los datos en particiones disjuntas, cada una procesada
por un worker independiente con su propia conexión.

::: util_bbdd.bulk._execution.parallel_loader.ParallelBulkLoader
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## AuditManager

Fachada de auditoría que registra cada operación bulk en un CSV persistente y expone
métodos de análisis y exportación del historial.

::: util_bbdd.bulk.audit.AuditManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## AuditTransaction

Context manager que agrupa y registra operaciones bulk bajo un nombre de transacción.

::: util_bbdd.bulk.audit.AuditTransaction
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
