# Ejemplo: Generación de Grafos de Relaciones

## 1. Contexto del Ejemplo

Introspecciona las claves foráneas de un esquema y genera grafos SVG/PNG que muestran las relaciones entre tablas. Útil para documentar la estructura de una base de datos sin escribir DDL manualmente.

Resuelve la necesidad de comunicar el modelo de datos a equipos de arquitectura, auditoría o soporte sin exponer las credenciales ni requerir acceso directo a la BD.

!!! note "Dependencia opcional"
    Requiere el extra `analysis`: `pip install util_bbdd[analysis]` y los binarios de Graphviz instalados en el sistema (`dot` en PATH).

## 2. Implementación de Referencia

```python
--8<-- "examples/graph_generation.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`max_depth`**: controla cuántos saltos de FK se incluyen desde la tabla raíz. Valores > 3 generan grafos ilegibles en esquemas complejos.
- **`LevelDirection`**: `OUTGOING` muestra tablas hijas (las que la tabla referencia); `INCOMING` tablas padre (las que la referencian); `BOTH` ambas.
- **Paginación automática**: si `max_subnodes` se configura y la tabla tiene muchas relaciones, el módulo genera múltiples imágenes numeradas automáticamente.
- **`pipe_*` vs `generate_*`**: los métodos `pipe_*` retornan bytes sin escribir en disco (útil para embeber en aplicaciones web); los `generate_*` escriben directamente al sistema de archivos.

## 4. Ejecución y Pruebas

```bash
# Instalar extra de análisis
pip install "util_bbdd[analysis]"

# Instalar binarios Graphviz del sistema (Linux/macOS)
# apt install graphviz / brew install graphviz

# Validación sintáctica
python -m py_compile docs/examples/graph_generation.py

# Ejecución (requiere BD con FKs definidas)
python docs/examples/graph_generation.py
```

Los ficheros SVG/PNG se generan en el directorio de salida configurado.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Visualización de Grafos](../functional/graph_analysis.md) — casos de uso y reglas de negocio
- **Referencia técnica**: [Grafos de Relaciones](../api/analysis.md) — API de `GraphvizRelationshipGraphExt` y opciones de renderización
- **Ejemplos relacionados**: [Generación de Documentación de Base de Datos](database_documentation_generation.md) — grafos embebidos en documentación
