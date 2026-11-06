# PLAN + AUDIT_PLAN — Grupo A (base Mermaid ER en `_core` y `analysis`)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §7, grupo A). Los grupos B–F quedan fuera.

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Base reutilizable para dibujar diagramas ER Mermaid sin Graphviz y con orden estable |
| Módulos | `src/util_bbdd/_core/mermaid.py` (nuevo), `src/util_bbdd/analysis/mermaid_er.py` (nuevo), `analysis/base.py`, `analysis/graphviz_ext.py`, `analysis/__init__.py`, `comparar/reporters/_base.py`, `comparar/reporters/markdown_reporter.py` |
| API pública | Nuevo `util_bbdd.analysis.MermaidRelationshipGraph` (submódulo público → MINOR). `_core.mermaid` es interno |
| Contrato de entrada | `RelationshipGraphSource` (lo mismo que Graphviz y Matplotlib): snapshot por lotes, ADR-003 |
| Contrato de salida | `MermaidErResult` con uno o varios bloques `erDiagram` en texto, el `GraphDocument` y los avisos. Salida idéntica entre procesos (`PYTHONHASHSEED`) |
| Reglas de negocio | No inventar metadatos; cardinalidad con la misma lógica que Graphviz; lado padre `\|o` si alguna columna de la FK admite nulos (decisión del usuario) |
| Restricciones | Sin dependencias nuevas; no importar `graphviz`; sin cambio de comportamiento en `comparar` ni en Graphviz salvo el orden estable |
| Motores | Todos (independiente del motor; probado con fuente simulada y SQLite) |
| Migraciones | No |

## PLAN

### A1 · `_core/mermaid.py` (nuevo, capa 1, solo `re`)

- `escape_mermaid_label(name) -> str`: **movida tal cual** desde `comparar/reporters/_base.py:111`, con sus regex.
  `_base.py` la reimporta y la mantiene en `__all__`, así que `html_reporter` y `markdown_reporter` no cambian.
- `mermaid_node_id(prefix, name, used) -> str`: movida desde `markdown_reporter.py:29` (`_mermaid_node_id`).
  `markdown_reporter` importa la nueva función con el alias `_mermaid_node_id`.
- `escape_mermaid_er_text(text) -> str` (**nueva**, SPIKE_C3):
  - primero `#` → `#35;`;
  - después `%` → `#37;`, `\` → `#92;`, `"` → `#quot;`, `[` → `#91;`, `]` → `#93;`;
  - saltos de línea y caracteres de control (el mismo patrón que G46) → espacio.
- `normalize_er_type(raw) -> str` y `normalize_er_name(raw) -> tuple[str, bool]` (**nuevas**):
  - `[^\w\-()\[\]]` → `_` en los tipos y `[^\w]` → `_` en los nombres, con Unicode permitido;
  - prefijo `t_`/`c_` si no empiezan por letra;
  - `PK`/`FK`/`UK`, sin distinguir mayúsculas, llevan sufijo `_`;
  - vacío → `t_`/`c_`;
  - `normalize_er_name` devuelve también si el nombre se alteró, para llevar el real al comentario.

### A2 · Cardinalidad a `analysis/base.py`

Se mueven **sin cambiar el cuerpo** de `graphviz_ext.py:146-203` a `DatabaseRelationshipGraphBase`:
`_get_primary_keys`, `_get_unique_columns`, `_is_primary_key`, `_is_unique_column`, `_determine_cardinality` y
`_build_cardinality_markers`. Todos usan `self._snapshot(...)`, que ya está en la base. `GraphvizRelationshipGraphExt`
los hereda. Los tests que los sustituyen en la instancia (`test_graphviz_ext_helpers.py:89,158,191,226`) siguen
funcionando. `_get_table_columns_with_types` se queda en Graphviz: Mermaid lee `ColumnMeta` completo, porque
necesita `nullable`.

### A3 · Recorrido determinista (condición C1)

En `base.py`, `_build_level_data` (:331) y `_collect_next_level_tables` (:438) iteran `for current_table in
sorted(frontier)`. Es el mismo arreglo que G47. Con eso quedan estables el orden de `levels[].edges`,
`document.edges`, `relations` y la inserción en `nodes`; los conjuntos (`tables`, `level.tables`) no tienen orden
por naturaleza. Efecto lateral: el orden de los nodos en Graphviz, HTML y Word pasa a ser estable. Mejora; se anota
en el CHANGELOG.

### A4 · `analysis/mermaid_er.py` (nuevo, condición C2)

```python
@dataclass(frozen=True)
class MermaidErResult:
    blocks: tuple[str, ...]          # texto "erDiagram\n..." sin la fence de Markdown
    document: GraphDocument
    warnings: tuple[str, ...]        # recortes o repartos (texto en español, para el renderer)

class MermaidRelationshipGraph(DatabaseRelationshipGraphBase):
    def __init__(self, db_manager, *, column_mode="relations", max_columns=8, show_constraint_name=False,
                 max_entities=40, max_chars=50_000, schema=None): ...
    def render_er(self, table_name, *, max_depth=1, direction="both", max_subnodes=10) -> MermaidErResult: ...
```

- **No importa `graphviz`.** Tampoco hereda de `GraphvizRelationshipGraphExt`.
- Flujo:
  1. `build_graph_document`;
  2. una línea de relación por **restricción**: las FK compuestas generan hoy un `TableRelation` por columna, y se
     agrupan por `(source, target, constraint)`;
  3. orden total por `(target, source, constraint)`;
  4. reparto con `_split_relations_for_visualization(max_subnodes)`;
  5. un bloque por trozo.
- Entidades: `e1` es la tabla raíz y el resto se numera en orden alfabético. Alias con `escape_mermaid_er_text`.
  Atributos según `column_mode`:
  - `compact`: ninguno;
  - `relations`: PK y columnas de las FK dibujadas;
  - `all`: todas, hasta `max_columns`.

  Claves `PK`, `FK` y `UK` (UK solo con restricción de una columna). El tipo es `ColumnMeta.data_type`
  normalizado; si el nombre se alteró, el real va al comentario.
- Cardinalidad: `_determine_cardinality` + `_build_cardinality_markers`, para tener **paridad con Graphviz**. Marcador
  `1` → `||` (o `|o` en el lado padre si alguna columna de la FK admite nulos); `N`/`M` → `}o` en el padre y `o{` en
  el hijo. Línea `--` si las columnas de la FK están todas en la PK de la tabla hija; si no, `..`. Etiqueta: el
  nombre de la restricción si `show_constraint_name`; si no, `""`.
- Guardas: si un bloque supera `max_entities` o `max_chars`, se rehace sin columnas; si aún las supera, el trozo se
  parte en dos, recursivamente. Cada caso añade un aviso.
- Sin relaciones: `blocks=()`, sin bloque vacío.
- Export perezoso en `analysis/__init__.py` (`MermaidRelationshipGraph`, `MermaidErResult`), como los demás.

### Tests

| Fichero | Casos |
|---|---|
| `tests/unit/test_core_mermaid.py` (nuevo) | `escape_mermaid_label` reexportada (misma salida que hoy); `escape_mermaid_er_text`: `#`, `%`, `\`, `"`, corchetes, `\n`/U+2028, `%%{init}`, `#quot;` literal → `#35;quot;`; `normalize_er_type`/`name`: `double precision`, `decimal(10,2)`, `timestamp(6) with time zone`, `pk`, `FK`, `1col`, `año` (se conserva), vacío |
| `tests/comparar/test_mermaid_injection.py` (existente) | Sin cambios: debe seguir en verde (regresión G46) |
| `tests/unit/test_analysis_traversal_order.py` (nuevo) | `build_graph_document` en dos subprocesos con `PYTHONHASHSEED` distinto (patrón `test_fk_graph_cycle_order.py`) → mismas aristas y mismo orden; también `total_*_levels` |
| `tests/unit/test_analysis_cardinality_base.py` (nuevo) | La cardinalidad funciona en una instancia de la base, sin `graphviz` (`1:N`, `1:1`, `M:N`, `N:1`) |
| `tests/unit/test_graphviz_ext_*` (existentes) | Sin cambios: regresión del movimiento |
| `tests/unit/test_analysis_mermaid_er.py` (nuevo) | Fuente simulada: 1:N; FK nullable → `\|o`; identificante `--` y no identificante `..`; FK compuesta → una línea; FK reflexiva; dos FK al mismo par; los tres `column_mode`; reparto por `max_subnodes`; guarda de entidades (sin columnas y luego partida) con avisos; nombres hostiles (`%`, `\`, `"`, `PK`); sin relaciones → `blocks=()`; sin `graphviz` (`sys.modules["graphviz"] = None` en subproceso); salida idéntica en dos subprocesos |
| e2e SQLite | 3 tablas con FK en `:memory:` con `SyncDatabaseManager`, a través de `MermaidRelationshipGraph` |

Comandos de cierre: `ruff check`/`format`, `mypy src tests/unit/test_protocol_conformance.py`, `pytest` y
`python scripts/gen_arquitectura_capas.py`. No hay imports nuevos entre paquetes: `analysis → _core` y
`comparar → _core` ya existen.

## AUDIT_PLAN

**Riesgos funcionales**

- **Paridad heredada discutible.** `N:1` (FK que apunta a una columna que no es PK) produce `target_marker="N"`
  (`graphviz_ext.py:202`), es decir, una «N» en el lado padre. En Mermaid sería `}o..o|`. Se mantiene la paridad y
  se registra como deuda junto a F3 (`M:N` con dos PK). No se corrige aquí.
- **FK compuestas.** Mermaid dibuja una sola línea por restricción y Graphviz una por columna. Es una diferencia
  visual deliberada.

**Riesgos técnicos**

- **LSP.** `MermaidRelationshipGraph` es una subclase más de la base, al lado de Matplotlib. Los métodos movidos
  conservan firma y comportamiento, y los subtipos que los sobrescriben (tests) siguen funcionando.
- **ISP.** La base gana 6 métodos privados de lectura. Es aceptable: son consultas al snapshot que ya usaba.
- **Cambio de orden.** El orden estable cambia la colocación de nodos en Graphviz respecto de 5.2.0. No es un
  contrato, pero un usuario podría notarlo; va al CHANGELOG.
- **Memoria y tiempo.** Ningún coste nuevo: un `sorted()` por nivel y lecturas al snapshot ya cacheado.

**Riesgos de seguridad**

- La inyección en Mermaid queda cubierta por `escape_mermaid_er_text`, validado en SPIKE_C3.
- `escape_mermaid_label` no cambia: G46 sigue igual.
- Sin E/S: el módulo solo devuelve texto.

**Simplificaciones**

- `MermaidErResult.document` podría omitirse, pero el renderer del grupo B lo necesita para el resumen de niveles
  (`diagram_summary.py`), así que se mantiene.
- No se crea una clase `MermaidOptions`: bastan los kwargs, como en Graphviz.

**Veredicto: `GO`.** No hay condiciones abiertas para este grupo: C1 y C2 son su propio contenido, y C3 ya está
cumplida.
