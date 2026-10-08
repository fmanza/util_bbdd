"""P1 M1 de drivers-connections-audit (FASE 1, 2026-10-08).

``charset`` e ``init_command`` eran independientes: con ``charset="latin1"`` se seguía ejecutando
``SET NAMES utf8mb4`` (sesión utf8mb4, driver decodificando latin1 → mojibake). ``charset`` tampoco se validaba
antes de llegar al driver y al ``SET NAMES``.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.connection.config import MariaDBConnectionConfig

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_default_init_command_follows_charset() -> None:
    config = MariaDBConnectionConfig.from_params({**BASE, "charset": "latin1"})

    assert config.charset == "latin1"
    assert config.init_command == "SET NAMES latin1"


def test_explicit_init_command_wins_over_charset() -> None:
    config = MariaDBConnectionConfig.from_params(
        {**BASE, "charset": "latin1", "init_command": "SET NAMES latin1 COLLATE latin1_spanish_ci"}
    )

    assert config.init_command == "SET NAMES latin1 COLLATE latin1_spanish_ci"


@pytest.mark.parametrize("charset", ["utf8mb4; DROP TABLE t", "../../etc/passwd", "utf8 mb4", "latin1'"])
def test_invalid_charset_is_rejected(charset: str) -> None:
    with pytest.raises(ValueError, match="charset"):
        MariaDBConnectionConfig.from_params({**BASE, "charset": charset})
