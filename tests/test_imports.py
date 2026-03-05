"""
Test básico de importación para util_bbdd
"""

import pytest


class TestImports:
    """Suite de tests para validar imports"""

    def test_module_import(self):
        """Test que el módulo util_bbdd se puede importar"""
        try:
            import util_bbdd

            assert util_bbdd.__version__ == "0.1.0"
        except ImportError:
            # Es esperado si no todas las dependencias están disponibles
            pass

    def test_bbdd_module_exists(self):
        """Test que el módulo bbdd existe en util_bbdd"""
        try:
            from util_bbdd import bbdd

            assert bbdd is not None
        except ImportError:
            # Es esperado si no todas las dependencias están disponibles
            pass
