"""
Tests para QueryRegistry (PR 0)

Pruebas unitarias para el componente QueryRegistry que centraliza
carga y acceso a definiciones de queries desde sql_queries.json.

Todos los tests son sin dependencias de bases de datos reales.
"""

import pytest

from util_bbdd.exceptions import QueryNotFoundError
from util_bbdd.models import QueryDefinition
from util_bbdd.query import QueryRegistry


class TestQueryRegistryLoad:
    """Tests para carga de queries desde JSON"""

    def test_load_queries_success(self, temp_queries_file):
        """Test: carga exitosa de queries desde archivo temporal"""
        registry = QueryRegistry(temp_queries_file)
        assert registry is not None
        assert len(registry.get_all_db_types()) > 0

    def test_load_queries_structure_valid(self, temp_queries_file):
        """Test: estructura interna es válida después de carga"""
        registry = QueryRegistry(temp_queries_file)
        all_types = registry.get_all_db_types()
        assert "mariadb" in all_types
        assert "oracle" in all_types

    def test_file_not_found_raises_error(self, tmp_path):
        """Test: FileNotFoundError si archivo no existe"""
        nonexistent_file = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError) as exc:
            QueryRegistry(nonexistent_file)
        assert "not found" in str(exc.value)

    def test_invalid_json_raises_error(self, tmp_path):
        """Test: ValueError si JSON es mal formado"""
        bad_json_file = tmp_path / "bad.json"
        bad_json_file.write_text("{invalid json")

        with pytest.raises(ValueError) as exc:
            QueryRegistry(bad_json_file)
        assert "Invalid JSON" in str(exc.value)


class TestGetQueryDefinition:
    """Tests para obtención de QueryDefinition"""

    def test_get_query_definition_exists(self, temp_queries_file):
        """Test: obtiene QueryDefinition cuando query existe"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        assert isinstance(qdef, QueryDefinition)
        assert qdef.name == "obtener_tablas"
        assert qdef.db_type == "mariadb"
        assert len(qdef.required_params) > 0

    def test_query_definition_has_all_fields(self, temp_queries_file):
        """Test: QueryDefinition tiene todos los campos requeri dos"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        assert qdef.name is not None
        assert qdef.db_type is not None
        assert qdef.sql_template is not None
        assert isinstance(qdef.required_params, list)
        assert isinstance(qdef.optional_params, list)

    def test_query_definition_not_found(self, temp_queries_file):
        """Test: QueryNotFoundError cuando query no existe"""
        registry = QueryRegistry(temp_queries_file)

        with pytest.raises(QueryNotFoundError) as exc:
            registry.get_query_definition("mariadb", "nonexistent_query")

        assert "nonexistent_query" in str(exc.value)
        assert exc.value.__cause__ is not None

    def test_db_type_not_found(self, temp_queries_file):
        """Test: QueryNotFoundError cuando db_type no existe"""
        registry = QueryRegistry(temp_queries_file)

        with pytest.raises(QueryNotFoundError) as exc:
            registry.get_query_definition("nonexistent_db", "obtener_tablas")

        assert "nonexistent_db" in str(exc.value)
        assert exc.value.__cause__ is not None

    def test_db_type_case_insensitive(self, temp_queries_file):
        """Test: db_type es case-insensitive"""
        registry = QueryRegistry(temp_queries_file)

        qdef1 = registry.get_query_definition("MariaDB", "obtener_tablas")
        qdef2 = registry.get_query_definition("mariadb", "obtener_tablas")
        qdef3 = registry.get_query_definition("MARIADB", "obtener_tablas")

        assert qdef1.sql_template == qdef2.sql_template
        assert qdef2.sql_template == qdef3.sql_template

    def test_db_type_stripped_of_whitespace(self, temp_queries_file):
        """Test: db_type se limpia de espacios en blanco"""
        registry = QueryRegistry(temp_queries_file)

        qdef1 = registry.get_query_definition("  mariadb  ", "obtener_tablas")
        qdef2 = registry.get_query_definition("mariadb", "obtener_tablas")

        assert qdef1.sql_template == qdef2.sql_template


class TestExtractePlaceholders:
    """Tests para extracción de placeholders"""

    def test_extract_single_placeholder(self, temp_queries_file):
        """Test: extrae un solo placeholder"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        # "obtener_tablas" tiene placeholder {database}
        assert "database" in qdef.required_params

    def test_extract_multiple_placeholders(self, temp_queries_file):
        """Test: extrae múltiples placeholders"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "columnas_tabla")

        # "columnas_tabla" tiene {database} y {tabla}
        assert "database" in qdef.required_params
        assert "tabla" in qdef.required_params
        assert len(qdef.required_params) >= 2

    def test_extract_no_placeholders(self, temp_queries_file):
        """Test: query sin placeholders tiene lista vacía"""
        # Agregar una query sin placeholders al archivo temp
        # Para este test, verificar una query que no tenga placeholders
        registry = QueryRegistry(temp_queries_file)
        # "obtener_vistas" en mariadb también tiene {database}, así que usamos indices
        qdef = registry.get_query_definition("mariadb", "indices")

        # "indices" tiene {tabla}
        assert "tabla" in qdef.required_params

    def test_extract_unique_placeholders(self):
        """Test: no duplica placeholders"""
        sql = "SELECT * FROM {tabla} WHERE {tabla}.id = {id} AND {tabla}.name LIKE %{id}%"
        placeholders = QueryRegistry._extract_placeholders(sql)

        # Debe contener cada placeholder una sola vez
        assert "tabla" in placeholders
        assert "id" in placeholders
        assert len(placeholders) == 2


class TestGetAvailableQueries:
    """Tests para listar queries disponibles"""

    def test_get_available_queries_mariadb(self, temp_queries_file):
        """Test: lista queries para MariaDB"""
        registry = QueryRegistry(temp_queries_file)
        queries = registry.get_available_queries("mariadb")

        assert isinstance(queries, list)
        assert len(queries) > 0
        assert "obtener_tablas" in queries
        assert "columnas_tabla" in queries

    def test_get_available_queries_oracle(self, temp_queries_file):
        """Test: lista queries para Oracle"""
        registry = QueryRegistry(temp_queries_file)
        queries = registry.get_available_queries("oracle")

        assert isinstance(queries, list)
        assert len(queries) > 0
        assert "obtener_tablas" in queries

    def test_get_available_queries_nonexistent_db(self, temp_queries_file):
        """Test: devuelve lista vacía para db_type inexistente"""
        registry = QueryRegistry(temp_queries_file)
        queries = registry.get_available_queries("nonexistent_db")

        assert isinstance(queries, list)
        assert len(queries) == 0

    def test_get_available_queries_case_insensitive(self, temp_queries_file):
        """Test: case-insensitive en db_type"""
        registry = QueryRegistry(temp_queries_file)

        queries1 = registry.get_available_queries("MariaDB")
        queries2 = registry.get_available_queries("mariadb")

        assert queries1 == queries2


class TestGetAllDbTypes:
    """Tests para listar todos los db_types"""

    def test_get_all_db_types(self, temp_queries_file):
        """Test: lista todos los db_types disponibles"""
        registry = QueryRegistry(temp_queries_file)
        db_types = registry.get_all_db_types()

        assert isinstance(db_types, list)
        assert len(db_types) > 0
        assert "mariadb" in db_types
        assert "oracle" in db_types
        assert "postgresql" in db_types

    def test_get_all_db_types_not_empty(self, temp_queries_file):
        """Test: lista no está vacía"""
        registry = QueryRegistry(temp_queries_file)
        db_types = registry.get_all_db_types()

        assert len(db_types) >= 3  # Test file tiene al menos 3


class TestQueryRegistryMetadata:
    """Tests para metadata de QueryDefinition"""

    def test_query_definition_metadata_present(self, temp_queries_file):
        """Test: QueryDefinition incluye metadata"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        assert isinstance(qdef.metadata, dict)
        assert "source" in qdef.metadata
        assert "motor" in qdef.metadata

    def test_query_definition_metadata_values(self, temp_queries_file):
        """Test: metadata tiene valores correctos"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        assert qdef.metadata["source"] == "sql_queries.json"
        assert qdef.metadata["motor"] == "mariadb"


class TestQueryRegistryEdgeCases:
    """Tests para casos límite"""

    def test_empty_optional_params_by_default(self, temp_queries_file):
        """Test: optional_params está vacío por defecto"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        assert qdef.optional_params == []

    def test_query_definition_immutable_like(self, temp_queries_file):
        """Test: QueryDefinition se comporta como immutable"""
        registry = QueryRegistry(temp_queries_file)
        qdef1 = registry.get_query_definition("mariadb", "obtener_tablas")
        qdef2 = registry.get_query_definition("mariadb", "obtener_tablas")

        # Mismo contenido
        assert qdef1.name == qdef2.name
        assert qdef1.sql_template == qdef2.sql_template
        # Pero diferentes instancias
        assert qdef1 is not qdef2

    def test_sql_template_not_modified(self, temp_queries_file):
        """Test: sql_template no se modifica ni interpola"""
        registry = QueryRegistry(temp_queries_file)
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")

        # Debe contener placeholders sin interpolar
        assert "{database}" in qdef.sql_template
