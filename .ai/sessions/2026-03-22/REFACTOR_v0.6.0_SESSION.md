# Sesión de Refactorización v0.6.0
**Fecha**: 22 de marzo de 2026
**Rama**: develop → main (v0.6.0)
**Tipo**: Refactorización + Feature (Breaking Change)

---

## 📋 RESUMEN EJECUTIVO

Refactorización completa del subsistema de generación de gráficos de relaciones entre tablas.
- **Objetivo principal**: Soportar relaciones de n niveles con visualización parametrizable
- **Breaking Change**: SÍ (eliminamos compatibilidad hacia atrás)
- **Alcance**: `src/util_bbdd/analysis/` + `src/util_bbdd/doc` + configuración

---

## 🎯 OBJETIVOS FUNCIONALES

### O1: Soporte Multi-nivel (N-ary Relations)
- Actual: solo primer nivel de relaciones
- Nuevo: profundidad configurable (min: 1)
- Indicador visual de niveles no mostrados (entrada/salida)

### O2: Visualización Mejorada de Cardinalidad
- Cardinalidad explícita en puntos de unión (1 en un nodo, n en otro)
- Diferenciación visual entre sentidos de relación
- Símbolos de llave para FK, color destacado para PK

### O3: Parametrización de Información por Columnas
```
Modo Compacto  → máximo N columnas configurable (min: 1)
Modo Relaciones → solo columnas involucradas en FK
Modo Todas     → todas las columnas + indicador "..."
```

### O4: Formatos Específicos
| Formato | Cambios |
|---------|---------|
| Graphviz | Símbolos mejorados, cardinalidad visible |
| HTML | Pestañas por nivel (entrada/salida diferenciadas) |
| Word | Indicadores de niveles no mostrados |

---

## 📁 SCOPE TÉCNICO

### Archivos Afectados
```
src/util_bbdd/
  ├── analysis/
  │   ├── base.py                 (refactor: base para gráficos)
  │   ├── graphviz_ext.py         (refactor: generación gráficos)
  │   ├── graphviz_relationship_graph.py (nuevo módulo)
  │   └── relationship_graph_base.py     (nuevo módulo base)
  ├── doc/
  │   └── (revisar compatibilidad)
  ├── metadata/
  │   └── cache.py               (reutilizar cache centralizado)
  └── __init__.py                (resolver exports públicos)

docs/
  ├── ARCHITECTURE.md            (actualizar diagrama completo)
  ├── v0.6.0/                    (documentación v0.6.0)

pyproject.toml                    (version = "0.6.0")
CHANGELOG.md                      (cambios v0.6.0)
README.md                         (ejemplos nuevos)
.ai/
  ├── architecture.md            (actualizar)
  ├── standards.md               (actualizar)
  └── sessions/2026-03-22/       (esta sesión)
```

---

## 🔍 PLAN DE ACCIÓN (PR)

### 🔴 Fase 1: Auditoría y Diseño (PLAN + AUDIT_PLAN)
**Salidas**:
- `01-AUDIT.md` - Problemas actuales
- `02-DESIGN.md` - Arquitectura SOLID

**Actividades**:
1. Analizar código actual en `analysis/base.py` y `graphviz_ext.py`
2. Mapear dependencias y caches existentes
3. Identificar puntos de acoplamiento
4. Diseñar interfaces de extensión (protocolo de gráficos)

---

### 🟡 Fase 2: Refactorización de Base (IMPLEMENT)
**Salidas**:
- Módulos base desacoplados
- Interfaz `RelationshipGraphProtocol`
- Cache integrado

**Cambios clave**:
1. Extraer `RelationshipGraphBase` - responsabilidad única para lógica multi-nivel
2. Refactorizar `GraphvizRelationshipGraph` - heredar de base
3. Integrar cache centralizado (no reinventar)
4. Remover código obsoleto de compatibilidad hacia atrás

---

### 🟠 Fase 3: Nuevas Funcionalidades (IMPLEMENT)
**Salidas**:
- Soporte n-niveles implementado
- Parametrización de profundidad
- Nuevos modos de visualización de columnas

**Cambios clave**:
1. Método `build_n_level_graph(start_table, max_depth, direction)`
2. Clase `ColumnVisualizationMode` (Enum: COMPACT, RELATIONS, ALL)
3. Clase `CardinalityMarker` - visual indicators
4. HTML generator with tab system

---

### 🟢 Fase 4: Testing y Documentación (AUDIT_CODE + TESTING)
**Salidas**:
- Test coverage ≥ 85% (analysis module)
- Ejemplos en README
- ARCHITECTURE.md actualizado

**Tests**:
```
tests/analysis/
  ├── test_relationship_graph_base.py
  ├── test_n_level_traversal.py
  ├── test_cardinality_visualization.py
  ├── test_column_modes.py
  └── test_format_consistency.py
```

**Auditoría**:
- Security: No SQL injection, validaciones de entrada
- Performance: Benchmarks para n-niveles
- Memoria: Pruebas con GBs de metadata
- Tipado: Type hints completos (100%)

---

### 🔵 Fase 5: Release (VERSION)
**Salidas**:
- CHANGELOG.md actualizado
- README.md con ejemplos v0.6.0
- pyproject.toml versión actualizada
- Etiqueta git: v0.6.0

---

## 💡 DECISIONES ARQUITECTÓNICAS

### D1: Protocolo sobre Herencia Múltiple
**Decisión**: Usar `typing.Protocol` para gráficos
**Justificación**: Composición flexible, evita jerarquías profundas
**Implicación**: Fácil añadir nuevos formatos (SVG, JSON, etc.)

### D2: Cache Centralizado
**Decisión**: Reutilizar `src/util_bbdd/metadata/cache.py`
**Justificación**: Una fuente de verdad, invalidación coordinada
**Implicación**: Menos código, menos bugs, mejor mantenibilidad

### D3: Enum para Modos de Visualización
**Decisión**: `ColumnVisualizationMode` (Enum + dataclass de config)
**Justificación**: Type-safe, extensible, evita magic strings
**Implicación**: Errores en tiempo de desarrollo, no en producción

### D4: Sin Compatibilidad Hacia Atrás
**Decisión**: Breaking change explícito en v0.6.0
**Justificación**: Usuarios adoptan nueva API limpia, sin deuda técnica
**Implicación**: Documentación de migración (docs/MIGRATION_GUIDE.md)

---

## 🛠️ PLAN DE REFACTORIZACIÓN

### R1: Extractar Lógica Multi-nivel
```python
# ANTES: Todo en GraphvizRelationshipGraph
# DESPUÉS:
class RelationshipGraphBase:
    def traverse_n_levels(self, start: Table, max_depth: int) → GraphData
    def calculate_cardinality_positions(self, rels) → CardinalityMarkers

class GraphvizRelationshipGraph(RelationshipGraphBase):
    def _render_node(self, table: Table) → str
    def _render_edge(self, rel: Relationship) → str
```

### R2: Eliminar Duplicación en Formatos
- HTML, Word, Graphviz comparten lógica de construcción
- Extraer a `GraphDataBuilder` agnostico a formato
- Cada formato responsable solo de rendering

### R3: Inyección de Dependencias
```python
class GraphRenderer:
    def __init__(self,
                 metadata_provider: MetadataProvider,
                 cache: GraphCache,
                 config: GraphConfig):
        pass
```

### R4: Limpieza de Dependencias
- Revisar imports no usados
- Eliminar archivos legacy de v0.5.x
- Consolidar excepciones en `exceptions.py`

---

## ⚠️ RIESGOS Y MITIGACIÓN

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|--------|-----------|
| Rendimiento en n-niveles | MEDIA | ALTO | Pruebas con 5+ niveles, cache agresivo |
| Cambios API rompen usuarios | ALTA | CRÍTICO | MIGRATION_GUIDE.md + ejemplos |
| Regression en formatos | MEDIA | MEDIO | Tests de regresión 1:1 con v0.5.x |
| Memoria con tablas grandes | BAJA | ALTO | Limitador de memoria + warning |

---

## 📝 NUEVA CONFIGURACIÓN (pyproject.toml)

```toml
[tool.util_bbdd.graph]
max_depth = 3
visualization_mode = "relations"  # compact | relations | all
show_data_types = false
cardinality_style = "crow_foot"  # crow_foot | line | uml

[tool.util_bbdd.graph.formats]
structure = ["graphviz", "html"]
include_cardinality_markers = true
include_column_symbols = true

[tool.util_bbdd.graph.html]
tabs_per_level = true
items_per_page = 15
theme = "light"

[tool.util_bbdd.graph.cache]
enabled = true
ttl_seconds = 3600
backend = "memory"  # memory | file | redis
```

---

## 📚 DOCUMENTOS A ACTUALIZAR POST-REFACTOR

1. **CHANGELOG.md** - Entrada v0.6.0 con cambios breaking
2. **README.md** - Ejemplos nuevos de uso, configuración
3. **docs/ARCHITECTURE.md** - Diagrama UML del nuevo subsistema
4. **docs/MIGRATION_GUIDE.md** - De v0.5.x → v0.6.0 (CREAR)
5. **.ai/architecture.md** - Impacto en arquitectura general
6. **.ai/standards.md** - Nuevos estándares de testing
7. **.ai/glossary.md** - Términos nuevos (n-level, crow-foot, etc.)

---

## ✅ CRITERIOS DE ACEPTACIÓN

- [ ] Todos los tests pasan (≥85% coverage en analysis/)
- [ ] Soporte n-niveles funcional (tested min 1-5 niveles)
- [ ] Parametrización funcionando en 3 modos (COMPACT, RELATIONS, ALL)
- [ ] HTML con pestañas diferenciadas (entrada/salida)
- [ ] Cardinality markers visibles en Graphviz
- [ ] Cache integrado y sin memory leaks
- [ ] Documentación completa (inline + guides)
- [ ] Cero deuda técnica en analysis/
- [ ] PEP8 100% compliance (ruff check clean)
- [ ] MIGRATION_GUIDE.md comprensible para usuarios

---

## 🚀 SIGUIENTE PASO

Fase 1 ejecutada:
→ Auditoría completada en 01-AUDIT.md
→ Diseño objetivo completado en 02-DESIGN.md
→ Arquitectura validada para iniciar Fase 2

Fase 2 ejecutada:
→ Núcleo multinivel extraído en analysis/base.py
→ Graphviz adaptado al modelo GraphDocument
→ Contrato de configuración de grafo migrado a max_depth, direction y columns.mode
→ HTML y Word adaptados para consumir el nuevo contrato

Siguiente paso operativo:
→ Representación HTML por pestañas y por sentido implementada
→ Migración funcional de configuración y uso documentada
→ Resumen Word de niveles totales/no visibles implementado
→ Pruebas de integración HTML/Word ampliadas
→ pyproject.toml y CHANGELOG alineados a v0.6.0
→ Matplotlib alineado al modelo multinivel

**Comandos sugeridos**:
```bash
pytest tests/analysis/ --cov=src/util_bbdd/analysis --cov-report=html
ruff check src/util_bbdd/analysis/
mypy src/util_bbdd/analysis/
```

---

*Sesión iniciada: 2026-03-22 | Metodología: util_bbdd governance*
