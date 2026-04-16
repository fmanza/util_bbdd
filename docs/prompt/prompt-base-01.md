Carpetas a revisar
    src\util_bbdd\_core
    src\util_bbdd\core

Contexto
    Identificar el motivo poer el que se dispone de  dos módulos core

Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas

Documentar la sesión actual siguiendo .ai\sessions\INDEX.md

---

/tech-debt

Módulo objetivo: src\util_bbdd\comparar\
Deuda conocida o síntomas: no contemepla todos los motores definidos en src\util_bbdd\connection\params.py, e _BUILD_SUPPORTED_TYPES.
Restricciones de scope: solo análisis (PLAN + AUDIT_CODE), sin IMPLEMENT por ahora.
Política de compatibilidad: se autoriza romper contratos públicos.

Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas

Documentar la sesión actual siguiendo .ai\sessions\INDEX.md

---
# noqa: BLE001

---
Necesito revisar toda la documentación de util_bbdd.

Usa Documentation Reviewer para:
1. Mapear estado actual (README, guías, ejemplos, docstrings)
2. Identificar ejemplos faltantes por módulo principal
3. Encontrar gaps críticos vs mejoras recomendadas
4. Generar backlog de acciones con prioridades

Alcance: Todos los módulos públicos en src/util_bbdd/

---

/runSubagent Documentation Reviewer

Input: Auditoría completa de documentación incluyendo ejemplos faltantes, gaps críticos y backlog de acciones priorizadas.
Output: Reporte detallado con recomendaciones específicas para mejorar la documentación de util_bbdd.

---
Crear la funcionalidad para generar documentación en html, Excel, Word y Markdown (usando mermaid si es necesario) para la salida del módulo src\util_bbdd\comparar.
Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

---
Crear las siguientes mejoras:
1. Refactorizar src\util_bbdd\comparar\reporters\html_reporter.py para permitir el filtrado por los cinco bloques (Tablas añadidas, Tablas eliminadas, Tablas modificadas, Vis con DIF, Rutinas con DIF), proponer la mejor alternativa a Jinja2.
2. Refactorizar src\util_bbdd\comparar\reporters\word_reporter.py, reducir los retornos de carro y compactar lo máximo posible el documento para ahorrar espacio.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

---
Crear las siguientes mejoras:
1. Refactorizar src\util_bbdd\comparar\reporters\html_reporter.py para permitir el filtrado por los cinco bloques (Tablas añadidas, Tablas eliminadas, Tablas modificadas, Vis con DIF, Rutinas con DIF) y poder buscar sus elementos escribiéndolos, volver a usar Jinja2.
2. Refactorizar src\util_bbdd\comparar\reporters\word_reporter.py, para poner le formato de título 1 a: Tablas añadidas, Tablas eliminadas, Tablas modificadas, Vistas con diff, Rutinas con diff.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

---
Crear la funcionalidad para generar la salida necearia SQL de las diferencias encontradas en src\util_bbdd\comparar para el motor de destino y poder nivelar los dos schemas/database.
Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---
---
Refactorizar src\util_bbdd\comparar\reporters\sql_reporter.py para incorporar la creación de tablas y la creación o eliminación de columnas y elementos faltantes de la implementación actual. Para ello añadiremos las funcionalidad necesaria y el acceso a los metadatos de SQLAlchemy. Si es necesario crear nuevas clases que obtenga la información para poder crear o modificar tablas, columnas, vistas o rutinas, se pueden crear dentro de src\util_bbdd\comparar\reporters\sql_reporter.py o en un nuevo módulo dentro de comparar, lo importante es que la funcionalidad quede bien organizada y estructurada.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Leer y usar siempre la base de CLAUDE.md para cualquier decisión de diseño, implementación o refactorización.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md y .ai\sessions\TEMPLATE\TRACEABILITY.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---
---
Se ha detectado que la comparación de Vistas y Rutinas en src\util_bbdd\comparar\reporters necesita ser mejorada, actualmente la comparación es literal, en el caso de MariaDB en la vistas se incluye el DEFINER=DataBase, lo que hace que aunque la vista sea idéntica en ambos esquemas, se detecte como diferente. Tambien sucede con las Rutinas, en algunos motores como MariaDB se incluye el DEFINER=DataBase, lo que hace que aunque la rutina sea idéntica en ambos esquemas, se detecte como diferente. Por lo tanto, es necesario mejorar la lógica de comparación para que sea más inteligente y no detecte diferencias irrelevantes y revisar la lógica para el resto de motores. En el ecaso de diferencia, la salilda de la información "DDL" de la vista o rutina debe ser lo más completa posible para poder crear o modificar la vista o rutina en el motor de destino.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Leer y usar siempre la base de CLAUDE.md para cualquier decisión de diseño, implementación o refactorización.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md y .ai\sessions\TEMPLATE\TRACEABILITY.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---
Refactorizar y crear nueva funcionalidad en la salida html de la documentación en su apartado de Diagrama de diferencias (tablas). Este apartado mostrará tres opciones Añadidas, Modificadas, Elliminadas, y al hacer click en cada una de ellas se mostrarán solo las tablas que correspondan a esa categoría. Además, la nueva visualización mostrará tantos bloques como seán necesarios y estos contendrán nueve tablas cómo máximo cada uno de los bloques. Recuerda que eres un ingeniero en Frontend, por lo que la experiencia de usuario y la usabilidad de la interfaz deben ser una prioridad en esta mejora y la decisión de arquitectura. Actualmente se usa Mermaid y se le quiere dar prioridad a este formato, pero no cierres otras posibilidaders, se pueden usar librerías de visualización como D3.js o similares para mejorar la presentación de los datos.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md y .ai\sessions\TEMPLATE\TRACEABILITY.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---
Añadir un nuevo reporter SqlDiffReporter que genere un script .sql de nivelación (bring-target-to-source) a partir de un SchemaDiff, e integrarlo en la facade SchemaDiffReporter como nuevo formato "sql".
---
---
Refactorizar src\util_bbdd\comparar para quitar la exceciones genéricas y crear excepciones específicas para cada tipo de error que pueda ocurrir durante la comparación, como por ejemplo: ComparacionException, ConexionException, ValidacionException, etc. Esto permitirá tener un mejor control sobre los errores y poder manejarlos de manera más específica en la generación de la documentación y en la salida de los reportes.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md y .ai\sessions\TEMPLATE\TRACEABILITY.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---
Revisar el código de src\util_bbdd\comparar para identificar todas las excepciones genéricas que se están lanzando (ValueError, Exception, NotImplementedError) y reemplazarlas por excepciones específicas que se ajusten al tipo de error que se está produciendo. Para ello, se crearán nuevas clases de excepciones específicas en la jerarquía de excepciones de _core/exceptions.py, como ComparerError, SchemaDiffValidationError, MetadataIntrospectionError, DiffReportGenerationError, etc. Además, se actualizarán los tests correspondientes para que esperen las nuevas excepciones específicas en lugar de las genéricas.
Los errores de type-check que son pre-existentes (no relacionados a mi refactor) deben actualizarse.

Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md y .ai\sessions\TEMPLATE\TRACEABILITY.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.
Actualizar CHANGELOG.md con un resumen claro de los cambios realizados, incluyendo la creación de nuevas excepciones específicas y la actualización de los tests correspondientes.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
---


Quiero documentar el uso de util_bbdd, mostrando ejemplos prácticos y casos de uso reales.

https://github.com/squidfunk/mkdocs-material
https://squidfunk.github.io/mkdocs-material
