# Aplicar metodología para refactor:

## Objetivo
-	Permitir sacar relaciones de n niveles (nodos), ahora solo se permite generar del primer nivel
-	Mejorar la visualización de la cardinalidad de la línea y flecha que indica el sentido de la cardinalidad, esta debe tener su cardinalidad en la unión de los nodos, si la cardinalidad es de 1 a n, según el sentido los puntos que unen lo nodos se tienen que representar la cardinalidad el 1 en un nodo y n en el otro nodo.
-	Permitir parametrizar el número máximo de niveles a mostrar, para evitar generar gráficos con demasiados nodos y relaciones que no se puedan visualizar correctamente, esto es importante para bases de datos con muchas tablas y relaciones, por lo tanto se necesita:
    -	Parametrizar el número máximo de niveles a mostrar en el gráfico, mínimo 1
    -	Mostrar el número total de niveles, se indicará en la parte inferior del gráfico que existen más niveles que no se están mostrando, diferenciando los niveles de entrada y de salida.
- En el formato HTML:
    - Disponer de pestañas para cada nivel, de esta forma se pueden mostrar todos los niveles sin necesidad de generar gráficos con demasiados nodos y relaciones que no se puedan visualizar correctamente, esto es importante para bases de datos con muchas tablas y relaciones, por lo tanto se necesita:
        - Crear pestañas para cada nivel, diferenciando los niveles de entrada y de salida.
        - Mostrar el número total de niveles, se indicará en la parte inferior del gráfico que existen más niveles que no se están mostrando, diferenciando los niveles de entrada y de salida.
- En el formato WORD:
    - Se representarán como hasta ahora, pero se indicará el número total de niveles, se indicará en la parte inferior del gráfico que existen más niveles que no se están mostrando, diferenciando los niveles de entrada y de salida.

-	Parametrizar la información que se visualiza cuando se permite visualizar las columnas:
    - Parametrizar la visualización del tipo de dato, se muestra o no.
    - Crear las opciones de:
        - *Compacto*: mediante parametrización se indica el número máximo de columnas a mostrar, mínimo siempre 1
        - *Relaciones*: Mostrar solo las columnas involucradas en las relaciones
        - *Todas*: muestra todas las columnas
    - Añadir apartado de puntos suspensivos si existen más columnas que puedan representarse.
- Mejorar la visualización indicando con un símbolo de llave las columnas que están relación, la clave principal en un color más llamativo que el resto.
- Optimizar su estructura y ejecución

## Scope
- Archivos afectados:
    -	src\util_bbdd\analysis\base.py
    -	src\util_bbdd\analysis\graphviz_ext.py
    -	src\util_bbdd\doc
- Breaking Change: Sí/No
- Retrocompatibilidad esperada: Ninguna, se eliminará la compatibilidad hacia atrás para forzar la adopción de la nueva funcionalidad y evitar mantener código obsoleto que complique el mantenimiento futuro.

## Justificación
Ampliarar funcionalidad y mejorar la visualización de las relaciones entre tablas en los gráficos generados, permitiendo mostrar relaciones de n niveles, parametrizar la información visualizada y optimizar la estructura y ejecución del código, lo que resultará en una herramienta más potente, flexible y fácil de mantener.

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
-	Una vez finalizado crearemos la version = "v0.6.0" y se documentará y actualizara
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
-   La Carpeta de trabajo es .ai\sessions\<fecha>, aqui dejaremos el documento markdown con toda la información, una vez finalizado se actualizarán los archivos de .ai/sessions/<fecha>/ y se actualizará el README.md, .ai\architecture.md, .ai\glossary.md, .ai\product.md, .ai\runtime.md, y .ai\standards.md con la nueva versión v0.6.0 y si consideras alguno más indicalo.

# Añado ejemplo de configuración/parametrización para impresión actual es:
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
