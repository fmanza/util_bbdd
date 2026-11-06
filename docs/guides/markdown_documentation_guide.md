# Guía: Documentación Markdown de la base de datos

## 1. Objetivo

Genera la documentación de un schema en Markdown (desde 5.3.0) y conviértela en un recurso vivo, en este orden:

1. Generarla: un fichero por tabla, vista y rutina, con diagramas entidad-relación de Mermaid.
2. Publicarla como sitio con Zensical o MkDocs, también sin Internet.
3. Versionarla con git.
4. Enlazarla con el código y los documentos funcionales y técnicos mediante un mapa de trazabilidad.
5. Ver qué cambió respecto de la generación anterior.
6. Dársela a una IA para que la interprete.

Es una guía *how-to*. La referencia completa de opciones está en
[Generador de Documentación de BD](../api/database_documentation.md#documentacion-markdown-markdown).

## 2. Requisitos Previos

- util_bbdd 5.3.0 o posterior y un `SyncDatabaseManager` conectado, con permiso de lectura sobre el catálogo.
- **No hace falta Graphviz**: los diagramas son texto Mermaid.
- Para publicar: Zensical (`pip install zensical`) o MkDocs Material. Lo usa el CI de este proyecto y es opcional
  para generar.
- Para publicar sin Internet: un `mermaid.min.js` local, por ejemplo el de `npm install mermaid` en
  `node_modules/mermaid/dist/`.

## 3. Pasos

### 3.1 Generar la documentación

```python
from pathlib import Path

from util_bbdd import SyncDatabaseManager
from util_bbdd.doc import DatabaseDocumentation

imprimir = {
    "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True, "pk": True, "fk": True, "unicas": True, "indices": True},
    "vistas": {"imprimir_vistas": True, "ddl": True, "columnas": True},
    "rutinas": {"imprimir_procedures": True, "imprimir_function": True},
    "grafo": {"enabled": True, "max_depth": 2, "cardinality": {"show_constraint_name": True}},
    "markdown": {"site_name": "Modelo de datos de Ventas"},
}

with SyncDatabaseManager("postgresql", conn_params) as manager:
    result = DatabaseDocumentation(
        manager, Path("docs_bd"), Path("ventas"), imprimir=imprimir, formatos=["markdown"]
    ).generate()

print(result.outputs["markdown"])  # docs_bd/ventas/MARKDOWN
```

- **Secciones**: las mismas que en Word, con las mismas opciones de `imprimir`. Sin activar ninguna, cada página solo
  lleva el título y el comentario.
- **Diagramas**: con `grafo.enabled`, cada tabla lleva su diagrama al final, con el resumen de niveles debajo. La
  profundidad es `grafo.max_depth` con el tope `markdown.max_diagram_depth` (2 por defecto); si recorta, la página lo
  avisa.
- **Columnas de los diagramas**: las elige `grafo.columns.mode`, igual que en Graphviz:
  - `relations`: las de las relaciones dibujadas;
  - `compact`: esas primero y después las demás;
  - `all`: todas.

  `grafo.show_columns: False` las quita.

### 3.2 Revisar la salida

```text
docs_bd/ventas/MARKDOWN/
  manifest.json      mkdocs.yml
  docs/index.md                     # inventario, enlaces y leyenda de los diagramas
  docs/tables/index.md              # letras → index-a.md, index-a-2.md… (200 entradas por página)
  docs/tables/pedidos.md            # una página por tabla
  docs/views/…  docs/routines/…  docs/database/…
  docs/catalog.json  docs/llms.txt  docs/llms-full.txt
```

Cada página de tabla empieza con un **front matter** en una línea JSON:

- `id` estable (`table:public.pedidos`);
- `pk`;
- `fk_out`, las FK salientes con el id de la tabla referenciada;
- `fk_in`, los ids de las tablas que la referencian;
- `hash`, que cambia si cambia su estructura.

Cada columna tiene un ancla (`pedidos.md#col-cliente-id`).

### 3.3 Publicar con Zensical (o MkDocs)

```bash
cd docs_bd/ventas/MARKDOWN
zensical build --strict     # o: zensical serve
```

- **Navegación**: el `mkdocs.yml` generado tiene una `nav` corta (Inicio, Tablas, Vistas, Rutinas…). A cada objeto se
  llega por los índices por letra o por el buscador; con cientos de tablas, la barra lateral sigue siendo usable.
- **Sin Internet**: Zensical carga Mermaid de `unpkg.com`, y sin Internet los diagramas no se dibujan. Pasa un Mermaid
  local:

  ```python
  imprimir["markdown"]["mermaid_js"] = "node_modules/mermaid/dist/mermaid.min.js"
  ```

  Se copia a `docs/assets/javascripts/mermaid.min.js` y se carga desde el sitio: Zensical solo va a unpkg si no hay
  ninguno cargado. El `mkdocs.yml` lleva además `theme.font: false`, para no pedir Google Fonts.
- **Configuración propia**: con `mkdocs_yml: False` no se genera el `mkdocs.yml`; usa el tuyo con
  `pymdownx.superfences` y la `custom_fence` de Mermaid.

### 3.4 Versionar con git

1. Usa un `fichero_salida` fijo (`Path("ventas")`) para regenerar siempre en la misma carpeta.
2. Regenera tras cada cambio de esquema y revisa con `git diff`. La salida es **idéntica** para el mismo esquema y las
   mismas opciones; solo cambia la fecha de `manifest.json`.
3. Ficheros sobrantes: al regenerar se borran solo los ficheros que generó la vez anterior, que ya no se producen y
   que nadie ha modificado (por ejemplo, la página de una tabla eliminada). Tus propios ficheros dentro de la carpeta,
   y los generados que hayas editado, se conservan.
4. Cancelaciones y errores: la generación se escribe en una carpeta temporal y se publica al final. Si se cancela
   (`cancel_token`) o falla, la versión anterior queda intacta.

### 3.5 Mapa de trazabilidad

Crea un fichero TOML (recomendado: admite comentarios) y pásalo en `markdown.trace_map`:

```toml
version = 1                                    # opcional

[tables."PEDIDOS"]                             # nombre exacto o, si no es ambiguo, sin distinguir mayúsculas
code = ["src/ventas/pedidos.py#Pedido", "src/ventas/service.py"]
functional = ["docs/functional/ventas.md#alta-de-pedido"]
technical = ["docs/api/ventas.md"]
requirements = ["REQ-012", "https://jira.example.com/browse/VEN-7"]
tags = ["ventas"]
notes = "Cabecera de pedido; el detalle está en LINEAS."

[tables."PEDIDOS".columns."CLIENTE_ID"]        # trazabilidad por columna
code = ["src/ventas/pedidos.py#Pedido.cliente_id"]

[views."V_PEDIDOS_ABIERTOS"]
functional = ["docs/functional/ventas.md#pedidos-abiertos"]

[routines."PROCEDURE:P_ALTA_PEDIDO"]           # TIPO:nombre
code = ["src/ventas/alta.py"]
```

El equivalente en JSON (`.json`) tiene la misma estructura:
`{"tables": {"PEDIDOS": {"code": [...], "columns": {"CLIENTE_ID": {...}}}}}`.

- **Validación estricta al crear `DatabaseDocumentation`**: una sección o un campo desconocidos (una errata como
  `requirement`), un tipo incorrecto o un error de sintaxis dan `DocumentationConfigError`, con todos los errores
  juntos, y no se genera nada.
- **Referencias**: son texto y nunca se leen del disco. Las URL `http(s)` se enlazan; el resto (rutas,
  `fichero#Clase`) se muestra como código.
- **Salida**:
  - en cada página, una sección «Trazabilidad», con la columna enlazada a su ancla;
  - en el front matter y en `catalog.json`, la clave `trace`, que no cambia el `hash`;
  - `docs/traceability.md`, con la cobertura por tipo de objeto y de referencia, la matriz, los objetos sin trazar,
    qué objetos cubre cada requisito y cada fichero de código, y las **entradas del mapa sin objeto** (tablas
    renombradas o eliminadas, columnas inexistentes, nombres ambiguos).

### 3.6 Comparar con la generación anterior

```python
imprimir["markdown"]["previous"] = "docs_bd/ventas/MARKDOWN"   # la carpeta, su docs/ o su catalog.json
```

- **Qué se compara**: se lee el `catalog.json` de esa generación, sin conectarse a la base de datos, y se publican
  `docs/changes.md` (con enlaces a las páginas actuales) y `docs/changes.json`.
- **Visor de la web**: `changes.json` usa el formato `util_bbdd.schema_diff` (`SchemaDiff.from_dict`), el mismo que el
  informe de comparación y el visor de util_bbdd_web.
- **Misma carpeta**: con un `fichero_salida` fijo, `previous` puede ser **la misma carpeta** que se va a regenerar. El
  catálogo anterior se lee antes de publicar la nueva versión.
- **Schema distinto** (por ejemplo, desarrollo frente a producción): se compara por nombre de objeto y se avisa.
- **Motor distinto**: es error, porque los tipos no son comparables.
- **Tipos de objeto no documentados en las dos generaciones** (por ejemplo, vistas desactivadas): no se comparan, y
  se avisa en lugar de darlos por eliminados.

### 3.7 Dársela a una IA

| Fichero | Para qué |
|---|---|
| `docs/llms.txt` | Índice con un enlace y un comentario por objeto (formato de llmstxt.org) |
| `docs/llms-full.txt` | Todas las páginas en un fichero, cada una precedida de `<!-- <id> · <ruta> -->` |
| `docs/catalog.json` | Estructura completa: columnas, claves, índices y hashes ([ADR-006](../adr/ADR-006-catalogo-documentacion-markdown.md)) |
| Front matter e id | Referencias estables: `table:public.pedidos` en código, requisitos o el mapa de trazabilidad |
| `docs/traceability.md` / `docs/changes.md` | Contexto de trazas y de cambios recientes |

## 4. Verificación

```bash
python docs/examples/markdown_documentation.py
```

Salida esperada: el árbol de la carpeta `MARKDOWN`, un extracto de la página `pedidos.md` con su diagrama `erDiagram`,
la cobertura de `traceability.md` y el resumen de `changes.md`. Para el sitio:

```bash
cd <directorio_salida>/<nombre>/MARKDOWN && zensical build --strict
# No issues found
```

## 5. Variantes y Solución de Problemas

| Escenario/Error | Causa probable | Solución |
|---|---|---|
| El sitio muestra el código `erDiagram` en lugar del diagrama | Sin Internet: Zensical no puede cargar Mermaid de unpkg | `markdown.mermaid_js` con un `mermaid.min.js` local |
| `DocumentationConfigError: markdown.trace_map (...) no es válido: ...` | Errata o tipo incorrecto en el mapa | El mensaje lista todos los errores con su ruta (`tables.X.requirement`) |
| `DocumentationConfigError: ... la generación anterior es de otro motor` | `previous` apunta a una documentación de otro motor | Compara solo generaciones del mismo motor; entre motores, usa `SchemaComparator` |
| Una tabla cambió y no aparece en `changes.md` | Solo cambiaron restricciones únicas, identidad o columnas calculadas: el modelo `SchemaDiff` no las recoge | Revisa el `hash` de la tabla en `catalog.json` o la página de la tabla |
| Una FK aparece «modificada» con las mismas columnas | Cambió solo `ON DELETE`/`ON UPDATE` (el modelo no tiene esos campos) | La página de la tabla muestra las acciones actuales |
| Un `PACKAGE` de Oracle aparece en `changes.md` pero no en `changes.json` | `SchemaDiff` solo admite `PROCEDURE` y `FUNCTION` | Comportamiento esperado |
| Dos funciones sobrecargadas comparten página | El catálogo de rutinas no las distingue (igual que Word y HTML) | Comportamiento esperado |
| `manifest.json` o `mkdocs.yml` indican una versión de util_bbdd antigua | Instalación editable con metadatos de otra versión | `pip install -e .` para refrescar los metadatos |
| Un fichero generado que edité no se borra al dejar de generarse | Se conserva a propósito: su hash ya no es el del manifiesto | Bórralo a mano si ya no lo quieres |
| Diagramas partidos o sin columnas | Superaban 40 entidades o 50 000 caracteres (aviso en la página) | Baja `grafo.max_depth` o `grafo.max_subnodes` |
