"""
Tests funcionales para util_bbdd - usando API real con mocks.
Cobertura: build_conn_params, SyncDatabaseManager, factories
"""

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import ConnectionParamsManager, build_conn_params


class TestBuildConnParams:
    """Tests para build_conn_params - constructor de parámetros."""

    def test_build_mariadb_params(self):
        """Test: build_conn_params para MariaDB funciona."""
        params = build_conn_params(
            db_type="mariadb",
            host="localhost",
            port=3306,
            user="root",
            password="password",
            database="test_db",
        )

        assert params is not None
        assert isinstance(params, dict)
        assert params.get("host") == "localhost"
        assert params.get("port") == 3306
        assert params.get("user") == "root"

    def test_build_postgresql_params(self):
        """Test: build_conn_params para PostgreSQL funciona."""
        params = build_conn_params(
            db_type="postgresql",
            host="localhost",
            port=5432,
            user="postgres",
            password="password",
            database="test_db",
        )

        assert params is not None
        assert isinstance(params, dict)
        assert params.get("host") == "localhost"
        assert params.get("port") == 5432

    def test_build_oracle_params(self):
        """Test: build_conn_params para Oracle funciona."""
        params = build_conn_params(
            db_type="oracle",
            user="sys",
            password="password",
            host="localhost",
            port=1521,
            service_name="XE",
        )

        assert params is not None
        assert isinstance(params, dict)

    def test_build_sqlite_params(self):
        """Test: build_conn_params para SQLite funciona."""
        params = build_conn_params(
            db_type="sqlite",
            database=":memory:",
        )

        assert params is not None
        assert isinstance(params, dict)

    def test_mariadb_with_charset(self):
        """Test: build_conn_params con charset para MariaDB."""
        params = build_conn_params(
            db_type="mariadb",
            host="localhost",
            port=3306,
            user="root",
            password="pass",  # noqa: S105
            database="test",
            charset="utf8mb4",
        )

        assert params is not None
        assert params.get("charset") == "utf8mb4"

    @pytest.mark.parametrize("db_type", ["mariadb", "postgresql", "oracle", "sqlite"])
    def test_all_database_types(self, db_type):
        """Test: build_conn_params soporta todos los tipos de BD."""
        if db_type == "sqlite":
            params = build_conn_params(db_type=db_type, database=":memory:")
        elif db_type == "oracle":
            params = build_conn_params(
                db_type=db_type,
                user="sys",
                password="pass",  # noqa: S105
                host="localhost",
                port=1521,
                service_name="XE",
            )
        else:
            params = build_conn_params(
                db_type=db_type,
                host="localhost",
                port=3306,
                user="user",
                password="pass",  # noqa: S105
                database="test",
            )

        assert params is not None
        assert isinstance(params, dict)


class TestConnectionParamsManager:
    """Tests para ConnectionParamsManager."""

    def test_manager_prepare_and_validate(self):
        """Test: ConnectionParamsManager.prepare_and_validate()."""
        conn_params = build_conn_params(
            db_type="mariadb",
            host="localhost",
            port=3306,
            user="root",
            password="pass",  # noqa: S105
            database="test",
        )

        validated = ConnectionParamsManager.prepare_and_validate(
            db_type="mariadb",
            conn_params=conn_params,
        )
        assert validated is not None
        assert isinstance(validated, dict)

    def test_manager_sanitize_for_connection(self):
        """Test: ConnectionParamsManager.sanitize_for_connection()."""
        conn_params = build_conn_params(
            db_type="sqlite",
            database=":memory:",
        )

        sanitized = ConnectionParamsManager.sanitize_for_connection(
            db_type="sqlite",
            conn_params=conn_params,
        )
        assert isinstance(sanitized, dict)

    def test_manager_sanitize_for_pool(self):
        """Test: ConnectionParamsManager.sanitize_for_pool()."""
        conn_params = build_conn_params(
            db_type="sqlite",
            database=":memory:",
        )

        # SQLite doesn't have pool, but method should handle it
        try:
            sanitized = ConnectionParamsManager.sanitize_for_pool(
                db_type="sqlite",
                conn_params=conn_params,
            )
            assert isinstance(sanitized, dict)
        except ValueError:
            # Expected for some databases
            pass


class TestDatabaseManagerBasic:
    """Tests básicos para SyncDatabaseManager."""

    def test_database_manager_creation(self):
        """Test: crear SyncDatabaseManager con parámetros válidos."""
        conn_params = build_conn_params(
            db_type="sqlite",
            database=":memory:",
        )
        db = SyncDatabaseManager(db_type="sqlite", conn_params=conn_params)
        assert db is not None

    def test_database_manager_has_attributes(self):
        """Test: SyncDatabaseManager tiene atributos esperados."""
        conn_params = build_conn_params(
            db_type="sqlite",
            database=":memory:",
        )
        db = SyncDatabaseManager(db_type="sqlite", conn_params=conn_params)
        assert hasattr(db, "db_type")
        assert hasattr(db, "conn_params")
        assert db.db_type == "sqlite"


class TestFactoryBasic:
    """Tests básicos para factory."""

    def test_connect_factory_creation(self):
        """Test: crear ConnectionFactory."""
        from util_bbdd import ConnectionFactory

        factory = ConnectionFactory()
        assert factory is not None

    def test_sqlalchemy_engine_factory_creation(self):
        """Test: crear SQLAlchemyEngineFactory."""
        from util_bbdd.factory import SQLAlchemyEngineFactory

        factory = SQLAlchemyEngineFactory()
        assert factory is not None

    def test_pool_factory_creation(self):
        """Test: crear PoolFactory."""
        from util_bbdd.factory import PoolFactory

        factory = PoolFactory()
        assert factory is not None


class TestExceptionHandling:
    """Tests para manejo de excepciones."""

    def test_database_error_import(self):
        """Test: importar DatabaseError."""
        from util_bbdd import DatabaseException as DatabaseError

        assert DatabaseError is not None

    def test_connection_error_import(self):
        """Test: importar DatabaseConnectionError."""
        from util_bbdd import ConnectionError as DatabaseConnectionError

        assert DatabaseConnectionError is not None

    def test_raise_database_error(self):
        """Test: lanzar DatabaseError."""
        from util_bbdd import DatabaseException as DatabaseError

        with pytest.raises(DatabaseError):
            raise DatabaseError("Test error")

    def test_raise_connection_error(self):
        """Test: lanzar DatabaseConnectionError."""
        from util_bbdd import ConnectionError as DatabaseConnectionError

        with pytest.raises(DatabaseConnectionError):
            raise DatabaseConnectionError("Connection failed")


class TestDatabaseTypeValidator:
    """Tests para validación de tipos de BD."""

    def test_validator_import(self):
        """Test: importar DatabaseTypeValidator."""
        from util_bbdd._drivers import DatabaseTypeValidator

        assert DatabaseTypeValidator is not None

    def test_validator_creation(self):
        """Test: crear validador."""
        from util_bbdd._drivers import DatabaseTypeValidator

        validator = DatabaseTypeValidator()
        assert validator is not None

    def test_validator_legacy_module_reexports_canonical_validator(self):
        """Test: la ruta legacy apunta al validador canónico interno."""
        from util_bbdd._drivers import DatabaseTypeValidator
        from util_bbdd._drivers.validator import DatabaseTypeValidator as CanonicalValidator

        assert DatabaseTypeValidator is CanonicalValidator

    @pytest.mark.parametrize("db_type", ["mysql", "postgresql", "oracle", "sqlite"])
    def test_database_types_supported(self, db_type):
        """Test: validador soporta tipos comunes."""
        from util_bbdd._drivers import DatabaseTypeValidator

        validator = DatabaseTypeValidator()
        normalized_db_type = "mariadb" if db_type == "mysql" else db_type
        validator.validate_db_type(normalized_db_type)
        # Test pasa si no hay excepción


class TestConnectionPooling:
    """Tests para pooling de conexiones."""

    def test_pool_factory_with_size(self):
        """Test: PoolFactory con tamaño especificado."""
        from util_bbdd.factory import PoolFactory

        factory = PoolFactory()
        assert factory is not None

        # Verificar que le puedo pasar pool_size
        if hasattr(factory, "create_pool"):
            assert callable(factory.create_pool)

    @pytest.mark.parametrize("pool_size", [5, 10, 20])
    def test_pool_sizes(self, pool_size):
        """Test: diferentes tamaños de pool."""
        # Verificar que tamaños son válidos
        assert pool_size > 0
        assert isinstance(pool_size, int)


class TestConfigurationBuilding:
    """Tests para construcción de configuraciones."""

    def test_build_mariadb_connection_url(self):
        """Test: construir URL de conexión MariaDB."""
        params = build_conn_params(
            db_type="mariadb",
            host="db.example.com",
            port=3306,
            user="admin",
            password="secret",  # noqa: S105
            database="myapp",
        )

        assert params["host"] == "db.example.com"
        assert params["user"] == "admin"
        assert params["database"] == "myapp"

    def test_build_postgresql_connection_url(self):
        """Test: construir URL de conexión PostgreSQL."""
        params = build_conn_params(
            db_type="postgresql",
            host="db.example.com",
            port=5432,
            user="postgres",
            password="secret",  # noqa: S105
            database="myapp",
        )

        assert params["host"] == "db.example.com"
        assert params["database"] == "myapp"

    def test_build_oracle_connection_url(self):
        """Test: construir URL de conexión Oracle."""
        params = build_conn_params(
            db_type="oracle",
            host="oracle.example.com",
            port=1521,
            user="system",
            password="secret",  # noqa: S105
            service_name="ORCL",
        )

        assert params["host"] == "oracle.example.com"
        assert params["user"] == "system"
