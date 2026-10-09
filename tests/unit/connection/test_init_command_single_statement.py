"""v0.40.2: ``init_command`` de MariaDB con varias sentencias y campos de ``DatabaseConfigurationError``.

MariaDB ejecuta ``init_command`` como una sola sentencia (también por ``cursor.execute``): con
``"SET SESSION character_set_server = utf8mb4; SET NAMES utf8mb4;"`` el servidor respondía con un error de sintaxis
«near 'SET NAMES utf8mb4'» que no nombraba el parámetro (comprobado con Connector/Python 1.1.14 y MariaDB 11.4).
Ahora se rechaza al validar ``conn_params``. Además, el error inesperado de ``SyncDatabaseManager.__init__`` guardaba
el texto del error en ``db_type`` y el motor en ``operation``.
"""

from __future__ import annotations

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseConfigurationError, ValidationError
from util_bbdd.connection.config import MariaDBConnectionConfig

pytestmark = pytest.mark.unit

_BASE: dict[str, object] = {"host": "db", "user": "app", "password": "pwd", "database": "ventas"}


@pytest.mark.parametrize(
    "init_command",
    [
        "SET SESSION character_set_server = utf8mb4; SET NAMES utf8mb4;",
        "SET NAMES utf8mb4;SET time_zone = '+00:00'",
        "SET @a = 1 ;  SET @b = 2",
    ],
)
def test_init_command_with_several_statements_is_rejected(init_command: str) -> None:
    with pytest.raises(ValueError, match="init_command admite una sola sentencia"):
        MariaDBConnectionConfig.from_params({**_BASE, "init_command": init_command})


@pytest.mark.parametrize(
    "init_command",
    [
        "SET NAMES utf8mb4",
        "SET NAMES utf8mb4;",
        "SET NAMES utf8mb4 ; ; ",
        "SET SESSION character_set_server = utf8mb4, NAMES utf8mb4",
        "SET @sep = 'a;b', time_zone = '+00:00'",
        'SET @sep = "x;y"',
        "SET @sep = 'it\\'s; ok'",
        "SET @`col;name` = 1",
    ],
)
def test_single_statement_init_command_is_accepted(init_command: str) -> None:
    config = MariaDBConnectionConfig.from_params({**_BASE, "init_command": init_command})
    assert config.init_command == init_command.strip()


def test_manager_rejects_several_statements_before_connecting() -> None:
    params = {**_BASE, "init_command": "SET SESSION character_set_server = utf8mb4; SET NAMES utf8mb4;"}
    with pytest.raises(ValidationError, match="init_command"):
        SyncDatabaseManager("mariadb", params)


def test_unexpected_init_error_keeps_db_type_and_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_self: SyncDatabaseManager) -> None:
        raise RuntimeError("fallo del driver")

    monkeypatch.setattr(SyncDatabaseManager, "_connect", _boom)

    with pytest.raises(DatabaseConfigurationError) as info:
        SyncDatabaseManager("sqlite", {"database": ":memory:"}, use_pool=False)

    assert info.value.db_type == "sqlite"
    assert info.value.operation == "UNKNOWN"
    assert str(info.value).count("fallo del driver") == 1
