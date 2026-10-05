"""Clases de configuracion tipadas para conexiones y pools por motor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _require_str(params: dict[str, Any], key: str, db_type: str) -> str:
    value: Any = params.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Parametro requerido faltante para {db_type}: {key}")
    return str(value).strip()


def _opt_str(params: dict[str, Any], key: str) -> str | None:
    if key not in params or params.get(key) is None:
        return None
    value: str = str(params.get(key)).strip()
    return value if value != "" else None


def _to_int(value: Any, key: str, db_type: str, min_value: int | None = None) -> int:
    try:
        parsed: int = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {db_type}: {key} debe ser entero") from exc
    if min_value is not None and parsed < min_value:
        raise ValueError(f"Parametro invalido para {db_type}: {key} debe ser >= {min_value}")
    return parsed


def _to_float(value: Any, key: str, db_type: str, min_value: float | None = None) -> float:
    try:
        parsed: float = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {db_type}: {key} debe ser numerico") from exc
    if min_value is not None and parsed < min_value:
        raise ValueError(f"Parametro invalido para {db_type}: {key} debe ser >= {min_value}")
    return parsed


def _to_bool(value: Any, key: str, db_type: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized: str = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    raise ValueError(f"Parametro invalido para {db_type}: {key} debe ser booleano")


@dataclass(frozen=True)
class MariaDBConnectionConfig:
    host: str
    user: str
    password: str
    database: str
    port: int = 3306
    unix_socket: str | None = None
    autocommit: bool = False
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 60
    charset: str | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> MariaDBConnectionConfig:
        db_type: str = "mariadb"
        return cls(
            host=_require_str(params, "host", db_type),
            user=_require_str(params, "user", db_type),
            password=_require_str(params, "password", db_type),
            database=_require_str(params, "database", db_type),
            port=_to_int(params.get("port", 3306), "port", db_type, min_value=1),
            unix_socket=_opt_str(params, "unix_socket"),
            autocommit=_to_bool(params.get("autocommit", False), "autocommit", db_type),
            connect_timeout=_to_int(params.get("connect_timeout", 10), "connect_timeout", db_type, min_value=0),
            read_timeout=_to_int(params.get("read_timeout", 30), "read_timeout", db_type, min_value=0),
            write_timeout=_to_int(params.get("write_timeout", 60), "write_timeout", db_type, min_value=0),
            charset=_opt_str(params, "charset"),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
            "autocommit": self.autocommit,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "write_timeout": self.write_timeout,
        }
        if self.unix_socket:
            payload["unix_socket"] = self.unix_socket
        if self.charset:
            payload["charset"] = self.charset
        return payload


@dataclass(frozen=True)
class MariaDBPoolConfig:
    connection: MariaDBConnectionConfig
    pool_size: int = 5
    pool_name: str | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> MariaDBPoolConfig:
        db_type: str = "mariadb"
        connection = MariaDBConnectionConfig.from_params(params)
        pool_name: str | None = _opt_str(params, "pool_name")
        return cls(
            connection=connection,
            pool_size=_to_int(params.get("pool_size", 5), "pool_size", db_type, min_value=1),
            pool_name=pool_name,
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs()
        payload["pool_size"] = self.pool_size
        if self.pool_name:
            payload["pool_name"] = self.pool_name
        return payload


@dataclass(frozen=True)
class MySQLConnectionConfig:
    """Parámetros de conexión MySQL para ``pymysql.connect`` (lista blanca).

    ``local_infile`` y ``client_flag`` (p. ej. ``MULTI_STATEMENTS``) no se aceptan: PyMySQL los deja desactivados
    por defecto y ``to_driver_kwargs`` no los reenvía aunque lleguen en ``conn_params``.
    """

    host: str
    user: str
    password: str
    database: str
    port: int = 3306
    unix_socket: str | None = None
    autocommit: bool = False
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 60
    charset: str | None = None
    ssl_ca: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None
    ssl_verify_cert: bool | None = None
    ssl_verify_identity: bool | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> MySQLConnectionConfig:
        db_type: str = "mysql"
        ssl_verify_cert: Any = params.get("ssl_verify_cert")
        ssl_verify_identity: Any = params.get("ssl_verify_identity")
        return cls(
            host=_require_str(params, "host", db_type),
            user=_require_str(params, "user", db_type),
            password=_require_str(params, "password", db_type),
            database=_require_str(params, "database", db_type),
            port=_to_int(params.get("port", 3306), "port", db_type, min_value=1),
            unix_socket=_opt_str(params, "unix_socket"),
            autocommit=_to_bool(params.get("autocommit", False), "autocommit", db_type),
            connect_timeout=_to_int(params.get("connect_timeout", 10), "connect_timeout", db_type, min_value=0),
            read_timeout=_to_int(params.get("read_timeout", 30), "read_timeout", db_type, min_value=0),
            write_timeout=_to_int(params.get("write_timeout", 60), "write_timeout", db_type, min_value=0),
            charset=_opt_str(params, "charset"),
            ssl_ca=_opt_str(params, "ssl_ca"),
            ssl_cert=_opt_str(params, "ssl_cert"),
            ssl_key=_opt_str(params, "ssl_key"),
            ssl_verify_cert=None if ssl_verify_cert is None else _to_bool(ssl_verify_cert, "ssl_verify_cert", db_type),
            ssl_verify_identity=None
            if ssl_verify_identity is None
            else _to_bool(ssl_verify_identity, "ssl_verify_identity", db_type),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
            "autocommit": self.autocommit,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "write_timeout": self.write_timeout,
        }
        optional: dict[str, Any] = {
            "unix_socket": self.unix_socket,
            "charset": self.charset,
            "ssl_ca": self.ssl_ca,
            "ssl_cert": self.ssl_cert,
            "ssl_key": self.ssl_key,
            "ssl_verify_cert": self.ssl_verify_cert,
            "ssl_verify_identity": self.ssl_verify_identity,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload


@dataclass(frozen=True)
class MySQLPoolConfig:
    """Pool MySQL: ``QueuePool`` de SQLAlchemy sobre ``pymysql.connect`` (PyMySQL no tiene pool nativo)."""

    connection: MySQLConnectionConfig
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> MySQLPoolConfig:
        db_type: str = "mysql"
        return cls(
            connection=MySQLConnectionConfig.from_params(params),
            pool_size=_to_int(params.get("pool_size", 5), "pool_size", db_type, min_value=1),
            max_overflow=_to_int(params.get("max_overflow", 10), "max_overflow", db_type, min_value=0),
            pool_timeout=_to_int(params.get("pool_timeout", 30), "pool_timeout", db_type, min_value=0),
            pool_recycle=_to_int(params.get("pool_recycle", 3600), "pool_recycle", db_type, min_value=-1),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs()
        payload["pool_size"] = self.pool_size
        payload["max_overflow"] = self.max_overflow
        payload["pool_timeout"] = self.pool_timeout
        payload["pool_recycle"] = self.pool_recycle
        return payload


@dataclass(frozen=True)
class PostgreSQLConnectionConfig:
    host: str
    user: str
    password: str
    database: str
    port: int = 5432
    schema: str | None = None
    dbname: str | None = None
    sslmode: str | None = None
    connect_timeout: int = 10
    application_name: str | None = None
    fallback_application_name: str | None = None
    keepalives: bool = True
    tcp_keepalives_idle: int | None = None
    tcp_keepalives_interval: int | None = None
    tcp_keepalives_count: int | None = None
    options: str | None = None
    target_session_attrs: str | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> PostgreSQLConnectionConfig:
        db_type: str = "postgresql"
        sslmode: str | None = _opt_str(params, "sslmode")
        if sslmode is not None:
            valid: set[str] = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
            if sslmode not in valid:
                raise ValueError(f"Parametro invalido para {db_type}: sslmode={sslmode}")
        return cls(
            host=_require_str(params, "host", db_type),
            user=_require_str(params, "user", db_type),
            password=_require_str(params, "password", db_type),
            database=_require_str(params, "database", db_type),
            port=_to_int(params.get("port", 5432), "port", db_type, min_value=1),
            schema=_opt_str(params, "schema"),
            dbname=_opt_str(params, "dbname"),
            sslmode=sslmode,
            connect_timeout=_to_int(params.get("connect_timeout", 10), "connect_timeout", db_type, min_value=0),
            application_name=_opt_str(params, "application_name"),
            fallback_application_name=_opt_str(params, "fallback_application_name"),
            keepalives=_to_bool(params.get("keepalives", True), "keepalives", db_type),
            tcp_keepalives_idle=(
                _to_int(params.get("tcp_keepalives_idle"), "tcp_keepalives_idle", db_type, min_value=0)
                if params.get("tcp_keepalives_idle") is not None
                else None
            ),
            tcp_keepalives_interval=(
                _to_int(
                    params.get("tcp_keepalives_interval"),
                    "tcp_keepalives_interval",
                    db_type,
                    min_value=0,
                )
                if params.get("tcp_keepalives_interval") is not None
                else None
            ),
            tcp_keepalives_count=(
                _to_int(params.get("tcp_keepalives_count"), "tcp_keepalives_count", db_type, min_value=0)
                if params.get("tcp_keepalives_count") is not None
                else None
            ),
            options=_opt_str(params, "options"),
            target_session_attrs=_opt_str(params, "target_session_attrs"),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
            "connect_timeout": self.connect_timeout,
            "keepalives": self.keepalives,
        }
        # schema is not a libpq parameter; it must be set via options=-c search_path=...
        options_parts: list[str] = []
        if self.schema:
            options_parts.append(f"-c search_path={self.schema}")
        if self.options:
            options_parts.append(self.options)
        if options_parts:
            payload["options"] = " ".join(options_parts)
        if self.dbname:
            payload["dbname"] = self.dbname
        if self.sslmode:
            payload["sslmode"] = self.sslmode
        if self.application_name:
            payload["application_name"] = self.application_name
        if self.fallback_application_name:
            payload["fallback_application_name"] = self.fallback_application_name
        if self.tcp_keepalives_idle is not None:
            payload["tcp_keepalives_idle"] = self.tcp_keepalives_idle
        if self.tcp_keepalives_interval is not None:
            payload["tcp_keepalives_interval"] = self.tcp_keepalives_interval
        if self.tcp_keepalives_count is not None:
            payload["tcp_keepalives_count"] = self.tcp_keepalives_count
        if self.target_session_attrs:
            payload["target_session_attrs"] = self.target_session_attrs
        return payload


@dataclass(frozen=True)
class PostgreSQLPoolConfig:
    connection: PostgreSQLConnectionConfig
    pool_size: int = 5
    pool_timeout: int = 30
    max_idle: int = 300

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> PostgreSQLPoolConfig:
        db_type: str = "postgresql"
        return cls(
            connection=PostgreSQLConnectionConfig.from_params(params),
            pool_size=_to_int(params.get("pool_size", 5), "pool_size", db_type, min_value=1),
            pool_timeout=_to_int(params.get("pool_timeout", 30), "pool_timeout", db_type, min_value=0),
            max_idle=_to_int(params.get("max_idle", 300), "max_idle", db_type, min_value=0),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs()
        payload.update(
            {
                "pool_size": self.pool_size,
                "pool_timeout": self.pool_timeout,
                "max_idle": self.max_idle,
            }
        )
        return payload


@dataclass(frozen=True)
class OracleConnectionConfig:
    user: str
    password: str
    dsn: str | None = None
    host: str = "localhost"
    port: int = 1521
    service_name: str | None = None
    sid: str | None = None
    database: str | None = None
    oracle_client_path: str | None = None
    oracle_thick_mode: bool = False

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> OracleConnectionConfig:
        db_type: str = "oracle"
        dsn: str | None = _opt_str(params, "dsn")
        service_name: str | None = _opt_str(params, "service_name")
        sid: str | None = _opt_str(params, "sid")
        database: str | None = _opt_str(params, "database")
        if not (dsn or service_name or sid or database):
            raise ValueError("Para oracle debe informar 'dsn' o 'service_name' o 'sid' o 'database'")
        return cls(
            user=_require_str(params, "user", db_type),
            password=_require_str(params, "password", db_type),
            dsn=dsn,
            host=str(params.get("host", "localhost")),
            port=_to_int(params.get("port", 1521), "port", db_type, min_value=1),
            service_name=service_name,
            sid=sid,
            database=database,
            oracle_client_path=_opt_str(params, "oracle_client_path"),
            oracle_thick_mode=_to_bool(params.get("oracle_thick_mode", False), "oracle_thick_mode", db_type),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
        }
        if self.dsn:
            payload["dsn"] = self.dsn
        if self.service_name:
            payload["service_name"] = self.service_name
        if self.sid:
            payload["sid"] = self.sid
        if self.database:
            payload["database"] = self.database
        if self.oracle_client_path:
            payload["oracle_client_path"] = self.oracle_client_path
        return payload


@dataclass(frozen=True)
class OraclePoolConfig:
    connection: OracleConnectionConfig
    pool_size: int = 5
    max_lifetime: int = 3600

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> OraclePoolConfig:
        db_type: str = "oracle"
        return cls(
            connection=OracleConnectionConfig.from_params(params),
            pool_size=_to_int(params.get("pool_size", 5), "pool_size", db_type, min_value=1),
            max_lifetime=_to_int(params.get("max_lifetime", 3600), "max_lifetime", db_type, min_value=1),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs()
        payload.update({"pool_size": self.pool_size, "max_lifetime": self.max_lifetime})
        return payload


@dataclass(frozen=True)
class SQLServerConnectionConfig:
    host: str
    user: str
    password: str
    database: str
    port: int = 1433
    timeout: int = 30
    login_timeout: int = 20
    charset: str = "UTF-8"
    as_dict: bool = False
    encryption: str = "optional"
    trust_cert: bool = False
    use_mars: bool = True
    sql_server_driver: str = "pymssql"
    driver_name: str = "ODBC Driver 17 for SQL Server"

    @classmethod
    def from_params(cls, params: dict[str, Any], driver: str | None = None) -> SQLServerConnectionConfig:
        db_type: str = "sqlserver"
        selected_driver: str = str(driver or params.get("sql_server_driver", "pymssql")).lower()
        if selected_driver not in {"pymssql", "pyodbc"}:
            raise ValueError(f"Driver invalido para SQL Server: {selected_driver}")
        encryption: str = str(params.get("encryption", "optional")).lower()
        if encryption not in {"mandatory", "optional", "off"}:
            raise ValueError(f"Parametro invalido para {db_type}: encryption={encryption}")
        return cls(
            host=_require_str(params, "host", db_type),
            user=_require_str(params, "user", db_type),
            password=_require_str(params, "password", db_type),
            database=_require_str(params, "database", db_type),
            port=_to_int(params.get("port", 1433), "port", db_type, min_value=1),
            timeout=_to_int(params.get("timeout", 30), "timeout", db_type, min_value=0),
            login_timeout=_to_int(params.get("login_timeout", 20), "login_timeout", db_type, min_value=0),
            charset=str(params.get("charset", "UTF-8")),
            as_dict=_to_bool(params.get("as_dict", False), "as_dict", db_type),
            encryption=encryption,
            trust_cert=_to_bool(params.get("trust_cert", False), "trust_cert", db_type),
            use_mars=_to_bool(params.get("use_mars", True), "use_mars", db_type),
            sql_server_driver=selected_driver,
            driver_name=str(params.get("driver_name", "ODBC Driver 17 for SQL Server")),
        )

    def to_driver_kwargs(self, driver: str | None = None) -> dict[str, Any]:
        selected_driver: str = str(driver or self.sql_server_driver).lower()
        payload: dict[str, Any] = {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "port": self.port,
            "timeout": self.timeout,
            "login_timeout": self.login_timeout,
            "charset": self.charset,
            "as_dict": self.as_dict,
            "encryption": self.encryption,
            "trust_cert": self.trust_cert,
            "use_mars": self.use_mars,
            "sql_server_driver": selected_driver,
        }
        if selected_driver == "pyodbc":
            payload["driver_name"] = self.driver_name
        return payload


@dataclass(frozen=True)
class SQLServerPoolConfig:
    connection: SQLServerConnectionConfig
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

    @classmethod
    def from_params(cls, params: dict[str, Any], driver: str | None = None) -> SQLServerPoolConfig:
        db_type: str = "sqlserver"
        return cls(
            connection=SQLServerConnectionConfig.from_params(params, driver=driver),
            pool_size=_to_int(params.get("pool_size", 5), "pool_size", db_type, min_value=1),
            max_overflow=_to_int(params.get("max_overflow", 10), "max_overflow", db_type, min_value=0),
            pool_timeout=_to_int(params.get("pool_timeout", 30), "pool_timeout", db_type, min_value=0),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs(driver=self.connection.sql_server_driver)
        payload.update(
            {
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "pool_timeout": self.pool_timeout,
            }
        )
        return payload


@dataclass(frozen=True)
class SQLiteConnectionConfig:
    database: str
    timeout: float = 5.0
    check_same_thread: bool = False
    isolation_level: str = ""
    cached_statements: int = 100

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> SQLiteConnectionConfig:
        db_type: str = "sqlite"
        isolation_level: str = str(params.get("isolation_level", "") or "").upper()
        if isolation_level not in {"", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"}:
            raise ValueError(f"Parametro invalido para {db_type}: isolation_level={isolation_level}")
        return cls(
            database=_require_str(params, "database", db_type),
            timeout=_to_float(params.get("timeout", 5), "timeout", db_type, min_value=0),
            check_same_thread=_to_bool(params.get("check_same_thread", False), "check_same_thread", db_type),
            isolation_level=isolation_level,
            cached_statements=_to_int(params.get("cached_statements", 100), "cached_statements", db_type, min_value=0),
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "timeout": self.timeout,
            "check_same_thread": self.check_same_thread,
            "isolation_level": self.isolation_level,
            "cached_statements": self.cached_statements,
        }


@dataclass(frozen=True)
class SQLitePoolConfig:
    connection: SQLiteConnectionConfig
    pool_size: int = 1

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> SQLitePoolConfig:
        return cls(connection=SQLiteConnectionConfig.from_params(params), pool_size=1)

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = self.connection.to_driver_kwargs()
        payload["pool_size"] = self.pool_size
        return payload


@dataclass(frozen=True)
class HSQLDBConnectionConfig:
    user: str
    jdbc_url: str
    jdbc_jar: str
    password: str = ""
    jdbc_driver: str = "org.hsqldb.jdbcDriver"
    connection_properties: dict[str, Any] | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> HSQLDBConnectionConfig:
        db_type: str = "hsqldb"
        connection_properties: dict[str, Any] | None = None
        raw_connection_properties: Any = params.get("connection_properties")
        if raw_connection_properties is not None:
            if not isinstance(raw_connection_properties, dict):
                raise ValueError(f"Parametro invalido para {db_type}: connection_properties debe ser dict")
            normalized_properties: dict[str, Any] = {}
            for key, value in raw_connection_properties.items():
                if not isinstance(key, str):
                    raise ValueError(f"Parametro invalido para {db_type}: connection_properties debe usar claves str")
                normalized_properties[key] = value
            connection_properties = normalized_properties
        return cls(
            user=_require_str(params, "user", db_type),
            password=str(params.get("password", "")),
            jdbc_driver=str(params.get("jdbc_driver", "org.hsqldb.jdbcDriver")),
            jdbc_url=_require_str(params, "jdbc_url", db_type),
            jdbc_jar=_require_str(params, "jdbc_jar", db_type),
            connection_properties=connection_properties,
        )

    def to_driver_kwargs(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user": self.user,
            "password": self.password,
            "jdbc_driver": self.jdbc_driver,
            "jdbc_url": self.jdbc_url,
            "jdbc_jar": self.jdbc_jar,
        }
        if self.connection_properties is not None:
            payload["connection_properties"] = self.connection_properties
        return payload
