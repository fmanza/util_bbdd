# Reporters

Generadores de reportes de diferencias de esquema en múltiples formatos.

---

## SchemaDiffReporter

Fachada principal. Coordina todos los reporters y permite generar todos los formatos
desde una sola instancia.

::: util_bbdd.comparar.reporters.facade.SchemaDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## HtmlDiffReporter

Reporte HTML interactivo con filtrado por categoría, búsqueda de texto y diagramas
Mermaid paginados.

::: util_bbdd.comparar.reporters.html_reporter.HtmlDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## SqlDiffReporter

Script SQL de nivelación por dialecto: `generic`, `mariadb`, `mysql`, `postgresql`,
`sqlserver`, `oracle` y `sqlite` (otro valor lanza `SchemaDiffValidationError`).

::: util_bbdd.comparar.reporters.sql_reporter.SqlDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## MarkdownDiffReporter

Reporte Markdown portátil con tablas de diferencias.

::: util_bbdd.comparar.reporters.markdown_reporter.MarkdownDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ExcelDiffReporter

Reporte Excel con múltiples hojas por sección.

::: util_bbdd.comparar.reporters.excel_reporter.ExcelDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## WordDiffReporter

Reporte Word con formato profesional y secciones por categoría.

::: util_bbdd.comparar.reporters.word_reporter.WordDiffReporter
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
