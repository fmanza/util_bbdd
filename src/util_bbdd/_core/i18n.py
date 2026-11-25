"""Idioma de los resultados: textos visibles y separadores numéricos de informes y documentación (5.10.0).

Los catálogos viven en ``util_bbdd/data/i18n/<locale>/<módulo>.json``: un fichero por módulo dueño de sus textos (``doc``,
``comparar``, ``dump``, ``audit``, ``analysis``) con claves planas, y ``_format.json`` con los separadores numéricos. La
clave completa es ``<módulo>.<clave>`` (``"dump.sheet.pk_sync"``). Solo afecta a lo que lee una persona: los datos para
máquinas (``catalog.json``, front matter, JSON de auditoría, rutas) y las excepciones y logs no se traducen.

Las fechas no dependen del idioma: los informes usan ISO 8601 (``2026-11-25 14:30:00``), que se lee igual en todos y no
tiene la ambigüedad de ``11/12/2026``. Los números sí: ``format_int`` y ``format_decimal`` aplican los separadores del
catálogo, sin ``locale.setlocale`` (estado global del proceso, inseguro con hilos y dependiente del sistema operativo).
"""

from __future__ import annotations

import json

from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, cast, get_args

Locale = Literal["es", "en"]
"""Idiomas de salida soportados."""

SUPPORTED_LOCALES: Final[tuple[Locale, ...]] = cast(tuple[Locale, ...], get_args(Locale))
DEFAULT_LOCALE: Final[Locale] = "es"
#: Catálogos empaquetados (``package-data``); ruta junto al módulo, como el resto de datos de la librería (sin
#: ``importlib.resources``, que falla si el paquete raíz aún se está importando).
CATALOG_ROOT: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "i18n"
_FORMAT_NAMESPACE: Final[str] = "_format"


def validate_locale(value: object) -> Locale:
    """Devuelve ``value`` si es un idioma soportado; si no, lanza ``ValueError`` (antes de leer ningún catálogo).

    Args:
        value: Idioma pedido por quien llama.

    Returns:
        El mismo valor, con el tipo ``Locale``.

    Raises:
        ValueError: Si no está en ``SUPPORTED_LOCALES``.

    Example:
        >>> validate_locale("en")
        'en'
    """
    if not isinstance(value, str) or value not in SUPPORTED_LOCALES:
        raise ValueError(f"Idioma no soportado: {value!r}. Valores válidos: {', '.join(SUPPORTED_LOCALES)}")
    return value


@cache
def _load_catalog(locale: Locale) -> Mapping[str, str]:
    """Une los catálogos ``<módulo>.json`` de un idioma en un mapa inmutable ``<módulo>.<clave> → texto``."""
    merged: dict[str, str] = {}
    for entry in sorted((CATALOG_ROOT / locale).glob("*.json")):
        namespace = entry.stem
        messages: dict[str, str] = json.loads(entry.read_text(encoding="utf-8"))
        merged.update({f"{namespace}.{key}": str(text) for key, text in messages.items()})
    return MappingProxyType(merged)


class Translator:
    """Textos y números de un idioma de salida.

    Inmutable y sin estado compartido: dos instancias de idiomas distintos pueden usarse a la vez en hilos distintos.
    Una clave que falte en el idioma pedido se toma del español (``DEFAULT_LOCALE``); si falta también ahí, es un error
    de programación (``KeyError``). Los tests de paridad garantizan que ``es`` y ``en`` tienen las mismas claves.

    Attributes:
        locale: Idioma de salida.

    Example:
        >>> tr = Translator("en")
        >>> tr.format_int(1234567)
        '1,234,567'
        >>> Translator("es").format_decimal(1.5, 2)
        '1,50'
    """

    def __init__(self, locale: Locale = DEFAULT_LOCALE) -> None:
        self.locale: Final[Locale] = validate_locale(locale)
        self._messages: Mapping[str, str] = _load_catalog(self.locale)
        self._fallback: Mapping[str, str] = _load_catalog(DEFAULT_LOCALE)
        self._decimal_sep: Final[str] = self._message(f"{_FORMAT_NAMESPACE}.decimal_sep")
        self._thousands_sep: Final[str] = self._message(f"{_FORMAT_NAMESPACE}.thousands_sep")

    def _message(self, key: str) -> str:
        text = self._messages.get(key)
        if text is None:
            text = self._fallback.get(key)
        if text is None:
            raise KeyError(f"Clave de traducción inexistente: {key}")
        return text

    def t(self, key: str, /, **params: object) -> str:
        """Texto de ``key`` en el idioma de salida, con ``{nombre}`` sustituidos por ``params``.

        Args:
            key: Clave completa ``<módulo>.<clave>``.
            **params: Valores de los marcadores del texto.

        Returns:
            Texto traducido.

        Raises:
            KeyError: Si la clave no existe en ningún catálogo o falta un marcador.
        """
        text = self._message(key)
        return text.format_map(params) if params else text

    def format_int(self, value: int, *, grouping: bool = True) -> str:
        """Entero con el separador de miles del idioma (``1.234.567`` en ``es``, ``1,234,567`` en ``en``).

        Raises:
            TypeError: Si ``value`` no es un ``int`` (``bool`` incluido).
        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"format_int espera un int, no {type(value).__name__}")
        return self._localize(f"{value:,d}" if grouping else f"{value:d}")

    def format_decimal(self, value: float | Decimal | int, digits: int, *, grouping: bool = False) -> str:
        """Número con ``digits`` decimales y los separadores del idioma (``1,50`` en ``es``, ``1.50`` en ``en``).

        Args:
            value: Número a formatear.
            digits: Número de decimales (``>= 0``).
            grouping: Si ``True``, agrupa también los miles.

        Raises:
            TypeError: Si ``value`` no es numérico (``bool`` incluido).
        """
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise TypeError(f"format_decimal espera un número, no {type(value).__name__}")
        spec = f"{',' if grouping else ''}.{digits}f"
        return self._localize(format(value, spec))

    def _localize(self, text: str) -> str:
        """Cambia los separadores de Python (``,`` miles, ``.`` decimal) por los del idioma."""
        return text.translate({ord(","): "\x00", ord("."): self._decimal_sep}).replace("\x00", self._thousands_sep)


__all__: list[str] = ["CATALOG_ROOT", "DEFAULT_LOCALE", "SUPPORTED_LOCALES", "Locale", "Translator", "validate_locale"]
