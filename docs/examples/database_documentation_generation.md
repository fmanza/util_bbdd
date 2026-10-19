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
- **`imprimir_config`**: diccionario que controla qué documentar y cómo presentarlo. Las claves `tablas`, `vistas` y `rutinas` controlan las secciones de objetos; `info_database`, `columnas_charset`, `almacenamiento` y `condiciones_motor` añaden secciones al final del documento; `plantilla_word`, `plantilla_html`, `tablas_por_documento`, `table_style` y `html_items_por_pagina` controlan la presentación, y `grafo` configura los diagramas de relaciones. Todas vienen desactivadas por defecto. Referencia de cada clave y ejemplo completo: [Configuración de `imprimir`](../api/database_documentation.md#configuracion-de-imprimir).
- **Batching automático de nombres**: cuando `fichero_salida` es `None`, el nombre se genera automáticamente. Las generaciones lanzadas dentro de `batch_window_seconds` (default 90 s) reutilizan la misma carpeta. Configurable con el parámetro `batch_window_seconds` (0 para deshabilitar, `None` para default, o un número de segundos personalizado).
- **Fragmentación Word automática**: con `tablas_por_documento=50` (default), esquemas grandes se dividen en múltiples ficheros `.docx` numerados automáticamente.
- **Dependencias**: `openpyxl`, `python-docx` y `jinja2` (Excel, Word y HTML) van en la instalación base; los grafos necesitan el extra `analysis` y los binarios de Graphviz.

```python
# Caso 1: Generar solo HTML sin gráficos (caso mínimo)
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

**Caso 2: Batching automático** (agrupar generaciones en la misma carpeta):
```python
# Generaciones lanzadas en los 90 segundos siguientes reutilizan la carpeta anterior
for i in range(3):
    doc = DatabaseDocumentation(
        db_manager=mgr,
        directorio_salida=Path("output"),
        # fichero_salida=None genera automático y se cachea
        formatos=["html"],
    )
    doc.generate()
    # Los tres archivos van a: output/<base-FECHA_HORA>/HTML/
```

**Caso 3: Deshabilitar batching** (cada generación en carpeta nueva):
```python
# Usar batch_window_seconds=0 para deshabilitar la cache
doc = DatabaseDocumentation(
    db_manager=mgr,
    directorio_salida=Path("output"),
    formatos=["html"],
    batch_window_seconds=0,  # Sin agrupamiento
)
doc.generate()
```

**Caso 4: Ventana más larga** (5 minutos):
```python
doc = DatabaseDocumentation(
    db_manager=mgr,
    directorio_salida=Path("output"),
    formatos=["html"],
    batch_window_seconds=300,  # Agrupa durante 5 minutos
)
doc.generate()
```

### Depuración: verificar el uso de la caché

Cuando se lanzan múltiples generaciones rápidamente, puedes ver si se reutiliza la carpeta (cache) activando logging `DEBUG`:

```python
import logging
from pathlib import Path
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

# Activa logging DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

with SyncDatabaseManager("sqlite", {"database": ":memory:"}) as mgr:
    # Primera generación
    doc1 = DatabaseDocumentation(mgr, Path("out"), formatos=["html"])
    doc1.generate()
    # Log: ✨ Generando nuevo nombre de carpeta... (nuevo)

    # Segunda generación (30 segundos después)
    doc2 = DatabaseDocumentation(mgr, Path("out"), formatos=["html"])
    doc2.generate()
    # Log: 📦 Reutilizando nombre de carpeta... (en cache)
```

**Símbolos en los logs**:
- `✨` → Nombre nuevo (cache vacía o caducada)
- `📦` → Nombre reutilizado del cache

## 4. Ejecución y Pruebas

```bash
# Grafos de relaciones (opcional): extra analysis + binarios de Graphviz
pip install "util_bbdd[analysis] @ git+https://github.com/fmanza/util_bbdd.git@v4.0.0"

# Validación sintáctica
python -m py_compile docs/examples/database_documentation_generation.py

# Ejecución (usa SQLite local; no requiere servidor externo)
python docs/examples/database_documentation_generation.py
```

Los ficheros se generan en `generated_docs/<nombre>/` bajo subdirectorios `HTML/`, `WORD/` y `EXCEL/` (con el ejemplo,
`generated_docs/demo-sqlite/`).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Generación de Documentación de BD](../functional/database_documentation.md) — objetivo de negocio y casos de uso
- **Referencia técnica**: [Generador de Documentación](../api/database_documentation.md) — API de `DatabaseDocumentation` y parámetros de `imprimir`
- **Ejemplos relacionados**: [Generación de Grafos de Relaciones](graph_generation.md) — grafos standalone sin documentación completa
