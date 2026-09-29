"""
MySQL Query Validator
"""

from .mariadb_validator import MariaDBValidator


class MySQLValidator(MariaDBValidator):
    """Validador de queries para MySQL.

    Mismas reglas que MariaDB: el catálogo de queries de MySQL usa los mismos parámetros e identificadores.
    """

    db_type = "mysql"
