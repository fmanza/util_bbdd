"""Unit tests for finalization safety (PythonFinalizationError prevention).

Tests verify that sys.is_finalizing() detection prevents thread creation
during Python interpreter shutdown.
"""

from __future__ import annotations

from unittest import mock

import pytest

from util_bbdd.connection.close import run_close_operation_sync


class TestFinalizationSafety:
    """Tests for shutdown-safe close operations."""

    def test_run_close_operation_sync_normal_mode_with_timeout(self) -> None:
        """Verify timeout mechanism works in normal mode (not finalizing)."""
        action_called = False

        def action() -> None:
            nonlocal action_called
            action_called = True

        # Normal mode (not finalizing): should use threading
        with mock.patch("sys.is_finalizing", return_value=False):
            run_close_operation_sync(
                action=action,
                timeout_seconds=1.0,
                action_name="test_action",
                db_type="test",
            )
        assert action_called is True

    def test_run_close_operation_sync_finalization_mode_with_timeout(self) -> None:
        """Verify no threading during finalization (sys.is_finalizing()=True)."""
        action_called = False

        def action() -> None:
            nonlocal action_called
            action_called = True

        # Finalization mode: should execute directly without threading
        with mock.patch("sys.is_finalizing", return_value=True):
            run_close_operation_sync(
                action=action,
                timeout_seconds=1.0,
                action_name="test_action",
                db_type="test",
            )
        assert action_called is True

    def test_run_close_operation_sync_finalization_skips_timeout(self) -> None:
        """Verify timeout is ignored during finalization."""
        import threading

        def slow_action() -> None:
            # This would timeout in 0.1s if timeout was enforced
            threading.Event().wait(timeout=0.5)

        # In finalization mode, this should complete without timeout
        with mock.patch("sys.is_finalizing", return_value=True):
            # Should NOT raise PoolTimeoutError
            run_close_operation_sync(
                action=slow_action,
                timeout_seconds=0.01,  # Very short timeout (ignored during finalization)
                action_name="slow_close",
                db_type="test",
            )

    def test_run_close_operation_sync_finalization_with_exception(self) -> None:
        """Verify exceptions are propagated even during finalization."""

        def failing_action() -> None:
            raise ValueError("Test error in finalization")

        with mock.patch("sys.is_finalizing", return_value=True):
            with pytest.raises(ValueError, match="Test error in finalization"):
                run_close_operation_sync(
                    action=failing_action,
                    timeout_seconds=1.0,
                    action_name="failing_close",
                    db_type="test",
                )

    def test_run_close_operation_sync_no_timeout_always_works(self) -> None:
        """Verify timeout_seconds=None works regardless of finalization state."""
        action_called = False

        def action() -> None:
            nonlocal action_called
            action_called = True

        # None timeout in normal mode
        with mock.patch("sys.is_finalizing", return_value=False):
            run_close_operation_sync(
                action=action,
                timeout_seconds=None,
                action_name="test_action",
                db_type="test",
            )
        assert action_called is True

        action_called = False

        # None timeout in finalization mode
        with mock.patch("sys.is_finalizing", return_value=True):
            run_close_operation_sync(
                action=action,
                timeout_seconds=None,
                action_name="test_action",
                db_type="test",
            )
        assert action_called is True

    def test_run_close_operation_sync_normal_mode_respects_timeout(self) -> None:
        """Verify normal mode still enforces timeout (regression check)."""
        from util_bbdd._core.exceptions import PoolTimeoutError

        def slow_action() -> None:
            import time

            time.sleep(0.5)  # Sleep longer than timeout

        with mock.patch("sys.is_finalizing", return_value=False):
            with pytest.raises(PoolTimeoutError):
                run_close_operation_sync(
                    action=slow_action,
                    timeout_seconds=0.01,  # 10ms timeout
                    action_name="slow_close",
                    db_type="test",
                )


class TestPostgresqlPoolFinalizationSafety:
    """Tests for PythonFinalizationError prevention in PoolConnection.close()."""

    def test_pool_close_skips_psycopg_close_during_finalization(self) -> None:
        """pool.close() must not call pool_ref.close() during interpreter shutdown."""
        import logging

        from util_bbdd.connection.postgresql.pool_connection_postgresql import PoolConnection

        close_called = False

        class _TrackingPool:
            def close(self, **kwargs: object) -> None:
                nonlocal close_called
                close_called = True

        pool = object.__new__(PoolConnection)
        pool.logger = logging.getLogger(__name__)
        pool._closed = False
        pool._close_timeout_seconds = 10.0
        pool.pool = _TrackingPool()

        with mock.patch("sys.is_finalizing", return_value=True):
            pool.close(timeout_seconds=10.0, force=False)

        assert close_called is False, "pool_ref.close() should NOT be called during finalization"
        assert pool.pool is None

    def test_pool_close_calls_psycopg_close_in_normal_mode(self) -> None:
        """pool.close() must call pool_ref.close() when not finalizing (regression)."""
        import logging

        from util_bbdd.connection.postgresql.pool_connection_postgresql import PoolConnection

        close_called = False

        class _TrackingPool:
            def close(self, timeout: float | None = None) -> None:
                nonlocal close_called
                close_called = True

        pool = object.__new__(PoolConnection)
        pool.logger = logging.getLogger(__name__)
        pool._closed = False
        pool._close_timeout_seconds = None
        pool.pool = _TrackingPool()

        with mock.patch("sys.is_finalizing", return_value=False):
            pool.close(timeout_seconds=None, force=False)

        assert close_called is True, "pool_ref.close() MUST be called during normal shutdown"
        assert pool.pool is None
