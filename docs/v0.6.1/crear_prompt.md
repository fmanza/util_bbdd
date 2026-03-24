# Aplicar metodología para new_feature:

## Objetivo
- Mejorar la representación de las tablas, para ello se analizará el código de un repositorio en GitHub de una aplicación parecida a la actual pero reliaza en java, usando graphviz para generar los gráficos, se analizará su código y se aplicarán las mejoras necesarias para implementar la nueva funcionalidad:
    - Repositorio a analizar:[schemaspy](https://github.com/schemaspy/schemaspy)
    - Pagina WEB con un ejemplo: [sample](https://schemaspy.org/samples/chinook/tables/Track.html)
    - Imagen otenida del ejemplo: ![image](https://schemaspy.org/samples/chinook/diagrams/Track.1degree.png)

- Mantendremos un código de color pastel para identificar las tablas, por ejemplo:
    - Tablas de tipo entidad: color azul
    - Tablas de tipo relación o asociación: color verde
    - Tablas de tipo jerarquía o especialización: color naranja
    - Tablas de tipo vista: color gris (revisar si es necesario su representación o si se puede omitir para simplificar la visualización, ya que en algunos casos las vistas pueden generar una gran cantidad de relaciones que dificultan la comprensión del diagrama).

- Mantendremos un código de color pastel para identificar los diferentes tipos de relaciones, por ejemplo:
    - Relaciones de clave foránea: color rojo
    - Relaciones de herencia o especialización: color azul
    - Relaciones de asociación o composición: color verde
    - Crearemso un leyenda para identificar cada tipo de relación, esto ayudará a los usuarios a entender rápidamente la naturaleza de las relaciones entre las tablas.

- Las flechas actuales cuando son totalmente verticales el número de la cardinalidad no se ve correctamente, separar la indicación de las cardinlidades de las flechas, para esto se necesita:
    - Separar la indicación de las cardinalidades de las flechas, colocándolas en una posición fija cerca de la tabla relacionada, para que sean fácilmente legibles independientemente de la orientación de las flechas.

- En el formato HTML:
    - La representación de los diagramas de relaciones, deben permitir:
        - La ampliación visual y movimiento dentro de su contenido, ya que existe casos en los que que se tiene muchas tablas relacionadas y estas no se ven correctamente.
    - La representación de las tablas debería tener un tamaño fijo, para esto se necesita:
        - Establecer un tamaño fijo para cada tabla, con un número máximo de columnas a mostrar, añadiendo puntos suspensivos si existen más columnas que puedan representarse.

- Ver si se puede optimizar la creación de imágenes ya que su tiempo de ejecución es grande.
- Explicación de que significa Salida oculta.

## Scope
- Archivos afectados:
    -	src\util_bbdd\analysis\base.py
    -	src\util_bbdd\analysis\graphviz_ext.py
    -	src\util_bbdd\doc
- Breaking Change: Sí, se introducirán cambios significativos en la forma en que se generan y visualizan los gráficos de relaciones entre tablas, lo que puede afectar a los usuarios que dependan de la funcionalidad actual. Se documentarán claramente los cambios y se proporcionarán guías de migración para facilitar la transición a la nueva versión.
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
-	Una vez finalizado crearemos la version = "v0.6.1" y se documentará y actualizara
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
-   La Carpeta de trabajo es .ai\sessions\<fecha>, aqui dejaremos el documento markdown con toda la información, una vez finalizado se actualizarán los archivos de .ai/sessions/<fecha>/ y se actualizará el README.md, .ai\architecture.md, .ai\glossary.md, .ai\product.md, .ai\runtime.md, y .ai\standards.md con la nueva versión v0.6.1 y si consideras alguno más indicalo.
-	Una vez finalizado el documento markdown, se creará un PR con los cambios realizados, incluyendo una descripción detallada de los cambios, las decisiones tomadas y cualquier consideración importante para la revisión del código. El PR se etiquetará adecuadamente para facilitar su revisión y seguimiento.
