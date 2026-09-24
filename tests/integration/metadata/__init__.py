"""Tests de integración de introspección de metadatos por motor.

Este ``__init__.py`` hace que pytest importe los subpaquetes como ``integration.metadata.<motor>``. Sin él, con el modo
de importación por defecto (``prepend``), ``tests/integration/metadata`` entraba en ``sys.path`` y ``mariadb/`` se
importaba como el paquete de primer nivel ``mariadb``, tapando al driver del mismo nombre en el resto de la suite.
"""
