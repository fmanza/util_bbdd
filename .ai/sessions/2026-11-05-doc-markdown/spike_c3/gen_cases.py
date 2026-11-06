"""Spike C3: casos erDiagram (validos, hostiles y normalizados) + sitio Zensical para probarlos.

Genera:
  out/cases.json         lista de casos {id, desc, expect, text}
  out/site/mkdocs.yml    + out/site/docs/*.md (un bloque mermaid por caso, mas pagina de escape HTML)
"""

from __future__ import annotations

import json
import re
import sys

from pathlib import Path

sys.path.insert(0, r"C:\Desarrollo\python\libs\util_bbdd\src")
from util_bbdd.comparar.reporters._base import escape_markdown_table_cell, escape_mermaid_label  # noqa: E402

OUT = Path(__file__).parent / "out"

_TYPE_BAD = re.compile(r"[^A-Za-z0-9_\-()\[\]]")
_NAME_BAD = re.compile(r"[^A-Za-z0-9_]")


def norm_type(raw: str) -> str:
    t = _TYPE_BAD.sub("_", raw.strip())
    return t if t[:1].isascii() and t[:1].isalpha() else f"t_{t}"


def norm_name(raw: str) -> str:
    n = _NAME_BAD.sub("_", raw.strip())
    return n if n[:1].isascii() and n[:1].isalpha() else f"c_{n}"


def comment(raw: str) -> str:
    return escape_mermaid_label(raw).replace('"', "'")


def er(*lines: str) -> str:
    return "erDiagram\n" + "\n".join(f"    {line}" for line in lines)


CASES: list[dict[str, str]] = []


def case(cid: str, desc: str, expect: str, text: str) -> None:
    CASES.append({"id": cid, "desc": desc, "expect": expect, "text": text})


# --- Sintaxis base propuesta en el PLAN (§4.2, §4.4) ---
case("base", "alias, PK/FK, 1:N identificante y no identificante, etiqueta vacia", "ok", er(
    'e1["clientes"] {', "    INTEGER id PK", "}",
    'e2["pedidos"] {', "    INTEGER id PK", "    INTEGER cliente_id FK", "}",
    'e3["lineas"] {', "    INTEGER pedido_id PK, FK", "    INTEGER linea PK", "}",
    'e1 ||--o{ e2 : "fk_ped_cli"',
    'e2 ||--o{ e3 : ""',
))
case("card_all", "todas las cardinalidades propuestas + no identificante ..", "ok", er(
    'e1["a"] {', "    INTEGER id PK", "}", 'e2["b"] {', "    INTEGER a_id FK", "}",
    'e1 ||--o{ e2 : "1N"', 'e1 |o--o{ e2 : "1N nullable"', 'e1 ||--o| e2 : "11"',
    'e1 }o--o{ e2 : "MN"', 'e1 ||..o{ e2 : "no identificante"', 'e1 |o..o| e2 : "11 nullable"',
))
case("self_ref", "FK reflexiva (arbol)", "ok", er('e1["empleados"] {', "    INTEGER id PK", "    INTEGER jefe_id FK", "}",
                                             'e1 |o..o{ e1 : "fk_jefe"'))
case("multi_edge", "dos FK entre el mismo par", "ok", er('e1["cuentas"] {', "    INTEGER id PK", "}",
                                                     'e2["movs"] {', "    INTEGER origen FK", "    INTEGER destino FK", "}",
                                                     'e1 ||..o{ e2 : "fk_origen"', 'e1 ||..o{ e2 : "fk_destino"'))
case("no_attrs", "entidad sin atributos (columns.mode=none)", "ok", er('e1["a"]', 'e2["b"]', 'e1 ||--o{ e2 : ""'))
case("empty_block", "entidad con bloque vacio", "ok", er('e1["a"] {', "}", 'e2["b"] {', "}", 'e1 ||--o{ e2 : ""'))

# --- Tipos ---
case("type_parens", "tipos con parentesis y corchetes crudos", "ok", er(
    'e1["t"] {', "    VARCHAR(255) nombre", "    NUMBER(10) importe", "    int[] tags", "    string(99) x", "}"))
case("type_comma_raw", "decimal(10,2) crudo (doc: coma no permitida)", "fail?", er('e1["t"] {', "    decimal(10,2) precio", "}"))
case("type_comma_norm", "decimal(10,2) normalizado", "ok", er('e1["t"] {', f"    {norm_type('decimal(10,2)')} precio", "}"))
case("type_space_raw", "double precision crudo", "fail?", er('e1["t"] {', "    double precision valor", "}"))
case("type_space_norm", "tipos con espacios normalizados", "ok", er(
    'e1["t"] {', f"    {norm_type('double precision')} a", f"    {norm_type('timestamp(6) with time zone')} b",
    f"    {norm_type('character varying(50)')} c", f"    {norm_type('NUMBER(38,3)')} d",
    f"    {norm_type('INTERVAL DAY(2) TO SECOND(6)')} e", "}"))
case("type_digit_first", "tipo que empieza por digito/simbolo, normalizado", "ok", er(
    'e1["t"] {', f"    {norm_type('2D_POINT')} a", f"    {norm_type('_internal')} b", "}"))
case("type_unicode_raw", "tipo unicode crudo (dominio con tilde)", "fail?", er('e1["t"] {', "    código_postal cp", "}"))
case("type_unicode_norm", "tipo unicode normalizado", "ok", er('e1["t"] {', f"    {norm_type('código_postal')} cp", "}"))

# --- Nombres de atributo ---
case("attr_unicode_raw", "nombre de columna unicode crudo", "?", er('e1["t"] {', "    INTEGER año", "}"))
case("attr_space_norm", "nombre con espacios normalizado + nombre real en comentario", "ok", er(
    'e1["t"] {', f'    INTEGER {norm_name("mi col")} "{comment("mi col")}"',
    f'    INTEGER {norm_name("año")} "{comment("año")}"', f'    INTEGER {norm_name("1col")} "{comment("1col")}"', "}"))
case("attr_keys", "PK, FK y UK combinados + comentario", "ok", er(
    'e1["t"] {', '    INTEGER id PK "clave"', "    INTEGER x PK, FK", "    VARCHAR(10) codigo UK", "    INTEGER y FK, UK", "}"))
case("attr_reserved", "columnas con nombres que son palabras clave de Mermaid", "?", er(
    'e1["t"] {', "    INTEGER PK PK", "    INTEGER FK", "    VARCHAR(5) erDiagram", "    INTEGER end", "    INTEGER style", "}"))
case("attr_reserved_norm", "palabras clave con prefijo c_ si colisionan", "ok", er(
    'e1["t"] {', '    INTEGER c_PK PK "PK"', '    INTEGER c_FK "FK"', '    INTEGER c_end "end"', "}"))

# --- Alias de entidad (escape_mermaid_label actual) ---
hostile_names = [
    "VENTAS.PEDIDOS", "Mi Tabla (v2)", 'tab"la', "tab[la]", "año_fiscal ñ", "a:b", "a;b", "a{b}", "a|b",
    "a<script>alert(1)</script>", "a\nerDiagram\n x ||--|| y : z", "%%{init: {'theme':'dark'}}%%", "--", "a -- b",
    "classDef x fill:#f00", "x #quot; y", "&lt;", "a'b", "``", "日本語テーブル",
]
lines = []
for i, n in enumerate(hostile_names, start=1):
    lines += [f'e{i}["{escape_mermaid_label(n)}"] {{', "    INTEGER id PK", "}"]
lines += [f'e1 ||--o{{ e{i} : "{comment(n)}"' for i in range(2, len(hostile_names) + 1)]
case("alias_hostile", "alias y etiquetas con nombres hostiles escapados", "ok", er(*lines))
case("alias_unquoted_dot", "entidad sin alias con punto (lo que NO haremos)", "?", er("VENTAS.PEDIDOS {", "    INTEGER id", "}"))

# --- Comentarios hostiles ---
case("comment_hostile", "comentarios de atributo hostiles escapados", "ok", er(
    'e1["t"] {', *[f'    INTEGER c{i} "{comment(n)}"' for i, n in enumerate(hostile_names)], "}"))
case("comment_quote_raw", "comentario con comilla doble cruda", "fail?", er('e1["t"] {', '    INTEGER c "di "hola""', "}"))

# --- Etiquetas de relacion ---
case("label_unquoted_space", "etiqueta sin comillas con espacio", "fail?", er('e1["a"]', 'e2["b"]', "e1 ||--o{ e2 : fk uno"))

# --- Tamano: 80 entidades x 8 columnas, 160 relaciones ---
big = []
for i in range(1, 81):
    big += [f'e{i}["SCHEMA_LARGO.TABLA_CON_NOMBRE_BASTANTE_LARGO_{i:03d}"] {{']
    big += [f"    VARCHAR(255) columna_{k:02d}{' PK' if k == 0 else ''}" for k in range(8)] + ["}"]
for i in range(2, 81):
    big += [f'e1 ||--o{{ e{i} : "fk_{i}_a"', f'e{i - 1} |o..o{{ e{i} : "fk_{i}_b"']
case("big_80x8_160", "80 entidades, 8 columnas, 158 relaciones", "ok", er(*big))
big2 = []
for i in range(1, 301):
    big2 += [f'e{i}["T{i}"] {{', "    INTEGER id PK", "}"]
for i in range(2, 301):
    big2 += [f'e1 ||--o{{ e{i} : ""', f'e{i - 1} ||..o{{ e{i} : ""']
case("big_300_598", "300 entidades, 598 relaciones (sobre maxEdges=500?)", "?", er(*big2))


def build_site() -> None:
    site = OUT / "site"
    docs = site / "docs"
    (docs / "tables").mkdir(parents=True, exist_ok=True)
    (site / "mkdocs.yml").write_text(
        "site_name: Spike erDiagram\n"
        "docs_dir: docs\n"
        "theme:\n  name: material\n"
        "markdown_extensions:\n"
        "  - tables\n  - admonition\n  - attr_list\n  - toc:\n      permalink: true\n"
        "  - pymdownx.superfences:\n      custom_fences:\n        - name: mermaid\n          class: mermaid\n"
        "          format: !!python/name:pymdownx.superfences.fence_code_format\n",
        encoding="utf-8", newline="\n",
    )
    body = ["# Casos erDiagram", ""]
    for c in CASES:
        body += [f"## {c['id']}", "", f"{c['desc']} (esperado: {c['expect']})", "", "```mermaid", c["text"], "```", ""]
    (docs / "tables" / "cases.md").write_text("\n".join(body), encoding="utf-8", newline="\n")

    hostile = 'a<script>alert(1)</script> & <img src=x onerror=alert(2)> | `x` *y*'
    front = json.dumps({"title": 'pedidos "x": --- y', "id": "table:main.pedidos", "fk_in": ["table:main.lineas"]},
                       ensure_ascii=False, sort_keys=True)
    page = [
        "---", front, "---", "", "# Tabla: pedidos", "",
        f"**Comentario:** {escape_markdown_table_cell(hostile).replace('<', '&lt;').replace('>', '&gt;')}", "",
        "| Campo | Tipo | Comentario |", "|---|---|---|",
        f'| <a id="col-id"></a>id | INTEGER | {escape_markdown_table_cell(hostile).replace("<", "&lt;").replace(">", "&gt;")} |',
        "", "## DDL", "", "````sql", "CREATE TABLE t (c TEXT DEFAULT '```');", "````", "",
        "!!! warning \"Profundidad limitada a 2 (configurada 4)\"", "    Texto del aviso.", "",
        "[ir a columna](#col-id)", "",
    ]
    (docs / "tables" / "pedidos.md").write_text("\n".join(page), encoding="utf-8", newline="\n")
    (docs / "index.md").write_text("# Spike\n\n- [Casos](tables/cases.md)\n- [Pedidos](tables/pedidos.md)\n",
                                   encoding="utf-8", newline="\n")
    (docs / "catalog.json").write_text('{"format": "util_bbdd.doc.catalog"}\n', encoding="utf-8", newline="\n")
    (docs / "llms.txt").write_text("# Spike\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "cases.json").write_text(json.dumps(CASES, ensure_ascii=False, indent=2), encoding="utf-8")
    build_site()
    print(f"{len(CASES)} casos; tamano big_80x8_160 = {len(next(c for c in CASES if c['id']=='big_80x8_160')['text'])} chars")
