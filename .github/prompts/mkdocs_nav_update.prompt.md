# Prompt: mkdocs_nav_update — Actualizar mkdocs.yml con nuevas páginas

<!--
  Prompt especializado para actualizar navegación de mkdocs.yml tras generar nuevas páginas.
  Uso: Documentation Generator debe ejecutar este prompt después de crear cualquier página nueva.
  Última revisión: 2026-10-06
-->

Actualiza la navegación de `mkdocs.yml` para publicar nuevas páginas de documentación y asegurar
que sean accesibles vía el navegador del sitio (evitar páginas "huérfanas").

---

## Especialización de dominio

- **Proyecto**: util_bbdd — librería Python multimotor de bases de datos
- **Archivo objetivo**: `mkdocs.yml` en la raíz del proyecto
- **Secciones de navegación**: Funcional, Técnica, Guías, Ejemplos, Config IA, Arquitectura
- **Formato YAML**: Indentación exacta (2 espacios), orden alfabético dentro de subsecciones

---

## Instrucción al modelo

```
Eres un especialista en estructura de sitios de documentación y YAML.

Lee:
1. El listado de nuevas páginas (rutas relativas desde `docs/`)
2. La estructura actual de `mkdocs.yml` (seción `nav`)
3. Las categorías existentes en el proyecto

Tarea: Proponer o aplicar cambios a `mkdocs.yml` siguiendo estas reglas:

### Reglas de clasificación

**Documentación Funcional** (`docs/functional/`)
  → Sección: "Documentación Funcional" (Product Owner, QA)
  → Agrupar por feature/módulo (Managers, Bulk, Migraciones, etc.)

**Documentación Técnica** (`docs/api/`)
  → Sección: "Referencia Técnica" (Desarrolladores)
  → Agrupar por componente (Managers, Bulk, Queries, Dump, etc.)

**Ejemplos** (`docs/examples/`)
  → Sección: "Ejemplos" (Usuarios finales)
  → Agrupar por feature/workflow

**Guías y Operación** (`docs/guides/`)
  → Sección: "Guías" (Cross-cutting)
  → Subsecciones: Onboarding, Conexión, Errores, Comparación, Volcado, Migraciones, Rendimiento, Herramientas IA

**Decisiones Arquitectónicas** (`docs/adr/`)
  → Sección: "Arquitectura → Decisiones Arquitectónicas (ADRs)"
  → Listar en orden ADR-001, ADR-002, ADR-003, ADR-004, ..., Plantilla ADR

**Auditorías y Planes** (`docs/` raíz)
  → Sección: "Guías → Auditoría" (si es constraints) o "Guías → Rendimiento" (si es performance)
  → O integrar en "Historia y Planes" si es un roadmap/plan de versión

### Reglas de formato YAML

1. **Indentación**: 2 espacios exactos (no tabs)
2. **Referencias a archivos**: `- Título: ruta/relativa/archivo.md` (desde `docs/` hacia abajo)
3. **Nombres de secciones**: Español, PascalCase si es título compuesto
4. **Ordenamiento**: Alfabético dentro de cada subsección (excepto grupos lógicos)
5. **Sin duplicados**: Verificar que no aparece la misma ruta en dos lugares

### Ejemplo de nueva página (guía de Drivers)

Entrada:
- Archivo: `docs/guides/drivers.md`
- Tipo: Guía operacional
- Descripción: "Guía de drivers por motor de BD"

Ubicación en `mkdocs.yml`:
```yaml
- Guías:
    - Drivers por Motor: guides/drivers.md
```
(Bajo la subsección "Conexión y Drivers" si existe, o como ítems independientes)

### Checklist de salida

Antes de finalizar, verifica:
- ✅ Todas las nuevas páginas están en `mkdocs.yml`
- ✅ No hay duplicados (misma ruta en dos lugares)
- ✅ Indentación YAML correcta (2 espacios)
- ✅ Referencias a archivos son rutas relativas desde `docs/`
- ✅ Nombres de secciones son descriptivos y en español
- ✅ Ordenamiento alfabético dentro de subsecciones
- ✅ Enlaces rotos verificados (archivo existe en disco)
```

---

## Entrada esperada

```
Archivo: mkdocs.yml
Nuevas páginas a publicar (rutas desde docs/):
  - [lista de rutas separadas por línea]

Contexto adicional (opcional):
  - Versión objetivo: [p.ej. v0.32.1]
  - Motivo: [p.ej. "Publicar huérfanas tras auditoría"]
```

---

## Salida esperada

**Modificación a `mkdocs.yml`**: YAML válido con nuevas entradas bajo las secciones apropiadas.

**Reporte de cambios**:
- Listado de nuevas referencias añadidas
- Ubicación en navegación (sección → subsección)
- Validación de sintaxis YAML
- Confirmación de que archivos existen en disco

---

## Casos de uso típicos

### Caso 1: Publicar páginas huérfanas tras auditoría

**Entrada**:
```
Nuevas páginas (huérfanas post-auditoría v0.32.1):
  - adr/ADR-004-lazy-oracle-version-resolution.md
  - constraints_audit_index.md
  - constraints_quick_reference.md
  - constraints_reading_guide.md
  - guides/drivers.md
  - guides/code_reusability_analysis_guide.md
  - performance_audit_guide.md
  - performance_audit_constraints_guide.md
```

**Salida esperada**:
```yaml
# En Arquitectura → Decisiones Arquitectónicas (ADRs):
- ADR-004 (Lazy Oracle Version): adr/ADR-004-lazy-oracle-version-resolution.md

# En Guías → Auditoría:
- Auditoría de Constraints (Quick Ref): constraints_quick_reference.md
- Auditoría de Constraints (Index): constraints_audit_index.md
- Auditoría de Constraints (Lectura): constraints_reading_guide.md

# En Guías → Rendimiento:
- Performance Audit (General): performance_audit_guide.md
- Performance Audit (Constraints): performance_audit_constraints_guide.md

# En Guías:
- Drivers por Motor: guides/drivers.md
- Reutilización de Código: guides/code_reusability_analysis_guide.md
```

### Caso 2: Generar nueva documentación funcional

**Entrada**:
```
Nueva página funcional:
  - docs/functional/connection_pooling.md (gestión de pool de conexiones)
```

**Salida esperada**:
```yaml
# En Documentación Funcional → Managers:
- Connection Pooling: functional/connection_pooling.md
```

---

## Integración con Documentation Generator

El agente `documentation-generator.agent.md` debe invocar este prompt **DESPUÉS**
de generar cualquier página nueva, pasando:
1. El archivo `mkdocs.yml` existente (lectura)
2. Lista de nuevas rutas generadas
3. Contexto: tipo de documento (funcional/técnica/ejemplo/guía) y módulo relacionado

**Flujo esperado**:
```
[Documentation Generator inicia]
  → Genera página (p.ej. docs/functional/nueva_feature.md)
  → [Invoca este prompt]
  → Actualiza mkdocs.yml con nueva entrada
  → Valida YAML y enlaces
  → Confirma cambios al usuario
```

---

*Prompt creado: 2026-10-06*
*Integración: documentation-generator.agent.md*
