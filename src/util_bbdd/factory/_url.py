"""Helpers de URL compartidos por ``SQLAlchemyEngineFactory`` y ``AsyncSQLAlchemyEngineFactory``."""

from __future__ import annotations

import logging

from typing import Any

from .._core.exceptions import ValidationError

logger: logging.Logger = logging.getLogger(__name__)

#: Por motor: (nombre para mensajes, usuario por defecto, puerto por defecto).
_SERVER_DEFAULTS: dict[str, tuple[str, str | None, int]] = {
    "mariadb": ("MariaDB", "root", 3306),
    "mysql": ("MySQL", "root", 3306),
    "postgresql": ("PostgreSQL", "postgres", 5432),
    "sqlserver": ("SQL Server", "sa", 1433),
    "oracle": ("Oracle", None, 1521),
}


def _text(conn_params: dict[str, Any], key: str, default: str | None) -> str | None:
    """``conn_params[key]`` como texto; ``None`` (ausente o explícito) da ``default``."""
    value: Any = conn_params.get(key)
    return default if value is None else str(value)


def server_url(db_type: str, drivername: str, conn_params: dict[str, Any], database: str | None) -> str:
    """URL de SQLAlchemy de un motor de servidor, con la misma semántica en las factories sync y async.

    ``host``/``user``/``port`` ausentes o ``None`` toman su valor por defecto; ``database`` ``None`` se toma de
    ``conn_params["database"]``; MariaDB, MySQL, PostgreSQL y SQL Server exigen contraseña y base de datos; Oracle exige
    usuario y contraseña y usa ``service_name`` o, si está vacío, ``database`` (alias, como ``OracleConnectionConfig``);
    sin ninguno de los dos vale ``dsn``/``sid`` (los resuelve el ``creator`` nativo).

    Raises:
        ValidationError: Si falta un parámetro requerido.
    """
    name, default_user, default_port = _SERVER_DEFAULTS[db_type]
    host: str = str(_text(conn_params, "host", "localhost"))
    user: str | None = _text(conn_params, "user", default_user)
    password: str | None = _text(conn_params, "password", None)
    port_value: Any = conn_params.get("port")
    port: int = default_port if port_value is None else int(port_value)
    raw_database: Any = database if database is not None else conn_params.get("database")
    target_db: str = "" if raw_database is None else str(raw_database)

    if db_type == "oracle" and not user:
        logger.warning(f"⚠️ No se proporcionó usuario para {name}")
        raise ValidationError(f"Se requiere un usuario para la conexión a {name}", db_type=db_type)
    if not password:
        logger.warning(f"⚠️ No se proporcionó contraseña para {name}")
        raise ValidationError(f"Se requiere una contraseña para la conexión a {name}", db_type=db_type)

    if db_type == "oracle":
        service_name: str = _text(conn_params, "service_name", None) or target_db
        if not service_name:
            if conn_params.get("dsn") or conn_params.get("sid"):
                # El destino lo resuelve el ``creator`` nativo (makedsn con dsn/sid).
                return render_url(drivername, str(user), password, host, port, "")
            raise ValidationError(f"Se requiere 'service_name' o 'database' para {name}", db_type=db_type)
        return render_url(drivername, str(user), password, host, port, "", query={"service_name": service_name})

    if not target_db:
        raise ValidationError(f"Se requiere 'database' para {name}", db_type=db_type)
    return render_url(drivername, str(user), password, host, port, target_db)


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
