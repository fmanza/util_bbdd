"""Diagramas entidad-relación en Mermaid (``erDiagram``) a partir del grafo de relaciones, sin Graphviz.

Texto listo para un bloque ```` ```mermaid ```` de Markdown (Zensical/MkDocs, GitHub, la web). Comparte con
:class:`~util_bbdd.analysis.graphviz_ext.GraphvizRelationshipGraphExt` el recorrido por niveles y la cardinalidad
(``DatabaseRelationshipGraphBase``), pero no importa ``graphviz``: funciona sin el extra ``analysis``.

Gramática y límites validados con Mermaid 11.17.2 y 12.2.0 (sesión ``2026-11-05-doc-markdown``, ``SPIKE_C3.md``); el
orden ``nombre tipo`` de los atributos, con 11.17.2 y 12.3.0 (sesión ``2026-11-13c-mermaid-nombre-tipo``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from .._core.mermaid import escape_mermaid_er_text, normalize_er_name, normalize_er_type
from ..metadata.model import ColumnMeta, Kind, SchemaSnapshot
from .base import (
    ColumnVisualizationMode,
    DatabaseRelationshipGraphBase,
    GraphDocument,
    LevelDirection,
    TableRelation,
)
from .contracts import RelationshipGraphSource

_KINDS: frozenset[Kind] = frozenset({Kind.COLUMNS, Kind.FOREIGN_KEYS, Kind.PRIMARY_KEYS, Kind.UNIQUES})

#: Orden de cada atributo de ``erDiagram``: ``name_type`` (nombre y después tipo, como Graphviz) o ``type_name``
#: (la forma canónica de Mermaid, la de hasta 5.7.0). Mermaid dibuja las columnas en el orden del texto.
AttributeOrder = Literal["name_type", "type_name"]
_ATTRIBUTE_ORDERS: frozenset[str] = frozenset({"name_type", "type_name"})


@dataclass(frozen=True)
class MermaidErResult:
    """Diagramas ER de una tabla.

    Attributes:
        blocks: Un texto ``erDiagram`` por diagrama, sin la *fence* de Markdown; vacío si la tabla no tiene relaciones.
            Hay varios cuando las relaciones superan ``max_subnodes`` o los límites de tamaño.
        document: Grafo del que salen (niveles visibles y ocultos para el resumen bajo el diagrama).
        warnings: Avisos para el lector (diagrama sin columnas o partido por tamaño), sin repetir.
    """

    blocks: tuple[str, ...]
    document: GraphDocument
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ErRelation:
    """Una FK dibujada: una línea por restricción aunque tenga varias columnas."""

    parent: str
    child: str
    constraint: str
    child_columns: tuple[str, ...]
    parent_columns: tuple[str, ...]


class MermaidRelationshipGraph(DatabaseRelationshipGraphBase):
    """Genera diagramas ``erDiagram`` de Mermaid de una tabla y sus relaciones.

    El resultado es determinista: mismas entidades, atributos y relaciones en el mismo orden en cualquier proceso.

    - Una línea por FK (restricción), con la cardinalidad de Graphviz: ``1:N`` → ``||--o{`` y ``1:1`` (las columnas
      de la FK son la PK o una ``UNIQUE`` de la hija) → ``||--o|``; el lado padre es opcional (``|o``) si alguna
      columna de la FK admite nulos.
    - Línea continua (``--``, identificante) si las columnas de la FK forman parte de la PK de la tabla hija; si no,
      discontinua (``..``).
    - Nombres y comentarios del catálogo escapados con códigos de entidad de Mermaid; tipos y nombres de columna
      normalizados a la gramática de ``erDiagram`` (el nombre real va al comentario si cambia).
    - Cada columna, como ``nombre tipo [PK, FK, UK] ["nombre real"]`` (desde 5.8.0; ``attribute_order``): Mermaid no
      reordena las columnas del dibujo y así salen como en Graphviz, el nombre primero.

    Args:
        db_manager: Fuente de metadatos por lotes (``RelationshipGraphSource``), p. ej. un ``SyncDatabaseManager``.
        show_columns: Columnas dentro de las entidades (``grafo.show_columns``); ``False``, solo los nombres de tabla.
        column_mode: Qué columnas, como en Graphviz: ``relations`` (las de las relaciones dibujadas), ``compact`` (esas
            primero y después las demás hasta ``max_columns``) o ``all`` (todas, en su orden).
        max_columns: Columnas por entidad como máximo (``relations`` y ``all``).
        show_constraint_name: Etiqueta de cada relación con el nombre de la FK; si no, sin etiqueta.
        max_entities: Entidades por diagrama como máximo; por encima, se parte (el dibujo de 300 entidades tarda entre
            12 y 28 s en el navegador).
        max_chars: Caracteres por diagrama como máximo (``maxTextSize`` de Mermaid: 50 000); por encima, primero se
            quitan las columnas y después se parte.
        schema: Schema que se dibuja; por defecto, el contexto de metadatos de ``db_manager``.
        attribute_order: ``name_type`` (por defecto desde 5.8.0: nombre y después tipo) o ``type_name`` (tipo y
            después nombre, la forma canónica de ``erDiagram`` y la salida hasta 5.7.0).

    Raises:
        ValueError: ``column_mode`` o ``attribute_order`` no soportados.

    Examples:
        >>> with SyncDatabaseManager("sqlite", {"database": "ventas.db"}) as manager:
        ...     result = MermaidRelationshipGraph(manager).render_er("pedidos")
        >>> print(result.blocks[0])
        erDiagram
            e1["pedidos"] {
            ...
    """

    _ATTRIBUTE_INDENT: ClassVar[str] = "        "
    _LINE_INDENT: ClassVar[str] = "    "

    def __init__(
        self,
        db_manager: RelationshipGraphSource,
        *,
        show_columns: bool = True,
        column_mode: ColumnVisualizationMode | str = ColumnVisualizationMode.RELATIONS,
        max_columns: int = 8,
        show_constraint_name: bool = False,
        max_entities: int = 40,
        max_chars: int = 50_000,
        schema: str | None = None,
        attribute_order: AttributeOrder = "name_type",
    ) -> None:
        super().__init__(db_manager, schema=schema)
        self.show_columns: bool = bool(show_columns)
        try:
            self.column_mode = ColumnVisualizationMode(str(column_mode).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Modo de columnas no soportado: {column_mode}") from exc
        self.max_columns: int = max(1, int(max_columns))
        self.show_constraint_name: bool = bool(show_constraint_name)
        self.max_entities: int = max(2, int(max_entities))
        self.max_chars: int = max(1, int(max_chars))
        if attribute_order not in _ATTRIBUTE_ORDERS:
            raise ValueError(f"Orden de atributos no soportado: {attribute_order} (name_type o type_name)")
        self.attribute_order: AttributeOrder = attribute_order

    def render_er(
        self,
        table_name: str,
        *,
        max_depth: int = 1,
        direction: LevelDirection | str = LevelDirection.BOTH,
        max_subnodes: int = 10,
    ) -> MermaidErResult:
        """Diagramas ER de ``table_name`` con sus relaciones hasta ``max_depth`` niveles.

        Args:
            table_name: Tabla central.
            max_depth: Niveles en cada sentido (mínimo 1); los demás cuentan como ocultos en ``document``.
            direction: ``outgoing`` (tablas a las que apunta), ``incoming`` (las que apuntan a ella) o ``both``.
            max_subnodes: Relaciones por diagrama; si hay más, se reparten en varios (como las imágenes de Word).

        Returns:
            Los diagramas, el grafo y los avisos.

        Raises:
            ValueError: ``direction`` no válida.
        """
        document = self.build_graph_document(table_name=table_name, max_depth=max_depth, direction=direction)
        relations = self._group_relations(document.relations)
        if not relations:
            return MermaidErResult(blocks=(), document=document, warnings=())
        snapshot = self._snapshot(set(_KINDS))
        blocks: list[str] = []
        warnings: list[str] = []
        for chunk in self._split_relations_for_visualization(relations, max(1, int(max_subnodes))):
            self._emit_guarded(snapshot, document.root_table, chunk, blocks, warnings)
        return MermaidErResult(blocks=tuple(blocks), document=document, warnings=tuple(dict.fromkeys(warnings)))

    # --- Relaciones ---

    @staticmethod
    def _group_relations(relations: list[TableRelation]) -> list[_ErRelation]:
        """Una relación por FK (las compuestas llegan como una ``TableRelation`` por columna), en orden estable.

        Las FK sin nombre (SQLite) no se agrupan: dos FK distintas entre las mismas tablas se fundirían en una (y la
        nulabilidad de una pasaría a la otra); una FK compuesta sin nombre sale como una línea por columna.
        """
        grouped: dict[tuple[str, str, str, str], list[TableRelation]] = {}
        for relation in relations:
            discriminator = "" if relation.constraint_name else relation.source_column
            key = (relation.target_table, relation.source_table, relation.constraint_name, discriminator)
            grouped.setdefault(key, []).append(relation)
        return [
            _ErRelation(
                parent=parent,
                child=child,
                constraint=constraint,
                child_columns=tuple(r.source_column for r in rows),
                parent_columns=tuple(r.target_column for r in rows),
            )
            for (parent, child, constraint, _), rows in sorted(grouped.items())
        ]

    def _relation_line(self, snapshot: SchemaSnapshot, relation: _ErRelation, ids: dict[str, str]) -> str:
        """``eP ||--o{ eH : "etiqueta"`` con cardinalidad, opcionalidad e identificación."""
        markers = self._build_cardinality_markers(
            self._determine_cardinality(
                relation.child_columns[0], relation.parent_columns[0], relation.child, relation.parent
            )
        )
        nullable = {c.name.lower() for c in snapshot.columns(relation.child) if c.nullable}
        optional = any(column.lower() in nullable for column in relation.child_columns)
        if markers.target_marker != "1":
            parent_end = "}o"
        else:
            parent_end = "|o" if optional else "||"
        child_end = "o{" if markers.source_marker != "1" else "o|"
        child_pk = self._get_primary_keys(relation.child)
        identifying = bool(child_pk) and all(column.lower() in child_pk for column in relation.child_columns)
        line = "--" if identifying else ".."
        label = escape_mermaid_er_text(relation.constraint) if self.show_constraint_name else ""
        return (
            f'{self._LINE_INDENT}{ids[relation.parent]} {parent_end}{line}{child_end} {ids[relation.child]} : "{label}"'
        )

    # --- Bloques y límites de tamaño ---

    def _emit_guarded(
        self,
        snapshot: SchemaSnapshot,
        root: str,
        chunk: list[_ErRelation],
        blocks: list[str],
        warnings: list[str],
    ) -> None:
        """Añade el bloque del trozo; si excede los límites, lo rehace sin columnas o lo parte en dos."""
        tables = self._chunk_tables(root, chunk)
        with_columns = self.show_columns
        text = self._block(snapshot, tables, chunk, with_columns)
        if len(tables) <= self.max_entities and len(text) <= self.max_chars:
            blocks.append(text)
            return
        if len(tables) <= self.max_entities and with_columns:
            text = self._block(snapshot, tables, chunk, with_columns=False)
            if len(text) <= self.max_chars:
                warnings.append(f"Diagrama sin columnas: con ellas superaba {self.max_chars} caracteres.")
                blocks.append(text)
                return
        if len(chunk) <= 1:
            blocks.append(text)  # una sola relación (dos entidades): no se puede partir más
            return
        warnings.append(f"Diagrama partido: superaba {self.max_entities} entidades o {self.max_chars} caracteres.")
        middle = len(chunk) // 2
        self._emit_guarded(snapshot, root, chunk[:middle], blocks, warnings)
        self._emit_guarded(snapshot, root, chunk[middle:], blocks, warnings)

    @staticmethod
    def _chunk_tables(root: str, chunk: list[_ErRelation]) -> list[str]:
        """La tabla central primero; el resto, en orden alfabético."""
        others = {table for relation in chunk for table in (relation.parent, relation.child)} - {root}
        return [root, *sorted(others, key=lambda name: (name.casefold(), name))]

    def _block(self, snapshot: SchemaSnapshot, tables: list[str], chunk: list[_ErRelation], with_columns: bool) -> str:
        ids = {table: f"e{index}" for index, table in enumerate(tables, start=1)}
        lines = ["erDiagram"]
        for table in tables:
            alias = f'{self._LINE_INDENT}{ids[table]}["{escape_mermaid_er_text(table)}"]'
            attributes = self._attributes(snapshot, table, chunk) if with_columns else []
            if attributes:
                lines += [f"{alias} {{", *attributes, f"{self._LINE_INDENT}}}"]
            else:
                lines.append(alias)
        lines += [self._relation_line(snapshot, relation, ids) for relation in chunk]
        return "\n".join(lines)

    # --- Atributos ---

    def _attributes(self, snapshot: SchemaSnapshot, table: str, chunk: list[_ErRelation]) -> list[str]:
        """Líneas de atributo de la entidad según ``column_mode``, en el orden de las columnas de la tabla."""
        columns = list(snapshot.columns(table))
        pk = set(self._get_primary_keys(table))
        # Misma política que Graphviz (``_select_columns_for_table``): relations = solo las de las relaciones dibujadas;
        # compact = esas primero y después las demás hasta ``max_columns``; all = todas en su orden
        drawn = {c.lower() for r in chunk if r.child == table for c in r.child_columns}
        drawn |= {c.lower() for r in chunk if r.parent == table for c in r.parent_columns}
        related = [c for c in columns if c.name.lower() in drawn]
        if self.column_mode == ColumnVisualizationMode.RELATIONS:
            columns = related
        elif self.column_mode == ColumnVisualizationMode.COMPACT:
            columns = related + [c for c in columns if c.name.lower() not in drawn]
        fk_columns = {c.lower() for fk in snapshot.foreign_keys(table) for c in fk.columns}
        uk_columns = set(self._get_unique_columns(table))
        return [self._attribute(c, pk, fk_columns, uk_columns) for c in columns[: self.max_columns]]

    def _attribute(self, column: ColumnMeta, pk: set[str], fk: set[str], uk: set[str]) -> str:
        """``nombre tipo PK, FK "nombre real"`` (o ``tipo nombre …`` con ``attribute_order="type_name"``)."""
        name, altered = normalize_er_name(column.name)
        lowered = column.name.lower()
        keys = [key for key, members in (("PK", pk), ("FK", fk), ("UK", uk)) if lowered in members]
        data_type = normalize_er_type(column.data_type or "unknown")
        parts = [name, data_type] if self.attribute_order == "name_type" else [data_type, name]
        if keys:
            parts.append(", ".join(keys))
        if altered:
            parts.append(f'"{escape_mermaid_er_text(column.name)}"')
        return f"{self._ATTRIBUTE_INDENT}{' '.join(parts)}"


__all__: list[str] = ["AttributeOrder", "MermaidErResult", "MermaidRelationshipGraph"]
