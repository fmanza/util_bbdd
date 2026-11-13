# Guía: Documentación Markdown de la base de datos

## 1. Objetivo

Genera la documentación de un schema en Markdown (desde 5.3.0) y conviértela en un recurso vivo, en este orden:

1. Generarla: un fichero por tabla, vista y rutina, con diagramas entidad-relación de Mermaid.
2. Publicarla como sitio con Zensical, también sin Internet.
3. Versionarla con git.
4. Enlazarla con el código y los documentos funcionales y técnicos mediante un mapa de trazabilidad.
5. Ver qué cambió respecto de la generación anterior.
6. Dársela a una IA para que la interprete.

Es una guía *how-to*. La referencia completa de opciones está en
[Generador de Documentación de BD](../api/database_documentation.md#documentacion-markdown-markdown).

## 2. Requisitos Previos

- util_bbdd 5.3.0 o posterior y un `SyncDatabaseManager` conectado, con permiso de lectura sobre el catálogo.
- **No hace falta Graphviz**: los diagramas son texto Mermaid.
- Para publicar: Zensical (`pip install zensical`). Lo usa el CI de este proyecto y es opcional para generar.
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
  manifest.json      zensical.toml  # configuración del sitio (5.6.0; antes, mkdocs.yml)
  README.md                         # cómo verla (VS Code, Zensical) y qué es cada fichero (5.5.0)
  docs/index.md                     # inventario, alcance del filtro, enlaces y leyenda de los diagramas
  docs/tables/index.md              # letras → index-a.md, index-a-2.md… (200 entradas por página)
  docs/tables/pedidos.md            # una página por tabla
  docs/views/…  docs/routines/…  docs/database/…
  docs/catalog.json  docs/llms.txt  docs/llms-full.txt
```

Para un visor o una herramienta, `manifest.json` → `pages` (desde 5.4.0) lista todas las páginas con su título en
texto plano, su sección y su papel (portada, índice, letra, objeto). Con eso se construye un árbol sin deducirlo de
las carpetas ([contrato](../api/database_documentation.md#contrato-de-salida)).

Cada página de tabla empieza con un **front matter** en una línea JSON:

- `id` estable (`table:public.pedidos`);
- `pk`;
- `fk_out`, las FK salientes con el id de la tabla referenciada;
- `fk_in`, los ids de las tablas que la referencian;
- `hash`, que cambia si cambia su estructura.

Cada columna tiene un ancla (`pedidos.md#col-cliente-id`).

### 3.3 Publicar con Zensical

```bash
cd docs_bd/ventas/MARKDOWN
zensical build --strict     # o: zensical serve
```

- **Navegación**: el `zensical.toml` generado tiene una `nav` corta (Inicio, Tablas, Vistas, Rutinas…). A cada objeto se
  llega por los índices por letra o por el buscador; con cientos de tablas, la barra lateral sigue siendo usable.
- **Sin Internet**: Zensical carga Mermaid de `unpkg.com`, y sin Internet los diagramas no se dibujan. Pasa un Mermaid
  local:

  ```python
  imprimir["markdown"]["mermaid_js"] = "node_modules/mermaid/dist/mermaid.min.js"
  ```

  Se copia a `docs/assets/javascripts/mermaid.min.js` y se carga desde el sitio: Zensical solo va a unpkg si no hay
  ninguno cargado. El `zensical.toml` lleva además `font = false` en `[project.theme]`, para no pedir Google Fonts.
- **Un solo Mermaid para muchas documentaciones** (desde 5.4.0): con `mermaid_js_ref` no se copia nada y `zensical.toml`
  lo referencia; pon tú el fichero en esa ruta antes de publicar (o usa una URL `https://`):

  ```python
  imprimir["markdown"]["mermaid_js_ref"] = "assets/javascripts/mermaid.min.js"
  ```

  Si falta, el build no avisa y el sitio vuelve a cargar Mermaid de unpkg (sin Internet, sin diagramas): ver
  [Mermaid referenciado](../api/database_documentation.md#mermaid-referenciado-mermaid_js_ref).
- **Configuración propia**: con `zensical_toml: False` no se genera el `zensical.toml`; usa el tuyo con
  `pymdownx.superfences` y la `custom_fence` de Mermaid.
- **`mkdocs.yml` (en desuso)**: hasta 5.5.0 la carpeta traía `mkdocs.yml`. Desde 5.6.0 solo se genera con
  `mkdocs_yml: True` (aviso en el log; se retirará en 6.0.0). Al regenerar sobre una carpeta anterior, el
  `mkdocs.yml` sin tocar se borra como cualquier fichero generado que ya no se produce; si lo editaste, se
  conserva. Zensical lee primero `zensical.toml`.

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
  juntos, y no se genera nada. Los mensajes nombran el fichero, nunca su ruta.
- **Validar antes, sin conexión** (desde 5.7.0): por ejemplo, al recibir el fichero en una aplicación:

  ```python
  from util_bbdd.doc import validate_trace_map
  from util_bbdd.exceptions import DocumentationConfigError

  try:
      validate_trace_map("trazas.toml")  # mismas reglas; no devuelve nada si es válido
  except DocumentationConfigError as error:
      print(error)  # todos los errores juntos
  ```
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

### 3.8 Documentar solo un módulo (filtro)

Desde 5.5.0, `filtro` limita las tablas y vistas que se documentan, en todos los formatos:

```python
imprimir["filtro"] = {
    "incluir": ["MVG_*"],            # solo el módulo MVG
    "excluir": ["*_BAK", "TMP_*"],   # sin copias ni temporales, aunque empiecen por MVG_
}
result = DatabaseDocumentation(manager, Path("docs_bd"), imprimir=imprimir, formatos=["markdown"]).generate()
print(result.frontier)   # tablas de otros módulos unidas por FK a las de MVG
```

- **Patrones**: *glob* sin distinguir mayúsculas (`*` cualquier texto, `?` un carácter). Sin `incluir`, entra todo
  menos lo excluido.
- **Frontera**: las tablas de fuera unidas por una FK a alguna documentada. Se listan en la portada («Alcance») y se
  ven en los diagramas, sin ficha propia. Se desactiva con `"frontera": False`.
- **Relaciones**: en la ficha de cada tabla, las relacionadas que no se documentan salen sin enlace y marcadas
  «frontera, sin ficha» o «excluida por el filtro», tanto en las claves foráneas como en «Referenciada por».
- **Comparar con `previous`**: si la generación anterior se hizo con otro filtro (o sin él), se comparan solo las
  tablas y vistas que entran en ambos; `changes.md` lo avisa.

### 3.9 Comparar entornos (Calidad y producción)

Hay dos formas, según haya conexión a los dos entornos o no:

- **Con conexión a ambos** (mismo motor o distinto): `SchemaComparator` compara los dos schemas en vivo y genera el
  informe en SQL, HTML, Word, Excel o Markdown ([guía](comparator.md)).
- **Sin conexión, con la documentación de cada entorno** (mismo motor): genera la de Calidad y, al generar la de
  producción, pasa la de Calidad como `previous`. `changes.md` y `changes.json` muestran la deriva. Si los schemas se
  llaman distinto, se compara por nombre de objeto y se avisa.

```python
calidad = DatabaseDocumentation(manager_calidad, Path("docs_bd"), Path("calidad"), imprimir=imprimir,
                                formatos=["markdown"]).generate().outputs["markdown"]
imprimir_prod = {**imprimir, "markdown": {"previous": str(calidad)}}
DatabaseDocumentation(manager_prod, Path("docs_bd"), Path("produccion"), imprimir=imprimir_prod,
                      formatos=["markdown"]).generate()
# docs_bd/produccion/MARKDOWN/docs/changes.md: «anterior» = Calidad, «actual» = producción
```

Usa el mismo `filtro` en las dos generaciones para comparar el mismo módulo.

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
| Con `mermaid_js_ref`, el sitio sin Internet no dibuja los diagramas y el build no avisó | El fichero referenciado no está en `docs/<ruta>` | Copia `mermaid.min.js` a esa ruta antes de publicar; el build no lo comprueba |
| `DocumentationConfigError: markdown.trace_map (...) no es válido: ...` | Errata o tipo incorrecto en el mapa | El mensaje lista todos los errores con su ruta (`tables.X.requirement`) |
| `DocumentationConfigError: ... la generación anterior es de otro motor` | `previous` apunta a una documentación de otro motor | Compara solo generaciones del mismo motor; entre motores, usa `SchemaComparator` |
| Una tabla cambió y no aparece en `changes.md` | Solo cambiaron restricciones únicas, identidad o columnas calculadas: el modelo `SchemaDiff` no las recoge | Revisa el `hash` de la tabla en `catalog.json` o la página de la tabla |
| Una FK aparece «modificada» con las mismas columnas | Cambió solo `ON DELETE`/`ON UPDATE` (el modelo no tiene esos campos) | La página de la tabla muestra las acciones actuales |
| Un `PACKAGE` de Oracle aparece en `changes.md` pero no en `changes.json` | `SchemaDiff` solo admite `PROCEDURE` y `FUNCTION` | Comportamiento esperado |
| Dos funciones sobrecargadas comparten página | El catálogo de rutinas no las distingue (igual que Word y HTML) | Comportamiento esperado |
| `manifest.json` o `zensical.toml` indican una versión de util_bbdd antigua | Instalación editable con metadatos de otra versión | `pip install -e .` para refrescar los metadatos |
| Un fichero generado que edité no se borra al dejar de generarse | Se conserva a propósito: su hash ya no es el del manifiesto | Bórralo a mano si ya no lo quieres |
| Con 1 nivel de relación el diagrama muestra tres tablas en cadena | Los niveles se cuentan en cada sentido: con `direction: "both"`, 1 nivel enseña la tabla de la que depende y la que depende de ella | Es lo esperado; `direction: "outgoing"` o `"incoming"` para un solo sentido. El resumen dice «Niveles por sentido» desde 5.5.0 |
| Una tabla relacionada sale sin enlace, marcada «frontera» o «excluida» | El `filtro` la deja fuera: no tiene ficha | Amplía `filtro.incluir` si la necesitas documentada |
| Diagramas partidos o sin columnas | Superaban 40 entidades o 50 000 caracteres (aviso en la página) | Baja `grafo.max_depth` o `grafo.max_subnodes` |
