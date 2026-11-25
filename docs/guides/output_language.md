# Idioma de los resultados

## 1. Objetivo

Generar los informes y la documentación de `util_bbdd` en español o en inglés (desde 5.10.0). El idioma se elige con
el parámetro `locale` de cada punto de entrada que produce ficheros para personas:

| Punto de entrada | Salidas | Parámetro |
|---|---|---|
| `DatabaseDocumentation` | Word, Excel, HTML y Markdown | `locale="en"` |
| `SchemaDiffReporter` | Informes de comparación (HTML, Excel, Word, Markdown y comentarios del SQL) | `locale="en"` (solo por nombre) |
| `DumpConfig` | Informe Excel del volcado | `locale="en"` |
| `AuditManager` | Resumen Excel y HTML de la auditoría | `locale="en"` |

El valor por defecto es `"es"`, así que el código existente genera exactamente lo mismo que antes.

## 2. Requisitos Previos

- `util_bbdd` 5.10.0 o posterior (ver [Instalación](../installation.md)).
- Nada más: los textos van dentro del paquete (`util_bbdd/data/i18n/`) y no hay dependencias nuevas.

## 3. Pasos

### Paso 1 — Documentación de la base de datos

```python
from pathlib import Path

from util_bbdd import SyncDatabaseManager
from util_bbdd.doc import DatabaseDocumentation

with SyncDatabaseManager("sqlite", {"database": "ventas.db"}, use_pool=False) as manager:
    result = DatabaseDocumentation(
        manager,
        Path("docs_bd"),
        imprimir={"tablas": {"imprimir_tablas": True, "columnas": True}},
        formatos=["excel", "html", "markdown"],
        locale="en",
    ).generate()
```

Sin `headers_file`, las cabeceras de las tablas salen del fichero por defecto de cada idioma
(`doc/data/headers_config.json` o `doc/data/headers_config.en.json`). Si pasas tu propio `headers_file`, se usa tal
cual en cualquier idioma.

### Paso 2 — Informes de comparación

```python
from pathlib import Path

from sqlalchemy import create_engine, inspect

from util_bbdd import SchemaComparator
from util_bbdd.comparar import SchemaDiffReporter

diff = SchemaComparator().compare(inspect(create_engine("sqlite:///a.db")), inspect(create_engine("sqlite:///b.db")))
SchemaDiffReporter(sql_dialect="sqlite", locale="en").render_all(diff, Path("informes"))
```

### Paso 3 — Informe del volcado y auditoría

```python
from pathlib import Path

from sqlalchemy import create_engine

from util_bbdd import DumpOrchestrator
from util_bbdd.bulk import AuditManager
from util_bbdd.dump import DumpConfig

origen = create_engine("sqlite:///a.db")
destino = create_engine("sqlite:///b.db")
DumpOrchestrator(DumpConfig(source_engine=origen, target_engine=destino, output_dir=Path("reports"), locale="en")).run()

audit = AuditManager("audit.csv", locale="en")
audit.exportar_resumen_html()
```

## 4. Verificación

- HTML: la etiqueta `<html lang="…">` indica el idioma de la página.
- Excel: los nombres de hoja cambian con el idioma (por ejemplo, «Auditoría Tablas» → «Table Audit» en el informe del
  volcado). Si un proceso tuyo busca una hoja por su nombre, usa el del idioma que generas.
- Markdown: `catalog.json`, `manifest.json`, `changes.json`, el front matter y las rutas (`tables/…`) son iguales en
  los dos idiomas, así que `markdown.previous` compara bien una generación en español con otra en inglés.

## 5. Qué cambia y qué no

| Cambia con el idioma | No cambia |
|---|---|
| Títulos, secciones, cabeceras, nombres de hoja, avisos y textos fijos | Metadatos de la base de datos: nombres, comentarios, tipos, DDL |
| Separadores de los números escritos como texto: `1.234.567` y `1,50` en español; `1,234,567` y `1.50` en inglés | Fechas: siempre ISO 8601 (`2026-11-25 14:30:00`), que se leen igual en los dos idiomas |
| `lang` del HTML y la ordenación de las tablas del HTML | Números guardados como número en Excel: los muestra Excel con la configuración de quien abre el libro |
| | Datos para máquinas: JSON de auditoría, `catalog.json`, front matter, nombres de fichero |
| | Columnas de las hojas de auditoría (`tabla`, `operacion`…), que son las del CSV |
| | Mensajes de excepciones y de log, y las recomendaciones de `EngineReadinessAdvisor` en la hoja «Condiciones del motor» |

## 6. Variantes y Solución de Problemas

- **`ValueError: Idioma no soportado`** (`DocumentationConfigError` en `DatabaseDocumentation`): `locale` solo admite
  `"es"` y `"en"`, en minúsculas.
- **El resumen HTML de auditoría en español muestra `1.234.567` donde antes salía `1,234,567`**: es la corrección de
  5.10.0; antes el HTML en español usaba los separadores ingleses.
- **Siguen apareciendo frases en español en un informe en inglés**: si están en la hoja «Condiciones del motor», son
  recomendaciones de `EngineReadinessAdvisor` y no se traducen; si son mensajes de error del motor, vienen del driver.
