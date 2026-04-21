# Refactorización Jinja2 Standalone

## Objetivo

Refactorizar la generación HTML basada en Jinja2 para que deje de depender de plantillas monolíticas en `src/util_bbdd/doc/data` y pase a una estructura más mantenible, con separación entre:

- configuración del motor de plantillas
- macros reutilizables
- layouts base
- páginas concretas

No se ha mantenido compatibilidad hacia atrás con las plantillas HTML antiguas.

## Estructura resultante

La estructura nueva queda así:

```text
src/util_bbdd/doc/
├─ template_engine.py
├─ html_generator.py
└─ templates/
   ├─ layouts/
   │  └─ base_page.j2
   ├─ macros/
   │  └─ common.j2
   └─ pages/
      ├─ detail.html.j2
      ├─ index.html.j2
      └─ collection.html.j2
```

## Decisiones de diseño

### 1. `TemplateEngine` dedicado

Se crea [template_engine.py](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/template_engine.py) para encapsular:

- `FileSystemLoader`
- `Environment`
- `autoescape`
- filtros personalizados
- carga y renderizado de plantillas

Con esto [html_generator.py](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/html_generator.py) deja de conocer detalles del `Environment` y se centra en preparar contexto y renderizar páginas.

### 2. Layout base + macros

Se introduce [base_page.j2](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/templates/layouts/base_page.j2) con bloques:

- `title`
- `head_assets`
- `styles`
- `content`
- `scripts`

También se crea [common.j2](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/templates/macros/common.j2) para agrupar elementos repetitivos:

- tablas simples
- badges de estado
- tarjetas resumen
- secciones laterales
- botones de exportación
- celdas de colección

### 3. Filtros personalizados

Se han movido a Python pequeñas transformaciones repetidas que ensuciaban las plantillas:

- `header_key`
- `status_class`
- `routine_label`

Esto deja las plantillas más legibles y reduce lógica inline.

### 4. Plantillas por página

Las páginas HTML quedan separadas por responsabilidad:

- [detail.html.j2](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/templates/pages/detail.html.j2)
  - detalle de tabla, vista, rutina o almacenamiento
- [index.html.j2](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/templates/pages/index.html.j2)
  - índice principal con panel lateral, resumen y navegación
- [collection.html.j2](/c:/Desarrollo/python/libs/util_bbdd/src/util_bbdd/doc/templates/pages/collection.html.j2)
  - páginas `Ver todo` con búsqueda, ordenación, paginación, exportación y scroll horizontal

### 5. Limpieza

Se eliminan las plantillas HTML antiguas bajo `src/util_bbdd/doc/data`:

- `html_documentation_template.j2`
- `html_index_template.j2`
- `html_collection_template.j2`

## Impacto funcional

La funcionalidad HTML se mantiene:

- índice con resumen y navegación
- páginas detalle
- páginas `Ver todo`
- búsqueda
- ordenación por columna
- paginación cliente
- exportación filtrada
- barra horizontal superior sincronizada
- tooltips para comentarios largos

## Verificación

Pruebas añadidas:

- [test_template_engine.py](/c:/Desarrollo/python/libs/util_bbdd/tests/unit/test_template_engine.py)
  - carga de plantillas
  - renderizado del índice
  - renderizado de colecciones
  - filtros personalizados

Pruebas ya existentes que siguen cubriendo el generador:

- [test_doc_generators_helpers.py](/c:/Desarrollo/python/libs/util_bbdd/tests/unit/test_doc_generators_helpers.py)

## Cómo ejecutar las pruebas

```powershell
python -m py_compile src/util_bbdd/doc/template_engine.py src/util_bbdd/doc/html_generator.py
pytest tests/unit/test_template_engine.py tests/unit/test_doc_generators_helpers.py -q
```

## Resultado

La capa Jinja2 queda desacoplada, más fácil de extender y más consistente con responsabilidad única. El generador HTML sigue usando Jinja2 standalone, pero ahora con una organización mantenible y profesional.
