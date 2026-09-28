# Dump — Autodoc

Documentación generada automáticamente desde los docstrings del módulo
`util_bbdd.dump`. Para la referencia técnica curada con diagramas y contratos
detallados, ver [Orquestador](dump.md) y [Generador de Reportes](dump_reporter.md).

---

## DumpOrchestrator

Orquesta el volcado completo en 7 fases: introspección → análisis FK → gestión de
constraints → limpieza → carga → rehabilitación → informe Excel.

::: util_bbdd.dump.orchestrator.DumpOrchestrator
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## DumpConfig

Configuración inmutable de un volcado. Se pasa al constructor de `DumpOrchestrator`.

::: util_bbdd.dump._models.DumpConfig
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## DumpResult

Resultado completo retornado por `DumpOrchestrator.run()`.

::: util_bbdd.dump._models.DumpResult
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## DumpReporter

Genera el informe Excel de auditoría a partir del resultado del volcado.

::: util_bbdd.dump.reporters.DumpReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## TableDumpResult

Resultado del volcado de una tabla individual. Accesible en `DumpResult.table_results`.

::: util_bbdd.dump._models.TableDumpResult
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## DumpAuditSummary

Métricas de auditoría de inserts extraídas del CSV de `bulk.audit` al finalizar
el volcado. Accesible en `DumpResult.audit_summary` cuando `bulk_audit_path` está
configurado.

::: util_bbdd.dump._models.DumpAuditSummary
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ConstraintManager

Gestiona la desactivación y reactivación de constraints en el motor destino.

::: util_bbdd.dump._constraints.ConstraintManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ConstraintResult

Resultado de rehabilitar una constraint individual en el destino.

::: util_bbdd.dump._models.ConstraintResult
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## IndexManager

Gestiona la desactivación y reconstrucción de índices secundarios no únicos
en el motor destino durante el volcado.

::: util_bbdd.dump._indexes.IndexManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## IndexActionResult

Resultado de gestionar (deshabilitar/reconstruir) un índice individual.

::: util_bbdd.dump._models.IndexActionResult
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
