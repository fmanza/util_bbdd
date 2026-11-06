# PLAN + AUDIT_PLAN — Grupo D (mapa de trazabilidad)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §4.7 y §7, grupo D). Se apoya en el grupo C
(`8c629287`). Quedan fuera E (`CHANGES.md`) y F (documentación, web y versión).

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Un fichero opcional (`imprimir["markdown"]["trace_map"]`) relaciona cada objeto con código, documentos funcionales y técnicos y requisitos. La documentación Markdown lo vuelca en cada página, en el front matter, en `catalog.json` y en una página `traceability.md` con la cobertura y los índices inversos |
| Módulos | `doc/infrastructure/renderers/markdown/_trace.py` (nuevo): modelo, carga, validación y páginas; `_pages.py`, `_front_matter.py`, `_catalog.py`, `_site.py` y `markdown_generator.py` (enganche); `print_config_manager.py` (clave `trace_map`); `database_documentation.py` (validación al construir) |
| API pública | Clave nueva `markdown.trace_map` (ruta a `.toml` o `.json`). Campo nuevo opcional `trace` en los objetos de `catalog.json`: aditivo, así que `format_version` sigue en 1 (ADR-006). MINOR |
| Contrato de entrada | Formato decidido por el usuario: TOML recomendado y JSON aceptado, elegido por extensión |
| Contrato de salida | Determinista; las referencias son **texto**: no se leen ni se resuelven contra el disco |
| Restricciones | Sin dependencias nuevas (`tomllib` y `json` son de la biblioteca estándar) |
| Migraciones | No |

## PLAN

### D1 · Formato del mapa (v1)

```toml
version = 1                                   # opcional; si se da, debe ser 1

[tables."PEDIDOS"]
code = ["src/ventas/pedidos.py", "src/ventas/service.py#PedidoService"]
functional = ["docs/functional/ventas.md#alta-de-pedido"]
technical = ["docs/api/ventas.md"]
requirements = ["REQ-012", "https://jira.example.com/browse/VEN-7"]
tags = ["ventas"]
notes = "Cabecera de pedido; el detalle está en LINEAS."

[tables."PEDIDOS".columns."CLIENTE_ID"]       # trazabilidad por columna (opcional)
code = ["src/ventas/pedidos.py#Pedido.cliente_id"]

[views."V_PEDIDOS_ABIERTOS"]
functional = ["docs/functional/ventas.md#pedidos-abiertos"]

[routines."PROCEDURE:P_ALTA_PEDIDO"]          # clave TIPO:nombre, como en las páginas
code = ["src/ventas/alta.py"]
```

- Secciones admitidas: `tables`, `views` y `routines`.
- Campos de cada objeto: `code`, `functional`, `technical`, `requirements` y `tags` (listas de cadenas), y `notes`
  (cadena).
- Las tablas pueden llevar además `columns.<columna>`, con los mismos campos salvo `columns`.
- Validación **estricta** al construir `DatabaseDocumentation` (`DocumentationConfigError`, con todos los errores
  juntos):
  - extensión distinta de `.toml` o `.json`;
  - fichero ilegible o con sintaxis inválida;
  - sección o campo desconocido, lo que detecta erratas como `requirement`;
  - tipos incorrectos;
  - `version` distinta de 1.
- Nombres de objeto y columna:
  - primero coincidencia exacta;
  - si no la hay, sin distinguir mayúsculas, siempre que no sea ambigua (Oracle guarda en mayúsculas y el usuario
    escribe en minúsculas);
  - una entrada que no casa con ningún objeto documentado no es un error: se lista en `traceability.md`.

### D2 · Salida

| Dónde | Qué |
|---|---|
| Página del objeto | Sección `## Trazabilidad` al final: tabla `Tipo \| Referencias`, etiquetas, notas y, para tablas, subsección por columna, con un enlace al ancla `#col-…` de la columna |
| Front matter | Clave `trace` con el mapa del objeto. **No entra en `hash`**: el hash identifica la estructura del objeto, y cambiar una traza no debe marcarlo como modificado en `CHANGES.md` |
| `catalog.json` | Campo `trace` en el objeto (aditivo, ADR-006), con el mismo criterio para `hash` |
| `docs/traceability.md` | Ver D3 |
| `llms.txt` | Entrada en `Optional`: `[Trazabilidad](traceability.md)` |
| `mkdocs.yml` | Entrada «Trazabilidad» en la `nav` corta |
| `llms-full.txt` | Las secciones de trazabilidad ya van en cada página |

Sin `trace_map` no cambia nada: ni sección, ni página, ni clave `trace`.

### D3 · `docs/traceability.md`

1. **Cobertura**: por tipo de objeto, cuántos documentados tienen al menos una referencia y el porcentaje, también
   por tipo de referencia (código, funcional, técnico, requisitos).
2. **Matriz**: una fila por objeto trazado con su enlace y los recuentos por tipo. Con 500 tablas solo se listan las
   trazadas.
3. **Objetos sin trazar**: nombres enlazados en una lista compacta separada por comas, por tipo.
4. **Índices inversos**: por requisito (`REQ-012` → objetos) y por fichero de código (la parte anterior a `#` →
   objetos y columnas), ordenados.
5. **Entradas del mapa sin objeto**: claves que no casan, para detectar tablas renombradas o eliminadas.

### D4 · Render de referencias (seguridad)

- `http://` o `https://` → enlace Markdown: la URL se codifica de forma segura y el texto se escapa.
- Cualquier otra cosa → *code span*: el contenido queda literal; las rachas de backticks se rodean con más
  backticks y `|` se escapa dentro de tablas.
- Nunca se generan `javascript:`, `data:` ni rutas relativas que puedan romper `zensical build --strict`.
- `notes` y `tags` pasan por `md_text`.

### Tests

| Fichero | Casos |
|---|---|
| `test_doc_markdown_trace.py` | Carga TOML y JSON equivalentes con el mismo resultado; errores juntos (sección y campo desconocidos, tipos, versión, extensión, sintaxis); casado exacto, sin mayúsculas y ambiguo; columnas; render de referencias (`http(s)`, `javascript:` como código, backticks, `\|`); `traceability.md` (cobertura, matriz, inversos, sin objeto); front matter y `catalog.json` con `trace` y `hash` sin cambios respecto a no tener mapa; `llms.txt` y `nav`; determinismo; sin mapa no cambia nada; ruta inválida → `DocumentationConfigError` antes de generar |
| `test_doc_markdown_e2e.py` (ampliado) | `zensical build --strict` con mapa (enlaces a anclas de columna y a `traceability.md`) |

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| DF1 | Casado sin mayúsculas ambiguo (`Foo` y `FOO` documentados, mapa con `foo`) | No casa; se lista en «sin objeto» con el motivo «ambiguo» |
| DF2 | `traceability.md` enorme con miles de objetos | Solo los trazados en la matriz; los no trazados, en una lista compacta |
| DF3 | El mapa se desactualiza (tablas renombradas) | «Entradas sin objeto» lo hace visible; con `CHANGES.md` (grupo E) se verá qué cambió |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| DT1 | Validar al construir exige leer el fichero dos veces (construcción y generación) | Coste despreciable. Se valida en la fachada, tras `settings()`, con la misma función de carga: sin tocar `DocumentationBootstrap` |
| DT2 | Que `trace` entre en `hash` rompería el uso de `hash` para detectar cambios de estructura | Se excluye a propósito y lo fija un test |
| DT3 | Tamaño de `_pages.py` | La sección de trazabilidad se construye en `_trace.py`; `_pages.py` solo la añade |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| DS1 | Enlaces `javascript:` o `data:` desde el mapa | Solo `http(s)` como enlace; el resto como código literal |
| DS2 | HTML o Markdown en `notes`, `tags` o referencias | `md_text` y *code spans* |
| DS3 | Rutas del mapa con travesía (`../../etc`) | Nunca se leen: son texto |
| DS4 | Fichero de mapa enorme o malicioso (TOML/JSON profundos) | Esquema estricto y poco profundo, y límite de tamaño del fichero (1 MB, configurable en código) |

### Simplificaciones

- Sin patrones en las claves (`VTA_*`): queda para una fase posterior (PLAN general §7).
- Sin comprobar que las rutas de `code` existen en un repositorio: es texto. Validarlas sería otra herramienta.

### Veredicto: `GO`

Sin condiciones abiertas. Hay dos decisiones de diseño que conviene que confirme el usuario al aprobar:

1. trazabilidad **por columna** incluida;
2. validación **estricta**: campos desconocidos son error, no aviso.
