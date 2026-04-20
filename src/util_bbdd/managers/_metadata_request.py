"""Construcción de requests para fetching de metadata (patrón: Builder)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetadataFetchRequest:
    """Describe una consulta de metadata reusable para managers sync/async."""

    query_name: str
    params: dict[str, Any]
    error_message: str
    table_name: str | None = None
    expect_one: bool = False


class MetadataRequestBuilder:
    """Constructor de requests para fetching de metadata (patrón: Builder).

    Centraliza la construcción de consultas de metadata, proporcionando
    una interfaz coherente y testeable independiente del motor de BD.
    """

    @staticmethod
    def routines(context_database: str) -> MetadataFetchRequest:
        """Construye la request estándar para listar rutinas.

        Args:
            context_database: Contexto (schema/database)

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="obtener_rutinas",
            params={"database": context_database},
            error_message="Error obteniendo rutinas",
        )

    @staticmethod
    def table_ddl(
        context_database: str,
        table_name: str,
        add_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
    ) -> MetadataFetchRequest:
        """Construye la request estándar para DDL de tabla.

        Args:
            context_database: Contexto (schema/database)
            table_name: Nombre de tabla
            add_context_params: Función para añadir parámetros de contexto

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="create_table",
            params=add_context_params({"tabla": table_name}, context_database),
            error_message="Error obteniendo DDL",
            table_name=table_name,
            expect_one=True,
        )

    @staticmethod
    def view_ddl(
        context_database: str,
        view_name: str,
        add_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
    ) -> MetadataFetchRequest:
        """Construye la request estándar para DDL de vista.

        Args:
            context_database: Contexto (schema/database)
            view_name: Nombre de vista
            add_context_params: Función para añadir parámetros de contexto

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="create_view",
            params=add_context_params({"tabla": view_name}, context_database),
            error_message="Error obteniendo DDL de vista",
            table_name=view_name,
            expect_one=True,
        )

    @staticmethod
    def columns(context_database: str, table_name: str) -> MetadataFetchRequest:
        """Construye la request estándar para columnas de tabla.

        Args:
            context_database: Contexto (schema/database)
            table_name: Nombre de tabla

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="columnas_tabla",
            params={"database": context_database, "tabla": table_name},
            error_message="Error obteniendo columnas",
            table_name=table_name,
        )

    @staticmethod
    def routine_parameters(
        context_database: str,
        routine_name: str,
        routine_type: str,
    ) -> MetadataFetchRequest:
        """Construye la request estándar para parámetros de rutina.

        Args:
            context_database: Contexto (schema/database)
            routine_name: Nombre de rutina
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc.)

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="parametros_rutina",
            params={
                "database": context_database,
                "rutina": routine_name,
                "tipo_rutina": routine_type,
            },
            error_message="Error obteniendo parámetros de rutina",
            table_name=routine_name,
        )

    @staticmethod
    def routine_ddl(
        context_database: str,
        routine_name: str,
        routine_type: str,
        add_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
    ) -> MetadataFetchRequest:
        """Construye la request estándar para DDL de rutina.

        Args:
            context_database: Contexto (schema/database)
            routine_name: Nombre de rutina
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc.)
            add_context_params: Función para añadir parámetros de contexto

        Returns:
            MetadataFetchRequest: Request configurada
        """
        return MetadataFetchRequest(
            query_name="create_rutina",
            params=add_context_params(
                {"rutina": routine_name, "tipo_rutina": routine_type},
                context_database,
            ),
            error_message="Error obteniendo DDL de rutina",
            table_name=routine_name,
            expect_one=True,
        )


__all__: list[str] = [
    "MetadataFetchRequest",
    "MetadataRequestBuilder",
]
