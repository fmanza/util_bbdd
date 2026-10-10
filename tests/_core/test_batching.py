"""Tests para batch resolver (_core/batching/)."""

from __future__ import annotations

from sqlalchemy import create_mock_engine

from util_bbdd._core.batching import resolve_write_batch_size


class TestResolveWriteBatchSize:
    """Tests para resolve_write_batch_size()."""

    def test_postgresql_default_batch_no_commit_cadence(self) -> None:
        """PostgreSQL con commit_every_n_chunks=None debe devolver max(chunk_size, 20_000)."""
        result = resolve_write_batch_size(db_type="postgresql", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 20_000

    def test_postgresql_default_batch_with_large_chunk_size(self) -> None:
        """PostgreSQL con chunk_size > 20_000 debe devolver chunk_size."""
        result = resolve_write_batch_size(db_type="postgresql", chunk_size=50_000, commit_every_n_chunks=None)
        assert result == 50_000

    def test_postgresql_with_commit_cadence(self) -> None:
        """PostgreSQL con commit_every_n_chunks != None debe devolver chunk_size (no optimizar)."""
        result = resolve_write_batch_size(db_type="postgresql", chunk_size=5000, commit_every_n_chunks=10000)
        assert result == 5000

    def test_mysql_default_batch(self) -> None:
        """MySQL debe devolver chunk_size (sin optimización COPY de PostgreSQL)."""
        result = resolve_write_batch_size(db_type="mysql", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 5000

    def test_oracle_default_batch(self) -> None:
        """Oracle debe devolver chunk_size."""
        result = resolve_write_batch_size(db_type="oracle", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 5000

    def test_sqlserver_default_batch(self) -> None:
        """SQL Server debe devolver chunk_size."""
        result = resolve_write_batch_size(db_type="sqlserver", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 5000

    def test_sqlite_default_batch(self) -> None:
        """SQLite debe devolver chunk_size."""
        result = resolve_write_batch_size(db_type="sqlite", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 5000

    def test_mariadb_default_batch(self) -> None:
        """MariaDB debe devolver chunk_size (no es PostgreSQL)."""
        result = resolve_write_batch_size(db_type="mariadb", chunk_size=5000, commit_every_n_chunks=None)
        assert result == 5000

    def test_with_target_engine_postgresql(self) -> None:
        """Si se pasa target_engine, debe usarse engine.dialect.name."""
        # Crear un engine PostgreSQL (en-memoria, URL ficticia; no se ejecuta SQL)
        engine = create_mock_engine("postgresql+psycopg2://", executor=lambda *a, **kw: None)
        result = resolve_write_batch_size(
            db_type="mysql", chunk_size=5000, commit_every_n_chunks=None, target_engine=engine
        )
        # Debe reconocer PostgreSQL del engine, no del db_type
        assert result == 20_000

    def test_with_target_engine_mysql(self) -> None:
        """Si se pasa target_engine MySQL, debe devolver chunk_size."""
        engine = create_mock_engine("mysql+pymysql://", executor=lambda *a, **kw: None)
        result = resolve_write_batch_size(
            db_type="postgresql", chunk_size=5000, commit_every_n_chunks=None, target_engine=engine
        )
        # Debe reconocer MySQL del engine, ignorar PostgreSQL del db_type
        assert result == 5000

    def test_none_db_type_with_engine(self) -> None:
        """Si db_type es None pero target_engine se pasa, debe usar engine.dialect.name."""
        engine = create_mock_engine("postgresql+psycopg2://", executor=lambda *a, **kw: None)
        result = resolve_write_batch_size(
            db_type=None, chunk_size=5000, commit_every_n_chunks=None, target_engine=engine
        )
        assert result == 20_000
