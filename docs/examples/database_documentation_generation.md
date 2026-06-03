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

- **Separación constructor / `generate()`**: el constructor carga los metadatos iniciales (tablas, vistas, rutinas) pero no escribe ficheros. `generate()` dispara la escritura. Esto permite configurar y verificar antes de ejecutar I/O.
- **`imprimir_config`**: diccionario que controla qué documentar y cómo presentarlo. Las claves `tablas`, `vistas` y `rutinas` controlan las secciones; la clave `grafo` configura los diagramas de relaciones.
- **Fragmentación Word automática**: con `tablas_por_documento=50` (default), esquemas grandes se dividen en múltiples ficheros `.docx` numerados automáticamente.
- **Dependencia `util-bbdd[doc]`**: la generación de Word, Excel y HTML requiere el extra `doc` instalado.

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
# Instalar dependencias de documentación
pip install "util-bbdd[doc]"

# Validación sintáctica
python -m py_compile docs/examples/database_documentation_generation.py

# Ejecución (usa SQLite local; no requiere servidor externo)
python docs/examples/database_documentation_generation.py
```

Los ficheros se generan en `generated_docs/` bajo subdirectorios `HTML/`, `WORD/` y `EXCEL/`.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Generación de Documentación de BD](../functional/database-documentation.md) — objetivo de negocio y casos de uso
- **Referencia técnica**: [Generador de Documentación](../api/database-documentation.md) — API de `DatabaseDocumentation` y parámetros de `imprimir`
- **Ejemplos relacionados**: [Generación de Grafos de Relaciones](graph_generation.md) — grafos standalone sin documentación completa
