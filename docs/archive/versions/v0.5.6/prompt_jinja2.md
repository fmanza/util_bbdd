# Pompt: Refactorización Profesional de Jinja2 Standalone
Actúa como un Arquitecto de Software Senior especializado en Python.

**Tu misión**: Refactorizar el siguiente desarrollo basado en Jinja2 (Standalone) aplicando principios de ingeniería de software de alto nivel.

**Requisitos de la Refactorización**:

1. **Arquitectura de Carpetas**: Organiza el proyecto de forma lógica:

   - `src/`: Lógica de Python (Cargadores de datos, lógica de negocio). Analiza  para este caso la mejor estrategia para organizar el código, si es necesario crear nuevos módulos o carpetas para mantener la responsabilidad única, hazlo sin miedo.
   - `templates/`: Plantillas Jinja2.
     - `layouts/`: Plantillas base para herencia.
     - `macros/`: Componentes reutilizables (botones, tablas).
        - `pages/`: Plantillas específicas para cada página o sección.
   - `tests/`: Pruebas unitarias.

2. **Principio de Responsabilidad Única (SOLID)**: Separa la configuración del Environment de Jinja2 de la lógica de obtención de datos y del proceso de renderizado. Crea una clase TemplateEngine o similar.

3. **Herencia y DRY (Don't Repeat Yourself)**: Implementa una plantilla base con bloques para title, styles, content y scripts.

Usa Macros para elementos repetitivos (botones, tarjetas, tablas).

4. **Filtros Personalizados**: Identifica lógica compleja dentro de la plantilla y muévela a filtros personalizados de Python para mantener el HTML limpio.

5. **Pruebas Unitarias**: Genera pruebas con pytest que verifiquen:

   - Que el motor carga las plantillas correctamente.
   - Que el HTML generado contiene los datos esperados (uso de assert).

Que el HTML generado contiene los datos esperados (uso de assert).

6. **Tipado y Documentación**: Usa Type Hints en Python y Docstrings.

**Código Original a Refactorizar:**
- src\util_bbdd\doc\data

7. **Limpieza de Código**: Elimina código muerto, comentarios innecesarios y asegúrate de que el código sigue PEP8.

8. **Mantener compatibilidad**: Asegúrate de que la refactorización no rompe la funcionalidad existente. No quiero compatiblidad hacia atras.

**Entrega**: Un proyecto refactorizado con la nueva estructura, código limpio, pruebas unitarias y documentación clara. Además, un archivo markdown detallando el proceso de refactorización, decisiones tomadas y cómo ejecutar las pruebas.
