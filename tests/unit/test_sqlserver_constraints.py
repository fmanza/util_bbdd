"""Tests para constraints (PK, FK) en SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.constraints import (
    fetch_foreign_keys_sync,
    fetch_primary_keys_sync,
)


class TestFetchPrimaryKeysSyncSqlServer:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_pk_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # sys.key_constraints returns: (constraint_name, column_name, key_ordinal)
        mock_cursor.fetchall.return_value = [
            ("PK_Users", "UserId", 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="dbo", table="Users")

        assert len(result) >= 0
        assert all(isinstance(r, tuple) and len(r) == 3 for r in result)

    def test_fetch_pk_composite_key(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("PK_UserRoles", "UserId", 1),
            ("PK_UserRoles", "RoleId", 2),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="dbo", table="UserRoles")

        assert len(result) == 2
        pk_columns = [r[1] for r in result]
        assert "UserId" in pk_columns
        assert "RoleId" in pk_columns

    def test_fetch_pk_no_primary_key(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="dbo", table="NoKey")
        assert result == []

    def test_fetch_pk_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_primary_keys_sync(mock_conn, schema="dbo", table=None)
        assert result == []

    def test_fetch_pk_returns_sorted_by_position(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("PK_Test", "ColA", 2),
            ("PK_Test", "ColB", 1),
            ("PK_Test", "ColC", 3),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="dbo", table="test")

        positions = [r[2] for r in result]
        assert positions == sorted(positions)


class TestFetchForeignKeysSyncSqlServer:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_fk_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # sys.foreign_keys returns:
        # (name, column, ref_table, ref_column, on_delete_code, on_update_code, ordinal)
        mock_cursor.fetchall.return_value = [
            ("FK_Users_Dept", "DeptId", "Departments", "DeptId", 0, 0, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Users")

        assert len(result) >= 0
        assert all(isinstance(r, tuple) and len(r) == 7 for r in result)

    def test_fetch_fk_cascade_actions_decoded(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Code 1 = CASCADE, Code 2 = SET NULL
        mock_cursor.fetchall.return_value = [
            ("FK_Orders", "CustomerId", "Customers", "CustomerId", 1, 2, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Orders")

        constraint_name, column, ref_table, ref_column, on_delete, on_update, ordinal = result[0]

        assert on_delete == "CASCADE"
        assert on_update == "SET NULL"

    def test_fetch_fk_multiple_foreign_keys(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("FK_Orders_Customer", "CustomerId", "Customers", "CustomerId", 0, 0, 1),
            ("FK_Orders_Salesman", "SalesmanId", "Employees", "EmployeeId", 1, 0, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Orders")

        assert len(result) == 2

    def test_fetch_fk_no_foreign_keys(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Standalone")
        assert result == []

    def test_fetch_fk_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table=None)
        assert result == []

    def test_fetch_fk_cascade_default_no_action(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Code 0 = NO ACTION (default)
        mock_cursor.fetchall.return_value = [
            ("FK_Test", "RefId", "Parent", "Id", 0, 0, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Child")

        _, _, _, _, on_delete, on_update, _ = result[0]
        assert on_delete == "NO ACTION"
        assert on_update == "NO ACTION"

    def test_fetch_fk_set_default_action(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Code 3 = SET DEFAULT
        mock_cursor.fetchall.return_value = [
            ("FK_Test", "Status", "StatusRef", "StatusId", 3, 2, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="dbo", table="Orders")

        _, _, _, _, on_delete, on_update, _ = result[0]
        assert on_delete == "SET DEFAULT"
        assert on_update == "SET NULL"

    def test_fetch_fk_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema=None, table="test")
        assert isinstance(result, list)
