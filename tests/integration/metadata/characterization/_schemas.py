"""Schema fijo de caracterización por motor (objetos ``zz_gold_*``) y cómo conectarse a él.

Mismo contenido lógico en todos los motores: PK simple y compuesta, FK con ``ON DELETE CASCADE``, FK compuesta, UK,
índice secundario, columna identidad, comentario de tabla, una vista, una función y un procedure (salvo SQLite).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import secrets
import tempfile

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

PREFIX = "zz_gold_"
# Driver nativo que usa el manager para el motor (la URL de los tests puede usar otro, p. ej. PyMySQL)
_NATIVE_DRIVERS: dict[str, str] = {"mariadb": "mariadb"}


def skip_reason(engine: str, url_env: str | None) -> str | None:
    """Por qué no se puede probar ``engine`` aquí (sin URL o sin el driver nativo del manager); ``None`` si se puede."""
    if url_env and not os.environ.get(url_env):
        return f"{url_env} no definida"
    driver = _NATIVE_DRIVERS.get(engine)
    if driver and importlib.util.find_spec(driver) is None:
        return f"paquete {driver} no instalado (driver del manager para {engine})"
    return None


@dataclass(frozen=True)
class GoldenTarget:
    """Dónde vive el schema de caracterización de un motor y cómo conectarse."""

    engine: str  # db_type de la librería
    url_env: str | None
    schema: str  # schema/owner/base que leen managers y extractores
    create: tuple[str, ...]
    drop: tuple[str, ...]
    migrate_source: bool = True
    doc: bool = True  # False si el schema no está aislado (Oracle comparte el del usuario bench): ver oracle_doc_target
    extra: dict[str, Any] = field(default_factory=dict)
    admin_url_env: str | None = None  # URL con la que se crea y borra el schema, si no es url_env
    login: tuple[str, str] | None = None  # (usuario, contraseña) del manager, si no son los de url_env

    def skip_reason(self) -> str | None:
        """Por qué no se puede probar este motor aquí (sin URL o sin el driver nativo del manager); ``None`` si se puede.

        ``SyncDatabaseManager("mariadb")`` usa MariaDB Connector/Python (paquete ``mariadb``), no el PyMySQL de la URL:
        sin él, los tests de MariaDB se saltan en lugar de fallar (p. ej. en el CI de integración, sin Connector/C).
        """
        return skip_reason(self.engine, self.url_env)

    def admin_engine(self) -> Engine:
        if self.engine == "sqlite":
            return create_engine(f"sqlite:///{sqlite_path().as_posix()}")
        url_env = self.admin_url_env or self.url_env
        assert url_env
        return create_engine(os.environ[url_env], isolation_level="AUTOCOMMIT")

    def manager_args(self) -> tuple[str, dict[str, Any]]:
        if self.engine == "sqlite":
            return "sqlite", {"database": str(sqlite_path())}
        assert self.url_env
        url = make_url(os.environ[self.url_env])
        params: dict[str, Any] = {"host": url.host, "port": url.port, "user": url.username, "password": url.password}
        if self.login:
            params["user"], params["password"] = self.login
        if self.engine == "oracle":
            return "oracle", {**params, "service_name": url.query.get("service_name", "FREEPDB1")}
        if self.engine in ("mysql", "mariadb"):
            return self.engine, {**params, "database": self.schema}
        return self.engine, {**params, "database": url.database, "schema": self.schema}


def sqlite_path() -> Path:
    return Path(tempfile.gettempdir()) / "util_bbdd_golden.db"


def _std_tables(*, int_t: str, txt: str, num: str, date: str, identity: str, tail: str = "") -> tuple[str, ...]:
    p = PREFIX
    return (
        f"CREATE TABLE {p}parent (id {int_t} NOT NULL, code {txt}(20) NOT NULL, name {txt}(100), amount {num}(12,2), "
        f"created {date}, CONSTRAINT pk_{p}parent PRIMARY KEY (id), CONSTRAINT uk_{p}parent_code UNIQUE (code)){tail}",
        f"CREATE TABLE {p}child (id {int_t} NOT NULL, parent_id {int_t} NOT NULL, label {txt}(50), "
        f"CONSTRAINT pk_{p}child PRIMARY KEY (id), CONSTRAINT fk_{p}child_parent FOREIGN KEY (parent_id) "
        f"REFERENCES {p}parent (id) ON DELETE CASCADE){tail}",
        f"CREATE INDEX ix_{p}child_label ON {p}child (label)",
        f"CREATE TABLE {p}composite (a {int_t} NOT NULL, b {int_t} NOT NULL, note {txt}(30), "
        f"CONSTRAINT pk_{p}composite PRIMARY KEY (a, b)){tail}",
        f"CREATE TABLE {p}ref_composite (id {int_t} NOT NULL, a {int_t}, b {int_t}, "
        f"CONSTRAINT pk_{p}ref_composite PRIMARY KEY (id), CONSTRAINT fk_{p}ref_composite FOREIGN KEY (a, b) "
        f"REFERENCES {p}composite (a, b)){tail}",
        # PK con nombre (los nombres generados por el motor cambian en cada creación); SQLite exige AUTOINCREMENT en línea
        f"CREATE TABLE {p}identity (id {identity}, val {txt}(10)"
        + ("" if "PRIMARY KEY" in identity else f", CONSTRAINT pk_{p}identity PRIMARY KEY (id)")
        + f"){tail}",
        f"CREATE VIEW {p}v_parent AS SELECT id, code FROM {p}parent",
    )


def targets() -> list[GoldenTarget]:
    p = PREFIX
    drop_std = (
        f"DROP VIEW {p}v_parent",
        f"DROP TABLE {p}ref_composite",
        f"DROP TABLE {p}composite",
        f"DROP TABLE {p}child",
        f"DROP TABLE {p}parent",
        f"DROP TABLE {p}identity",
    )
    pg_schema = "zz_util_bbdd_gold"
    return [
        GoldenTarget(
            engine="postgresql",
            url_env="UTIL_BBDD_TEST_POSTGRESQL_URL",
            schema=pg_schema,
            create=(
                f"CREATE SCHEMA {pg_schema}",
                f"SET search_path TO {pg_schema}",
                *_std_tables(
                    int_t="integer",
                    txt="varchar",
                    num="numeric",
                    date="date",
                    identity="integer GENERATED BY DEFAULT AS IDENTITY",
                ),
                f"COMMENT ON TABLE {p}parent IS 'tabla padre'",
                f"CREATE FUNCTION {p}f(x integer) RETURNS integer LANGUAGE sql AS 'SELECT x + 1'",
                f"CREATE PROCEDURE {p}p(x integer) LANGUAGE plpgsql AS $$ BEGIN PERFORM x; END $$",
            ),
            drop=(f"DROP SCHEMA IF EXISTS {pg_schema} CASCADE",),
        ),
        *[
            GoldenTarget(
                engine=engine,
                url_env=env,
                schema="zz_util_bbdd_gold",
                create=(
                    "CREATE DATABASE zz_util_bbdd_gold",
                    "USE zz_util_bbdd_gold",
                    *_std_tables(
                        int_t="INT",
                        txt="VARCHAR",
                        num="DECIMAL",
                        date="DATE",
                        identity="INT NOT NULL AUTO_INCREMENT",
                        tail=" ENGINE=InnoDB",
                    ),
                    f"ALTER TABLE {p}parent COMMENT = 'tabla padre'",
                    f"CREATE FUNCTION {p}f(x INT) RETURNS INT DETERMINISTIC NO SQL RETURN x + 1",
                    f"CREATE PROCEDURE {p}p(IN x INT) NO SQL BEGIN DECLARE y INT; SET y = x; END",
                ),
                drop=("DROP DATABASE IF EXISTS zz_util_bbdd_gold",),
            )
            for engine, env in (("mysql", "UTIL_BBDD_TEST_MYSQL_URL"), ("mariadb", "UTIL_BBDD_TEST_MARIADB_URL"))
        ],
        GoldenTarget(
            engine="sqlserver",
            url_env="UTIL_BBDD_TEST_MSSQL_URL",
            schema="zz_gold",
            create=(
                "CREATE SCHEMA zz_gold",
                *[
                    s.replace(f"TABLE {p}", f"TABLE zz_gold.{p}")
                    .replace(f"REFERENCES {p}", f"REFERENCES zz_gold.{p}")
                    .replace(f"VIEW {p}", f"VIEW zz_gold.{p}")
                    .replace(f"FROM {p}", f"FROM zz_gold.{p}")
                    .replace(f" ON {p}", f" ON zz_gold.{p}")
                    for s in _std_tables(
                        int_t="INT", txt="VARCHAR", num="DECIMAL", date="DATE", identity="INT IDENTITY(1,1) NOT NULL"
                    )
                ],
                "EXEC sp_addextendedproperty N'MS_Description', N'tabla padre', N'SCHEMA', N'zz_gold', N'TABLE', "
                f"N'{p}parent'",
                f"CREATE FUNCTION zz_gold.{p}f(@x INT) RETURNS INT AS BEGIN RETURN @x + 1 END",
                f"CREATE PROCEDURE zz_gold.{p}p @x INT AS BEGIN SET NOCOUNT ON; SELECT @x END",
            ),
            drop=(
                f"DROP PROCEDURE IF EXISTS zz_gold.{p}p",
                f"DROP FUNCTION IF EXISTS zz_gold.{p}f",
                *[
                    s.replace("DROP VIEW ", "DROP VIEW IF EXISTS zz_gold.").replace(
                        "DROP TABLE ", "DROP TABLE IF EXISTS zz_gold."
                    )
                    for s in drop_std
                ],
                "IF SCHEMA_ID('zz_gold') IS NOT NULL EXEC('DROP SCHEMA zz_gold')",
            ),
        ),
        GoldenTarget(
            engine="oracle",
            url_env="UTIL_BBDD_TEST_ORACLE_URL",
            schema="BENCH",
            create=(
                *_std_tables(
                    int_t="NUMBER(10)",
                    txt="VARCHAR2",
                    num="NUMBER",
                    date="DATE",
                    identity="NUMBER(10) GENERATED BY DEFAULT AS IDENTITY",
                ),
                f"COMMENT ON TABLE {p}parent IS 'tabla padre'",
                f"CREATE OR REPLACE FUNCTION {p}f(x NUMBER) RETURN NUMBER IS BEGIN RETURN x + 1; END;",
                f"CREATE OR REPLACE PROCEDURE {p}p(x NUMBER) IS y NUMBER; BEGIN y := x; END;",
            ),
            drop=(
                f"DROP PROCEDURE {p}p",
                f"DROP FUNCTION {p}f",
                *[s + (" CASCADE CONSTRAINTS PURGE" if s.startswith("DROP TABLE") else "") for s in drop_std],
            ),
            doc=False,
        ),
        GoldenTarget(
            engine="sqlite",
            url_env=None,
            schema="main",
            create=_std_tables(
                int_t="INTEGER", txt="VARCHAR", num="NUMERIC", date="DATE", identity="INTEGER PRIMARY KEY AUTOINCREMENT"
            ),
            drop=(),
            migrate_source=False,
        ),
    ]


ORACLE_DOC_USER = "ZZ_GOLD_DOC"
ORACLE_ADMIN_URL_ENV = "UTIL_BBDD_TEST_ORACLE_ADMIN_URL"


def oracle_doc_target(oracle: GoldenTarget) -> GoldenTarget | None:
    """El schema de Oracle en un usuario propio (``ZZ_GOLD_DOC``) para el dorado de documentación.

    En Oracle el contexto de metadatos es el usuario conectado, y el de ``bench`` tiene objetos de otras pruebas: la
    documentación los incluiría. Se crea con ``SYSTEM`` (``UTIL_BBDD_TEST_ORACLE_ADMIN_URL``, ver
    ``scripts/bench_env.example.sh``), con una contraseña nueva en cada ejecución, y se borra con ``DROP USER …
    CASCADE``. ``None`` si falta la URL de administración.
    """
    if not os.environ.get(ORACLE_ADMIN_URL_ENV):
        return None
    password = "Zz" + secrets.token_hex(12)
    user = ORACLE_DOC_USER
    return dataclasses.replace(
        oracle,
        schema=user,
        create=(
            f'CREATE USER {user} IDENTIFIED BY "{password}" QUOTA UNLIMITED ON USERS',
            f"GRANT CREATE SESSION TO {user}",
            f"ALTER SESSION SET CURRENT_SCHEMA = {user}",
            *oracle.create,
        ),
        drop=(f"DROP USER {user} CASCADE",),
        doc=True,
        admin_url_env=ORACLE_ADMIN_URL_ENV,
        login=(user, password),
    )


def build(target: GoldenTarget) -> None:
    """Borra lo que hubiera de una ejecución anterior y crea el schema."""
    if target.engine == "sqlite":
        sqlite_path().unlink(missing_ok=True)
    else:
        drop(target)
    eng = target.admin_engine()
    with eng.connect() as conn:
        for stmt in target.create:
            conn.execute(text(stmt))
        if target.engine == "sqlite":
            conn.commit()
    eng.dispose()


def drop(target: GoldenTarget) -> None:
    if target.engine == "sqlite":
        sqlite_path().unlink(missing_ok=True)
        return
    eng = target.admin_engine()
    with eng.connect() as conn:
        for stmt in target.drop:
            try:
                conn.execute(text(stmt))
            except Exception:  # noqa: BLE001 - objeto inexistente en la limpieza previa
                pass
    eng.dispose()
