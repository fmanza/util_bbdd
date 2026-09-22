"""Traducción de opciones libpq (psycopg3) a server_settings (asyncpg).

CNX-04 (AUDIT_CODE 2026-09-22): la versión sync (psycopg3) aplica
``schema``/``options``/``application_name`` vía los parámetros libpq ``options=``
y ``application_name=`` (ver ``PostgreSQLConnectionConfig.to_driver_kwargs`` en
``connection/config.py``, que ya combina ``schema`` → ``-c search_path=...`` con
cualquier ``options`` de usuario en un único string). La versión async los
descartaba en silencio porque ``asyncpg.connect()``/``asyncpg.create_pool()`` no
aceptan esas claves directamente — requieren ``server_settings`` (dict plano de
parámetros de sesión del servidor), compartido aquí entre conexión directa y pool.
"""

from __future__ import annotations

from typing import Any


def parse_libpq_options(options: str) -> dict[str, str]:
    """Parsea un string de opciones libpq estilo ``-c clave=valor`` a dict.

    Solo reconoce el patrón ``-c clave=valor`` (el uso más común, generado por
    ``PostgreSQLConnectionConfig.to_driver_kwargs()`` para ``schema``/``options``);
    formas más complejas de libpq (comillas anidadas, escapes) no se soportan —
    se ignoran silenciosamente en vez de fallar la conexión.
    """
    settings: dict[str, str] = {}
    for fragment in options.split("-c "):
        fragment = fragment.strip()
        if not fragment or "=" not in fragment:
            continue
        key, _, value = fragment.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            settings[key] = value
    return settings


def build_server_settings(conn_params: dict[str, Any]) -> dict[str, str]:
    """Construye ``server_settings`` para asyncpg desde parámetros ya saneados.

    ``conn_params`` debe venir de ``ConnectionParamsManager.sanitize_for_connection``/
    ``sanitize_for_pool`` (ya en formato psycopg3: ``options``/``application_name``).
    """
    settings: dict[str, str] = {}

    options: Any = conn_params.get("options")
    if options:
        settings.update(parse_libpq_options(str(options)))

    application_name: Any = conn_params.get("application_name")
    if application_name:
        settings["application_name"] = str(application_name)

    return settings


__all__: list[str] = ["build_server_settings", "parse_libpq_options"]
