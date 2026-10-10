# Ejemplo: Generación de Documentación de Base de Datos

## 1. Contexto del Ejemplo

Genera documentación navegable (HTML, Word, Excel) de una base de datos a partir de una conexión activa, sin necesidad de escribir SQL ni conocer el esquema de antemano.

El caso principal usa SQLite para evitar credenciales reales. Resuelve la necesidad de compartir la estructura de una BD con equipos de arquitectura o auditoría sin acceso directo al servidor.

## 2. Implementación de Referencia

```python
--8<-- "examples/database_documentation_generation.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **Separación constructor / `generate()`**: el constructor solo valida la configuración (lanza `DocumentationConfigError` si un formato, el fichero de cabeceras o la plantilla Word no son válidos) y no consulta la base de datos. `generate()` lee el catálogo, escribe los ficheros y devuelve un `DocumentationResult` con la ruta de cada formato y el número de tablas, vistas y rutinas.
- **`imprimir_config`**: diccionario que controla qué documentar y cómo presentarlo. Las claves `tablas`, `vistas` y `rutinas` controlan las secciones; la clave `grafo` configura los diagramas de relaciones.
- **Fragmentación Word automática**: con `tablas_por_documento=50` (default), esquemas grandes se dividen en múltiples ficheros `.docx` numerados automáticamente.
- **Dependencias**: `openpyxl`, `python-docx` y `jinja2` (Excel, Word y HTML) van en la instalación base; los grafos necesitan el extra `analysis` y los binarios de Graphviz.

```python
# Generar solo HTML sin gráficos (caso mínimo)
from pathlib import Path
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

with SyncDatabaseManager("sqlite", {"database": ":memory:"}, use_pool=False) as mgr:
    doc = DatabaseDocumentation(
        db_manager=mgr,
        directorio_salida=Path("output"),
        imprimir={"tablas": {"imprimir_tablas": True}},
        formatos=["html"],
    )
    doc.generate()
```

## 4. Ejecución y Pruebas

```bash
# Grafos de relaciones (opcional): extra analysis + binarios de Graphviz
pip install "util_bbdd[analysis] @ git+https://github.com/fmanza/util_bbdd.git@v1.1.0"

# Validación sintáctica
python -m py_compile docs/examples/database_documentation_generation.py

# Ejecución (usa SQLite local; no requiere servidor externo)
python docs/examples/database_documentation_generation.py
```

Los ficheros se generan en `generated_docs/` bajo subdirectorios `HTML/`, `WORD/` y `EXCEL/`.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Generación de Documentación de BD](../functional/database_documentation.md) — objetivo de negocio y casos de uso
- **Referencia técnica**: [Generador de Documentación](../api/database_documentation.md) — API de `DatabaseDocumentation` y parámetros de `imprimir`
- **Ejemplos relacionados**: [Generación de Grafos de Relaciones](graph_generation.md) — grafos standalone sin documentación completa
