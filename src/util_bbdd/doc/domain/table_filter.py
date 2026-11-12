"""Filtro de tablas y vistas de la documentación por patrones, con su frontera (``imprimir["filtro"]``, 5.5.0).

Los patrones son *glob* (:func:`fnmatch.fnmatchcase`): ``*`` cualquier texto, ``?`` un carácter y ``[ABC]`` uno de
esos caracteres. No distinguen mayúsculas (Oracle guarda los nombres en mayúsculas y PostgreSQL en minúsculas).

- ``incluir``: solo se documentan los objetos que casan con algún patrón (vacío = todos).
- ``excluir``: se quitan los que casan con algún patrón, aunque casen con ``incluir``.
- ``frontera``: tablas que no se documentan, unidas por una FK (en cualquier sentido) a alguna documentada y que no
  están excluidas expresamente. Se listan, sin ficha propia.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, ClassVar

#: Clave de ``imprimir`` y sus subclaves
FILTER_KEY = "filtro"


@dataclass(frozen=True, slots=True)
class TableFilter:
    """Patrones de inclusión y exclusión de tablas y vistas.

    Attributes:
        include: Patrones de ``incluir`` (vacío = todos los objetos).
        exclude: Patrones de ``excluir``.
        frontier: Calcular la frontera (tablas vecinas por FK que quedan fuera).

    Example:
        >>> f = TableFilter.from_config({"incluir": ["MVG_*"], "excluir": ["*_BAK"]})
        >>> f.matches("mvg_pedido"), f.matches("MVG_PEDIDO_BAK"), f.matches("COB_LINEA")
        (True, False, False)
    """

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    frontier: bool = True

    MAX_PATTERNS: ClassVar[int] = 100
    MAX_PATTERN_LENGTH: ClassVar[int] = 128

    @classmethod
    def from_config(cls, value: Any) -> TableFilter | None:
        """Filtro de ``imprimir["filtro"]``; ``None`` si no hay ningún patrón.

        Acepta ``{"incluir": [...], "excluir": [...], "frontera": bool}``; cada lista puede ser también un solo patrón
        en una cadena.

        Raises:
            ValueError: ``filtro`` no es un diccionario, o un patrón no es una cadena, está vacío, tiene caracteres de
                control o supera :attr:`MAX_PATTERN_LENGTH`, o hay más de :attr:`MAX_PATTERNS` en una lista.
        """
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(f"{FILTER_KEY} debe ser un diccionario con incluir/excluir")
        include = cls._patterns(value.get("incluir"), "incluir")
        exclude = cls._patterns(value.get("excluir"), "excluir")
        if not include and not exclude:
            return None
        return cls(include, exclude, bool(value.get("frontera", True)))

    @classmethod
    def _patterns(cls, value: Any, key: str) -> tuple[str, ...]:
        if value is None:
            return ()
        items = [value] if isinstance(value, str) else value
        if not isinstance(items, (list, tuple)):
            raise ValueError(f"{FILTER_KEY}.{key} debe ser una lista de patrones")
        if len(items) > cls.MAX_PATTERNS:
            raise ValueError(f"{FILTER_KEY}.{key}: como máximo {cls.MAX_PATTERNS} patrones")
        patterns: list[str] = []
        for item in items:
            if not isinstance(item, str):
                raise ValueError(f"{FILTER_KEY}.{key}: cada patrón debe ser una cadena, recibido {item!r}")
            pattern = item.strip()
            if not pattern or len(pattern) > cls.MAX_PATTERN_LENGTH or not pattern.isprintable():
                raise ValueError(
                    f"{FILTER_KEY}.{key}: patrón vacío, con caracteres de control o de más de "
                    f"{cls.MAX_PATTERN_LENGTH} caracteres: {item!r}"
                )
            if pattern not in patterns:
                patterns.append(pattern)
        return tuple(patterns)

    @classmethod
    def from_catalog(cls, value: Any) -> TableFilter | None:
        """Filtro guardado en ``catalog.json`` (``filter``: ``include``/``exclude``); ``None`` si no lo hay o no vale."""
        if not isinstance(value, dict):
            return None
        try:
            return cls.from_config({"incluir": value.get("include"), "excluir": value.get("exclude")})
        except ValueError:
            return None

    def to_config(self) -> dict[str, Any]:
        """Forma normalizada de ``imprimir["filtro"]`` (idempotente con :meth:`from_config`)."""
        return {"incluir": list(self.include), "excluir": list(self.exclude), "frontera": self.frontier}

    def to_catalog(self) -> dict[str, list[str]]:
        """``filter`` de ``catalog.json`` y ``manifest.json``."""
        return {"include": list(self.include), "exclude": list(self.exclude)}

    @staticmethod
    def _any(name: str, patterns: tuple[str, ...]) -> bool:
        folded = name.casefold()
        return any(fnmatchcase(folded, pattern.casefold()) for pattern in patterns)

    def excluded(self, name: str) -> bool:
        """El objeto casa con algún patrón de ``excluir``."""
        return self._any(name, self.exclude)

    def matches(self, name: str) -> bool:
        """El objeto se documenta: casa con ``incluir`` (o no hay) y con ningún patrón de ``excluir``."""
        return (not self.include or self._any(name, self.include)) and not self.excluded(name)

    def frontier_of(self, selected: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str]:
        """Tablas de la frontera: vecinas por FK de las de ``selected`` que no están en ella ni excluidas.

        Args:
            selected: Tablas documentadas.
            edges: ``(tabla con la FK, tabla referenciada)`` de todas las FK del schema.

        Returns:
            Nombres tal como vienen en ``edges``, sin repetir (sin distinguir mayúsculas), ordenados.
        """
        chosen = {name.casefold() for name in selected}
        found: dict[str, str] = {}
        for child, parent in edges:
            for inside, other in ((child, parent), (parent, child)):
                key = other.casefold()
                if inside.casefold() in chosen and key not in chosen and not self.excluded(other):
                    found.setdefault(key, other)
        return sorted(found.values(), key=str.casefold)


__all__: list[str] = ["FILTER_KEY", "TableFilter"]
