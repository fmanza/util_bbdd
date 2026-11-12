# Prompt: zensical_nav_update — Actualizar zensical.toml con nuevas páginas

<!--
  Prompt especializado para actualizar navegación de zensical.toml tras generar nuevas páginas.
  Uso: Documentation Generator debe ejecutar este prompt después de crear cualquier página nueva.
  Última revisión: 2026-10-06
-->

Actualiza la navegación de `zensical.toml` para publicar nuevas páginas de documentación y asegurar
que sean accesibles vía el navegador del sitio (evitar páginas "huérfanas").

---

## Especialización de dominio

- **Proyecto**: util_bbdd — librería Python multimotor de bases de datos
- **Archivo objetivo**: `zensical.toml` en la raíz del proyecto
- **Secciones de navegación**: Funcional, Técnica, Guías, Ejemplos, Config IA, Arquitectura
- **Formato TOML**: `nav` de `[project]` (lista de tablas en línea `{ "Título" = "ruta.md" }`), orden
  alfabético dentro de subsecciones

---

## Instrucción al modelo

```
Eres un especialista en estructura de sitios de documentación y TOML (Zensical).

Lee:
1. El listado de nuevas páginas (rutas relativas desde `docs/`)
2. La estructura actual de `zensical.toml` (seción `nav`)
3. Las categorías existentes en el proyecto

Tarea: Proponer o aplicar cambios a `zensical.toml` siguiendo estas reglas:

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

### Reglas de formato TOML

1. **Indentación**: 2 espacios por nivel de anidamiento (no tabs); coma final en cada elemento
2. **Referencias a archivos**: `{ "Título" = "ruta/relativa/archivo.md" },` (desde `docs/` hacia abajo);
   un grupo es `{ "Grupo" = [ ... ] },`
3. **Nombres de secciones**: Español, PascalCase si es título compuesto
4. **Ordenamiento**: Alfabético dentro de cada subsección (excepto grupos lógicos)
5. **Sin duplicados**: Verificar que no aparece la misma ruta en dos lugares

### Ejemplo de nueva página (guía de Drivers)

Entrada:
- Archivo: `docs/guides/drivers.md`
- Tipo: Guía operacional
- Descripción: "Guía de drivers por motor de BD"

Ubicación en `zensical.toml`:
```toml
{ "Guías" = [
  { "Drivers por Motor" = "guides/drivers.md" },
] },
```
(Bajo la subsección "Conexión y Drivers" si existe, o como ítems independientes)

### Checklist de salida

Antes de finalizar, verifica:
- ✅ Todas las nuevas páginas están en `zensical.toml`
- ✅ No hay duplicados (misma ruta en dos lugares)
- ✅ TOML válido (`python -c "import tomllib; tomllib.load(open('zensical.toml','rb'))"`)
- ✅ Referencias a archivos son rutas relativas desde `docs/`
- ✅ Nombres de secciones son descriptivos y en español
- ✅ Ordenamiento alfabético dentro de subsecciones
- ✅ Enlaces rotos verificados (archivo existe en disco)
```

---

## Entrada esperada

```
Archivo: zensical.toml
Nuevas páginas a publicar (rutas desde docs/):
  - [lista de rutas separadas por línea]

Contexto adicional (opcional):
  - Versión objetivo: [p.ej. v0.32.1]
  - Motivo: [p.ej. "Publicar huérfanas tras auditoría"]
```

---

## Salida esperada

**Modificación a `zensical.toml`**: TOML válido con nuevas entradas bajo las secciones apropiadas.

**Reporte de cambios**:
- Listado de nuevas referencias añadidas
- Ubicación en navegación (sección → subsección)
- Validación de sintaxis TOML y `zensical build --strict`
- Confirmación de que archivos existen en disco

---

## Casos de uso típicos

### Caso 1: Publicar páginas huérfanas tras auditoría

**Entrada**:
```
Nuevas páginas (huérfanas post-auditoría v0.32.1):
  - adr/ADR-004-lazy-oracle-version-resolution.md
  - guides/drivers.md
  - guides/code_reusability_analysis_guide.md
  - guides/performance_audit_guide.md
  - guides/performance_audit_constraints_guide.md
```

**Salida esperada**:
```toml
# En Arquitectura → Decisiones Arquitectónicas (ADRs):
{ "ADR-004 (Lazy Oracle Version)" = "adr/ADR-004-lazy-oracle-version-resolution.md" },

# En Guías → Rendimiento:
{ "Performance Audit (General)" = "guides/performance_audit_guide.md" },
{ "Performance Audit (Constraints)" = "guides/performance_audit_constraints_guide.md" },

# En Guías:
{ "Drivers por Motor" = "guides/drivers.md" },
{ "Reutilización de Código" = "guides/code_reusability_analysis_guide.md" },
```

### Caso 2: Generar nueva documentación funcional

**Entrada**:
```
Nueva página funcional:
  - docs/functional/connection_pooling.md (gestión de pool de conexiones)
```

**Salida esperada**:
```toml
# En Documentación Funcional → Managers:
{ "Connection Pooling" = "functional/connection_pooling.md" },
```

---

## Integración con Documentation Generator

El agente `documentation-generator.agent.md` debe invocar este prompt **DESPUÉS**
de generar cualquier página nueva, pasando:
1. El archivo `zensical.toml` existente (lectura)
2. Lista de nuevas rutas generadas
3. Contexto: tipo de documento (funcional/técnica/ejemplo/guía) y módulo relacionado

**Flujo esperado**:
```
[Documentation Generator inicia]
  → Genera página (p.ej. docs/functional/nueva_feature.md)
  → [Invoca este prompt]
  → Actualiza zensical.toml con nueva entrada
  → Valida el TOML y los enlaces (zensical build --strict)
  → Confirma cambios al usuario
```

---

*Prompt creado: 2026-10-06*
*Integración: documentation-generator.agent.md*
