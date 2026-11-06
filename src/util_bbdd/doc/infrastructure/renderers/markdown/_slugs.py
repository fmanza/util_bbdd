"""Nombres de fichero y anclas estables para la documentación Markdown.

El slug de un objeto no depende del orden ni de qué otros objetos haya, salvo colisión: si varios nombres dan el mismo
slug (``Foo`` y ``FOO`` en Oracle o PostgreSQL entrecomillados, sobrecargas de rutinas), **todos** los del grupo
llevan un sufijo con el hash de su nombre exacto. A diferencia del ``-2`` del HTML, ese sufijo no cambia al reordenar.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from collections.abc import Iterable

from ....._core.filenames import safe_file_stem

_MAX_STEM: int = 80
# Nombres de dispositivo de Windows (también con extensión: «con.md» no se puede crear) e índices propios
_RESERVED: re.Pattern[str] = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9]|index(-.*)?)$")


def _hash_suffix(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def unique_slugs(names: Iterable[str]) -> dict[str, str]:
    """Slug único y estable por nombre: ``safe_file_stem`` truncado, con hash si colisiona o es reservado.

    Examples:
        >>> slugs = unique_slugs(["Clientes", "clientes", "pedidos", "CON"])
        >>> slugs["pedidos"], slugs["Clientes"] != slugs["clientes"], slugs["CON"].startswith("con-")
        ('pedidos', True, True)
    """
    unique_names = sorted(set(names))
    stems = {name: safe_file_stem(name)[:_MAX_STEM].rstrip("-") or "item" for name in unique_names}
    counts: dict[str, int] = {}
    for stem in stems.values():
        counts[stem] = counts.get(stem, 0) + 1
    return {
        name: f"{stem}-{_hash_suffix(name)}" if counts[stem] > 1 or _RESERVED.match(stem) else stem
        for name, stem in stems.items()
    }


def index_letter(name: str) -> str:
    """Letra del índice de un nombre: ``a``–``z`` sin tildes, ``0-9`` o ``otros``."""
    first = unicodedata.normalize("NFKD", name.strip()[:1]).encode("ascii", "ignore").decode("ascii").lower()[:1]
    if "a" <= first <= "z":
        return first
    if first.isdigit():
        return "0-9"
    return "otros"


def sort_key(name: str) -> tuple[str, str]:
    """Orden de los objetos en índices y páginas: sin distinguir mayúsculas y, a igualdad, el nombre exacto (D1)."""
    return name.casefold(), name


__all__: list[str] = ["index_letter", "sort_key", "unique_slugs"]
