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
Crear la funcionalidad para generar la salida de SQL de las diferencias encontradas en src\util_bbdd\comparar para el motor de destino.
Alcance: Solo la generación de documentación, sin cambios en la lógica del módulo comparar.
Política de compatibilidad: Se autoriza romper contratos públicos.
Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas
Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
Revisar lo implementado en src\util_bbdd\comparar para asegurar que la documentación generada refleje fielmente la funcionalidad actual del módulo.
Revisar lo implementado en src\util_bbdd\doc como base de trabajo, se permite mejorar o modificar la estructura de generación de documentación si es necesario para cumplir con los objetivos de este task.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
