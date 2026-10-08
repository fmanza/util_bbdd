"""Helpers de URL compartidos por ``SQLAlchemyEngineFactory`` y ``AsyncSQLAlchemyEngineFactory``."""

from __future__ import annotations

from typing import Any


def render_url(
    drivername: str,
    user: str,
    password: str,
    host: str,
    port: Any,
    database: str,
    query: dict[str, str] | None = None,
) -> str:
    """URL con usuario y contraseña escapados (``URL.create``).

    Interpolarlos crudos permite que ``@``, ``:``, ``/``, ``?`` o ``#`` en la contraseña cambien el host de la URL
    (hotfix S1, drivers-connections-audit FASE 1).
    """
    from sqlalchemy.engine import URL

    url = URL.create(
        drivername,
        username=str(user),
        password=str(password),
        host=str(host),
        port=int(port),
        database=database,
        query=query or {},
    )
    return url.render_as_string(hide_password=False)


def sanitize_conn_str(conn_str: str) -> str:
    """Oculta la contraseña de una URL de conexión para logging (SVC-01, AUDIT_CODE 2026-09-22)."""
    if "@" not in conn_str or "://" not in conn_str:
        return conn_str
    prefix, rest = conn_str.split("://", 1)
    if ":" not in rest or "@" not in rest:
        return conn_str
    credentials, suffix = rest.split("@", 1)
    if ":" not in credentials:
        return conn_str
    user, _password = credentials.split(":", 1)
    return f"{prefix}://{user}:***@{suffix}"


def get_test_query(db_type: str) -> str:
    """Consulta de verificación de conexión por motor: Oracle requiere ``FROM DUAL``; el resto usa ``SELECT 1``."""
    if db_type == "oracle":
        return "SELECT 1 FROM DUAL"
    return "SELECT 1"


def sqlite_url(db_path: str, drivername: str) -> str:
    """URL SQLite (``<drivername>:///<ruta>`` o ``:memory:``) con separadores de Windows normalizados a ``/``.

    Una ruta absoluta tipo ``C:\\a\\b.db`` sin normalizar produce un URI SQLite inválido (SVC-03).
    """
    if db_path == ":memory:":
        return f"{drivername}:///:memory:"
    normalized_path: str = db_path.replace("\\", "/")
    return f"{drivername}:///{normalized_path}"
