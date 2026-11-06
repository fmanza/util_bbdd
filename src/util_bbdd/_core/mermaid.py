"""Texto seguro para diagramas Mermaid: labels de flowchart, ids de nodo y textos de ``erDiagram``.

Punto común de ``comparar`` (flowchart del informe de diferencias) y ``analysis`` (diagramas entidad-relación). Los
nombres y comentarios del catálogo son datos no confiables: un salto de línea, una directiva ``%%{init}`` o una comilla
añadirían sentencias al diagrama o lo romperían (G46 de util_bbdd_web).

Las reglas de ``erDiagram`` salen de la prueba con Mermaid 11.17.2 y 12.2.0 (sesión ``2026-11-05-doc-markdown``,
``SPIKE_C3.md``): un ``%`` o ``\\`` sueltos en el alias de una entidad rompen el diagrama, los tipos con espacios
también, y ``PK``, ``FK`` y ``UK`` no se admiten como tipo ni como nombre de atributo. Los códigos de entidad de Mermaid
(``#37;``…) se muestran como el carácter original, así que el texto no se altera.
"""

from __future__ import annotations

import re

# Saltos de línea y caracteres de control (C0, DEL, C1), más los separadores de línea y párrafo de Unicode, que el
# parser de Mermaid (JavaScript) también trata como fin de línea.
_LINE_BREAKS: re.Pattern[str] = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_DIRECTIVE: re.Pattern[str] = re.compile(r"%(?=%)")
_NON_ID_CHARS: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_]")

# erDiagram: el orden importa, «#» primero para no recodificar las entidades que se generan después
_ER_ENTITIES: tuple[tuple[str, str], ...] = (
    ("#", "#35;"),
    ("%", "#37;"),
    ("\\", "#92;"),
    ('"', "#quot;"),
    ("[", "#91;"),
    ("]", "#93;"),
)
_ER_TYPE_BAD: re.Pattern[str] = re.compile(r"[^\w\-()\[\]]")
_ER_NAME_BAD: re.Pattern[str] = re.compile(r"[^\w]")
_ER_RESERVED: frozenset[str] = frozenset({"PK", "FK", "UK"})


def escape_mermaid_label(name: str) -> str:
    """Escapa un nombre para usarlo como label en un diagrama Mermaid (flowchart).

    Las comillas y los corchetes cerrarían el label. G46 de util_bbdd_web (U-10.3): los saltos de línea y caracteres de
    control pasan a espacio, porque añadían sentencias o directivas (``%%{init: …}%%``) al diagrama, y ``%%`` se
    neutraliza (``% %``) porque Mermaid busca las directivas en cualquier parte del texto.

    No sirve para ``erDiagram``, donde un ``%`` suelto rompe el alias: ahí, :func:`escape_mermaid_er_text`.

    Examples:
        >>> escape_mermaid_label('a "b" [c]')
        "a 'b' (c)"
    """
    escaped = name.replace('"', "'").replace("[", "(").replace("]", ")")
    return _DIRECTIVE.sub("% ", _LINE_BREAKS.sub(" ", escaped))


def mermaid_node_id(prefix: str, name: str, used: set[str]) -> str:
    """Id de nodo Mermaid: ``prefix_nombre`` con solo ``[A-Za-z0-9_]`` (el resto, ``_``).

    G46 de util_bbdd_web (U-10.3): el id se construía con el escape del label y un nombre con saltos de línea o ``-->``
    añadía sentencias al diagrama. Si dos nombres dan el mismo id, el segundo lleva un sufijo (``_2``, ``_3``…); ``used``
    acumula los ids del diagrama.

    Examples:
        >>> used: set[str] = set()
        >>> mermaid_node_id("A", "ventas.pedidos", used), mermaid_node_id("A", "ventas-pedidos", used)
        ('A_ventas_pedidos', 'A_ventas_pedidos_2')
    """
    base = f"{prefix}_{_NON_ID_CHARS.sub('_', name)}"
    node_id = base
    suffix = 2
    while node_id in used:
        node_id = f"{base}_{suffix}"
        suffix += 1
    used.add(node_id)
    return node_id


def escape_mermaid_er_text(text: str) -> str:
    """Escapa texto libre para un ``erDiagram``: alias de entidad, comentario de atributo o etiqueta de relación.

    Usa los códigos de entidad de Mermaid, que se muestran como el carácter original: ``#``, ``%``, ``\\``, ``"``, ``[`` y
    ``]`` pasan a ``#35;``, ``#37;``, ``#92;``, ``#quot;``, ``#91;`` y ``#93;``. Una directiva ``%%{init}`` queda como
    texto y no se aplica. Los saltos de línea y caracteres de control pasan a espacio.

    Examples:
        >>> escape_mermaid_er_text('50% "neto"')
        '50#37; #quot;neto#quot;'
    """
    escaped = _LINE_BREAKS.sub(" ", text)
    for char, entity in _ER_ENTITIES:
        escaped = escaped.replace(char, entity)
    return escaped


def normalize_er_type(raw: str) -> str:
    """Tipo de columna válido como tipo de atributo de ``erDiagram``.

    Admite letras (también Unicode), dígitos, ``_``, ``-``, paréntesis y corchetes; el resto, espacios y comas incluidos,
    pasa a ``_``. Si no empieza por letra, lleva el prefijo ``t_``; ``PK``, ``FK`` y ``UK`` (sin distinguir mayúsculas),
    el sufijo ``_``.

    Examples:
        >>> normalize_er_type("double precision"), normalize_er_type("decimal(10,2)"), normalize_er_type("varchar(255)")
        ('double_precision', 'decimal(10_2)', 'varchar(255)')
    """
    return _normalize_er_token(raw, _ER_TYPE_BAD, "t_")


def normalize_er_name(raw: str) -> tuple[str, bool]:
    """Nombre de columna válido como nombre de atributo de ``erDiagram`` y si hubo que cambiarlo.

    Admite letras (también Unicode), dígitos y ``_``; el resto pasa a ``_``. Si no empieza por letra, lleva el prefijo
    ``c_``; ``PK``, ``FK`` y ``UK`` (sin distinguir mayúsculas), el sufijo ``_``. Si cambia, quien llama pone el nombre
    real en el comentario del atributo.

    Examples:
        >>> normalize_er_name("año"), normalize_er_name("mi col"), normalize_er_name("pk")
        (('año', False), ('mi_col', True), ('pk_', True))
    """
    normalized = _normalize_er_token(raw, _ER_NAME_BAD, "c_")
    return normalized, normalized != raw


def _normalize_er_token(raw: str, bad: re.Pattern[str], prefix: str) -> str:
    token = bad.sub("_", raw.strip())
    if not token[:1].isalpha():
        token = f"{prefix}{token}"
    if token.upper() in _ER_RESERVED:
        token = f"{token}_"
    return token


__all__: list[str] = [
    "escape_mermaid_er_text",
    "escape_mermaid_label",
    "mermaid_node_id",
    "normalize_er_name",
    "normalize_er_type",
]
