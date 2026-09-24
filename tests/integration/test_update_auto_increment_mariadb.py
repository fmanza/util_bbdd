"""Integración de UpdateAutoIncrement contra un MariaDB/MySQL real.

Se salta si no hay servidor configurado. Para ejecutarlo apunta ``UTIL_BBDD_TEST_MARIADB_URL`` a un servidor de PRUEBAS
(URL de SQLAlchemy; la cuenta necesita CREATE y DROP sobre bases de datos)::

    UTIL_BBDD_TEST_MARIADB_URL="mariadb+pymysql://usuario:clave@servidor:3306/" \\
        python -m pytest tests/integration/test_update_auto_increment_mariadb.py

Cada prueba crea una base temporal ``zz_util_bbdd_autoinc_<id>`` y la elimina al terminar, incluso si falla; no toca
ninguna otra base de datos del servidor. El MariaDB de ``docker-compose.bench.yml`` da al usuario ``bench`` permisos
solo sobre bases ``zz_util_bbdd_*``, suficiente para este test (``scripts/bench_env.example.*`` define la URL).
"""

from __future__ import annotations

import logging
import os
import uuid

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.connection.mariadb import UpdateAutoIncrement

URL_ENV = "UTIL_BBDD_TEST_MARIADB_URL"

pytestmark = pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida (MariaDB de pruebas)")

_BIG = 2**63 + 5  # fuera del rango de un BIGINT con signo

_DDL: list[str] = [
    "CREATE TABLE orders (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, note VARCHAR(20))",
    "CREATE TABLE empty_table (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY)",
    # Clave compuesta: solo `id` es AUTO_INCREMENT (InnoDB exige un índice que lo encabece).
    "CREATE TABLE composite (tenant INT NOT NULL, id INT NOT NULL AUTO_INCREMENT, PRIMARY KEY (tenant, id), KEY (id))",
    "CREATE TABLE `order` (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY)",  # palabra reservada
    "CREATE TABLE `we``ird` (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY)",  # backtick en el nombre
    "CREATE TABLE big_ids (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY)",
    "CREATE TABLE no_auto (id INT NOT NULL PRIMARY KEY)",
    "CREATE VIEW orders_view AS SELECT id FROM orders",
]

# Objetos que no todos los servidores admiten: se crean si se puede y su ausencia no invalida la prueba.
_OPTIONAL_DDL: dict[str, str] = {
    "float_auto": "CREATE TABLE float_auto (id FLOAT NOT NULL AUTO_INCREMENT PRIMARY KEY)",
    "sequence": "CREATE SEQUENCE seq_extra",
    # Si el Inspector no la listara, el script la omitiría en silencio: por eso la prueba exige su sentencia.
    "versioned": ("CREATE TABLE versioned (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, v INT) WITH SYSTEM VERSIONING"),
}


@dataclass
class Scratch:
    engine: Engine  # conectado a la base temporal
    admin: Engine  # conectado como en la URL original (sin la base temporal)
    schema: str
    created_optional: set[str] = field(default_factory=set)


@pytest.fixture
def scratch() -> Iterator[Scratch]:
    base_url = make_url(os.environ[URL_ENV])
    schema = f"zz_util_bbdd_autoinc_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE `{schema}`"))
    engine = create_engine(base_url.set(database=schema), isolation_level="AUTOCOMMIT")
    fixture = Scratch(engine=engine, admin=admin, schema=schema)
    try:
        _populate(fixture)
        yield fixture
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{schema}`"))
        admin.dispose()


def _populate(fixture: Scratch) -> None:
    with fixture.engine.connect() as connection:
        for statement in _DDL:
            connection.execute(text(statement))
        for name, statement in _OPTIONAL_DDL.items():
            try:
                connection.execute(text(statement))
            except SQLAlchemyError:
                continue
            fixture.created_optional.add(name)

        # `orders`: el contador queda en 101 aunque el máximo real sea 41.
        connection.execute(text("INSERT INTO orders (note) VALUES (:note)"), [{"note": "x"}] * 100)
        connection.execute(text("DELETE FROM orders WHERE id > 41"))
        connection.execute(text("INSERT INTO composite (tenant, id) VALUES (1, 5), (2, 9)"))
        connection.execute(text("INSERT INTO `order` (id) VALUES (3)"))
        connection.execute(text("INSERT INTO `we``ird` (id) VALUES (7)"))
        connection.execute(text("INSERT INTO big_ids (id) VALUES (:big)"), {"big": _BIG})
        connection.execute(text("INSERT INTO no_auto (id) VALUES (1)"))
        if "versioned" in fixture.created_optional:
            connection.execute(text("INSERT INTO versioned (id, v) VALUES (11, 1)"))


def _expected(fixture: Scratch, schema: str | None = None) -> list[str]:
    """Sentencias esperadas, en el orden por nombre de tabla que garantiza la utilidad."""
    next_values: dict[str, int] = {
        "big_ids": _BIG + 1,
        "composite": 10,
        "empty_table": 1,
        "order": 4,
        "orders": 42,
        "we`ird": 8,
    }
    if "versioned" in fixture.created_optional:
        next_values["versioned"] = 12
    prefix = f"`{schema}`." if schema else ""
    return [
        f"ALTER TABLE {prefix}`{name.replace('`', '``')}` AUTO_INCREMENT = {value};"
        for name, value in sorted(next_values.items())
    ]


def _next_id(connection, insert: str) -> int:  # type: ignore[no-untyped-def]
    return int(connection.execute(text(insert)).lastrowid)


def test_generates_the_expected_script_and_executes_nothing(scratch: Scratch, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="util_bbdd.connection.mariadb.update_auto_increment"):
        statements = UpdateAutoIncrement(scratch.engine).salida_sql()

    assert statements == _expected(scratch)
    if "float_auto" in scratch.created_optional:
        assert "no entero" in caplog.text  # AUTO_INCREMENT sobre FLOAT: omitida con aviso

    # Generar no modifica nada: el contador de `orders` sigue donde estaba (101), no en 42.
    with scratch.engine.connect() as connection:
        assert _next_id(connection, "INSERT INTO orders (note) VALUES ('n')") == 101


def test_the_schema_parameter_works_from_a_connection_to_another_database(scratch: Scratch) -> None:
    statements = UpdateAutoIncrement(scratch.admin, schema=scratch.schema).salida_sql()
    assert statements == _expected(scratch, scratch.schema)


def test_executing_the_script_leaves_each_counter_at_max_plus_one(scratch: Scratch) -> None:
    with scratch.engine.connect() as connection:
        for statement in UpdateAutoIncrement(scratch.engine).salida_sql():
            connection.execute(text(statement))

        assert _next_id(connection, "INSERT INTO orders (note) VALUES ('n')") == 42  # antes: 101
        assert _next_id(connection, "INSERT INTO empty_table () VALUES ()") == 1
        assert _next_id(connection, "INSERT INTO composite (tenant) VALUES (3)") == 10
        assert _next_id(connection, "INSERT INTO `order` () VALUES ()") == 4
        assert _next_id(connection, "INSERT INTO `we``ird` () VALUES ()") == 8
        assert _next_id(connection, "INSERT INTO big_ids () VALUES ()") == _BIG + 1
        if "versioned" in scratch.created_optional:
            assert _next_id(connection, "INSERT INTO versioned (v) VALUES (2)") == 12
