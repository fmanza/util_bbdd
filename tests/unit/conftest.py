"""Fixtures compartidas para tests unitarios."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_manager_with_logger() -> MagicMock:
    """Proporciona un MagicMock configurado con logger."""
    manager = MagicMock()
    manager.logger = logging.getLogger(__name__)
    manager.db_cache = MagicMock()
    return manager


@pytest.fixture
def mock_manager_with_connection() -> MagicMock:
    """Proporciona un MagicMock con connection y logger configurados."""
    manager = MagicMock()
    manager.logger = logging.getLogger(__name__)
    manager.db_cache = MagicMock()
    manager.connection = MagicMock()
    manager.connection.execute.return_value = MagicMock(fetchall=lambda: [])
    return manager


