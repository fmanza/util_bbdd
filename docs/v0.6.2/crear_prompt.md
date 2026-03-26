# Aplicar metodología para new_feature:

## Objetivo
- La creación de la imagen por defecto, actualmente es muy grande y debería ser más pequeña. En la creación de la representación de las tablas debería estar al 75% del que actualmente se usa, manteniendo un tamaño fijo por representación para todas las tablas:
    - Establecer un tamaño fijo para cada tabla, con un número máximo de columnas a mostrar, añadiendo puntos suspensivos si existen más columnas que puedan representarse.

- Mejorar la representación de la cardinalidad, actualmente los valores 1-N-M no se visualizan correctamente, añadir mejora para que estas se vean un poco más a la izquierda de las flechas actuales, de esta forma se mejora la visualización de las cardinalidades y se evita que se superpongan con las flechas, lo que dificulta la lectura del diagrama.

- Algunas etiquetas (texto de la dependencia de la cardinalidad) se superponen con las flechas, lo que dificulta la lectura del diagrama. Para mejorar esto, se propone separar la indicación de las cardinalidades de las flechas, colocándolas en una posición fija cerca de la tabla relacionada, para que sean fácilmente legibles independientemente de la orientación de las flechas. Razonar y proponer alternativas de diseño para esta mejora, teniendo en cuenta la claridad visual y la facilidad de comprensión del diagrama.

- Por cada nivel de entrada o salida se da la casuistica que la reprentación en muy numerosa y se hace difícil de leer, para esto se propone mantener la funcionalidad de poder dividir en varias imágenes las relaciones (como actualmente se hace en Word), creando pestañas por nivel o proponer mejor alternativa. Añadiendo una mejora que permita mostrar relaciones de n niveles, parametrizando la información visualizada, de esta forma se puede mostrar más información sin perder claridad visual.

- Panning y zoom controlado por la propia página, para esto se necesita:
    - Implementar una funcionalidad de panning y zoom dentro de la página HTML que permita a los usuarios navegar por el diagrama de relaciones de manera más intuitiva, especialmente cuando se trata de diagramas complejos con muchas tablas relacionadas. Esta funcionalidad debe ser fácil de usar y no debe interferir con la legibilidad del diagrama.
    - Se puede utiliza svg-pan-zoom o alguna librería similar para implementar esta funcionalidad de manera eficiente y con buena experiencia de usuario.

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
-	Una vez finalizado crearemos la version = "v0.6.2" y se documentará y actualizara
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
-   La Carpeta de trabajo es .ai\sessions\<fecha>, aqui dejaremos el documento markdown con toda la información, una vez finalizado se actualizarán los archivos de .ai/sessions/<fecha>/ y se actualizará el README.md, .ai\architecture.md, .ai\glossary.md, .ai\product.md, .ai\runtime.md, y .ai\standards.md con la nueva versión v0.6.2 y si consideras alguno más indicalo.
-	Una vez finalizado el documento markdown, se creará un PR con los cambios realizados, incluyendo una descripción detallada de los cambios, las decisiones tomadas y cualquier consideración importante para la revisión del código. El PR se etiquetará adecuadamente para facilitar su revisión y seguimiento.
