"""DSN de Oracle a partir de los parámetros saneados (conexión y pool, sync y async)."""

from __future__ import annotations

from typing import Any

__all__: list[str] = ["build_oracle_dsn"]


def build_oracle_dsn(oracledb_module: Any, conn_params: dict[str, Any]) -> str:
    """``dsn`` explícito o descriptor de ``makedsn`` con ``service_name`` / ``sid`` / ``database`` (alias de
    ``service_name``), por ese orden.

    ``protocol="tcps"`` cambia el ``PROTOCOL`` del descriptor (``makedsn`` solo genera TCP): antes se descartaba y la
    conexión iba sin TLS.

    Raises:
        ValueError: Si no hay ``dsn`` ni ``service_name``/``sid``/``database``.
    """
    dsn: Any = conn_params.get("dsn")
    if dsn:
        return str(dsn)
    host: str = str(conn_params.get("host") or "localhost")
    port: int = int(conn_params.get("port", 1521))
    service_name: Any = conn_params.get("service_name") or conn_params.get("database")
    sid: Any = conn_params.get("sid")
    if conn_params.get("service_name"):
        descriptor: str = oracledb_module.makedsn(host=host, port=port, service_name=service_name)
    elif sid:
        descriptor = oracledb_module.makedsn(host=host, port=port, sid=sid)
    elif service_name:
        descriptor = oracledb_module.makedsn(host=host, port=port, service_name=service_name)
    else:
        raise ValueError(
            "Para Oracle debe proporcionar 'dsn' o bien 'service_name'/'sid' "
            "(también se acepta 'database' como alias de service_name)."
        )
    protocol: str = str(conn_params.get("protocol") or "tcp").upper()
    if protocol != "TCP":
        descriptor = descriptor.replace("(PROTOCOL=TCP)", f"(PROTOCOL={protocol})", 1)
    return descriptor
