# Crear un prompt para mejorar los resultados de las consultas en base de datos he incorporarlo en la versión v0.5.6, incluyendo la visualización del motor de almacenamiento, charset y collation. Además, se debe revisar la compatibilidad con la generación de documentación y aplicar principios SOLID, legibilidad, Clean Code, tests y seguridad. Se documentará el proceso en un archivo markdown y se actualizará el README.md, ARCHITECTURE.md y CHANGELOG.md con los cambios realizados.:

## Ficheros y carpetas involucradas
-	Serán buscados en le proyecto todos los ficheros y carpetas que se vean afectados por los cambios, incluyendo pero no limitándose a:
    - src\util_bbdd\data\sql_queries.json
    - src\util_bbdd\managers\async_mgr.py
    - src\util_bbdd\managers\sync_mgr.py
    - src\util_bbdd\doc\* (toda la carpeta de documentación para revisar compatibilidad y actualizar plantillas)
    - README.md
    - docs\ARCHITECTURE.md
    - CHANGELOG.md

## Necesito:
-	Mejorar los resultados de las consultas en base de datos
-   Para todos los motores queremos mostrar:
    - El número de tablas, vistas, rutinas y elementos de almacenamiento que tiene la base de datos.
    - Se crearán consultas específicas u obtner lovalores de las consultas actuales para ello se validara la mejor estrategia, SI ampliar src\util_bbdd\data\sql_queries.json con las nuevas consultas necesarias para obtener esta información de manera eficiente, o obtnerla delos resultados btenido en las demas consultas, analizar si esta información es necesario quye esté cacheada.
    - En la visualización de las tablas, vistas, rutinas y elementos de almacenamiento, se debe mejorar la legibilidad y organización de la información, por ejemplo utilizando tablas con estilos claros, colores o iconos para diferenciar los diferentes tipos de objetos (tablas, vistas, rutinas, elementos de almacenamiento). Además, se debe revisar la compatibilidad de los nuevos campos con la generación de documentación en formato Word, y se deben actualizar las plantillas de Word si es necesario para mostrar los nuevos campos de manera clara y legible.
    - Esta información se mostra al estilo de encabezados o secciones claramente diferenciadas para cada tipo de objeto, por ejemplo, una sección para tablas, otra para vistas, otra para rutinas y otra para elementos de almacenamiento, y dentro de cada sección se mostrarán los objetos correspondientes con su información detallada.

- Para las tablas de base de datos:
    - Motor de almacenamiento de cada tabla si dispone de ello, si no no se informará, se mostrará en los tres formatos (Word, Excel y HTML). Ver si se puede ampliar la actual consulta o se necesitan nuevas consultas para obtener esta información de manera eficiente.
    - Mejorar la visualización del charset y collation de cada tabla si se dispone de ello, si no se muestra "N/A" o similar, actualmente se hace, pero su visualización debe mejorar o bien separado por un guión o bien en filas separadas,  una vez se decida la mejor forma de mostrarlo, se debe aplicar a los tres formatos (Word, Excel y HTML).

- En la salida HTML:
    - Los ficheros físicos deben permitir la exportación a Excel y CSV, por lo que se debe revisar la compatibilidad de los nuevos campos con la exportación a Excel y CSV, y se deben actualizar las plantillas de Excel y CSV si es necesario para mostrar los nuevos campos de manera clara y legible

    - En la visualización de las tablas, vistas, rutinas, se tiene que incluir un botón que permita visualizar el total de la información, todas las tabla (con sus columas), todas las vistas o todas las rutinas en una pagina nueva que se abrirán como pestaña en el propio nevegador, para que el usuario pueda acceder a toda la información de manera fácil y rápida sin tener que navegar por diferentes páginas o secciones del documento permitir la exportación a Excel y CSV de la información detallada de cada tabla, vista o rutina, que permita busqueda y ordenación, por lo que se debe revisar la compatibilidad de los nuevos campos con la exportación a Excel y CSV, y se deben actualizar las plantillas de Excel y CSV si es necesario para mostrar los nuevos campos de manera clara y legible. En excel ya se muestra en la hoja Columnas la información de las tablas con sus columnas, lo mismo para el resto.

-   Para MariaDB:
    - Revisar las consultas que obtienen la información de Ficheros físicos adicionales y Temp tablespaces:
        - Muestra el siguiete mensaje de error: "Error al obtener la información de los ficheros físicos adicionales: (1054, "Unknown column 'FILE_NAME' in 'field list'")", por lo que se debe revisar la consulta para obtener la información de los ficheros físicos adicionales y Temp tablespaces en MariaDB, ya que parece que la columna FILE_NAME no existe en la versión de MariaDB que se está utilizando, por lo que se debe revisar la consulta y adaptarla a la versión de MariaDB que se está utilizando para obtener la información de los ficheros físicos adicionales y Temp tablespaces de manera correcta
        - Muestra el siguiente mensaje de error: Parámetros inválidos: Query 'temp_tablespaces' not found for db_type 'mariadb'
        - Si no se dispone de esta información en MariaDB, se debe mostrar un mensaje claro indicando que no se dispone de esta información para MariaDB, en lugar de mostrar un mensaje de error genérico, y se debe revisar la compatibilidad de este cambio con la generación de documentación en formato Word y Esxcel, y se deben actualizar las plantillas de Word si es necesario para mostrar este mensaje de manera clara y legible

-   Revisar la compatibilidad con la generación de documentación que se encuentra en src\util_bbdd\doc, ya que se deben mostrar los nuevos campos en la documentación generada, tanto en el formato de Word como en el formato HTML, y se deben actualizar las plantillas de Word y HTML si es necesario para mostrar los nuevos campos de manera clara y legible

## Requisitos:
-	Incluir cachés siempre que se pueda, teniendo en cuenta que ya tenemos centralizado en src\util_bbdd\metadata\cache.py el uso de cachés
-	Mantener funcionalidad de poder dividir  en varias imágenes las relaciones
-	Reutilización de código
-	Aplicar responsabilidad única, revisando y proponiendo los cambios necesarios
-	En la ampliación se tiene que revisar la compatibilidad con la generación de documentación que se encuentra en src\util_bbdd\doc
-	Responsabilidad única para todas las modificaciones y ampliaciones, si es necesario refactorizar se documenta
-	Diseño y arquitectura SOLID
-	Legibilidad y Clean Code
-	Posibles bugs o errores ocultos
-	Cumplimiento de PEP8
-	Tests que cubran los cambios
-	Impacto en la rama (qué se supone que hace y si lo cumple)
-	Seguridad, rendimiento, dependencias, migraciones…
-	No quiero fix, quiero soluciones definitivas
-	Se estricto en la aplicación de los cambios
-	Limpiar dependencias no usadas y no mantener compatibilidad hacia atrás
-	Una vez finalizado crearemos la version = "v0.5.6" y se documentará y actualizara
        - En el CHANGELOG.md los cambios realizados
        - En el README.md se actualizará todo como sifuera una versión nueva, incluyendo ejemplos de uso y cambios en la configuración, respetando la configuración / apartados actuales en la medida de lo posible, añadiendo ejemplos de uso de las funcionalidades
        - docs\ARCHITECTURE.md se actualizará con la nueva arquitectura y diseño, incluyendo diagramas si es necesario (actualizar todo el proyecto a la nueva arquitectura y diseño, no solo la parte de análisis)
        - pyproject.toml se actualizará con la nueva versión
-   Si es necesario crear nuevos módulos o carpetas para mantener la responsabilidad única, hazlo sin miedo

## Crear un documento formato markdown
-	Crear prompt con los cambios a realizar
-	Incluir plan de acción PR con las decisiones tomadas
-	Incluir plan de refactorización si es necesario
-	Añade lo que consideres necesario
-   La Carpeta de trabajo es docs/v0.5.6/, aqui dejaremos el documento markdown con toda la información, una vez finalizado se moverá a la carpeta raíz de docs y se actualizará el README.md y ARCHITECTURE.md con la nueva versión v0.5.6

# Añado ejemplo de configuración para impresión
``` toml
[imprimir_config]
    # Formato de salida: "word", "excel" o "html"
    formatos = ["word", "excel", "html"]
    [imprimir_config.imprimir]
        # Ajustes generales
        table_style = "Grid Table 4 Accent 4"
        plantilla_word = "documentar_bbdd.docx"
        plantilla_html = ""
        html_items_por_pagina = 15
        tablas_por_documento = 50

        [imprimir_config.imprimir.tablas]
            imprimir_tablas = true
            ddl = true
            columnas = true
            pk = true
            fk = true
            unicas = true
            indices = true

        [imprimir_config.imprimir.vistas]
            imprimir_vistas = true
            ddl = true
            columnas = true

        [imprimir_config.imprimir.rutinas]
            imprimir_procedures = true
            imprimir_function = true

        [imprimir_config.imprimir.almacenamiento]
            imprimir_almacenamiento = true

        [imprimir_config.imprimir.columnas_charset]
            charset_collation = true

        [imprimir_config.imprimir.info_database]
            imprimir_info_database = true
            version = true
            charset_collation = true

        [imprimir_config.imprimir.grafo]
            enabled = true
            format = "png"
            show_columns = true
            first_level_only = true
            image_width_inches = 10.5
            images_paginated = true
            max_subnodes = 10

        # Nota:
        # - Si un bloque se configura pero no se especifican opciones, se asume que todas las opciones quedan a true.
```
