import logging
import sys
import traceback
from typing import TYPE_CHECKING, Any, List

import pandas as pd
from sqlalchemy.exc import DBAPIError, OperationalError

from util_bbdd.factory import SQLAlchemyEngineFactory

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine


class UpdateAutoIncrement:
    def __init__(self, conf: dict) -> None:
        """
        Constructor de la clase UpdateAutoIncrement.

        Args:
            conf (dict): Configuración de la BBDD de trabajo.
        """
        logger: logging.Logger = logging.getLogger(__name__)
        logger.info(f"ℹ️ Update Auto Increment: {conf['database']}")

        # Crear engine de SQLAlchemy
        self.engine: "Engine" = SQLAlchemyEngineFactory.create_engine(
            db_type=conf.get("db_type", "mariadb"),
            conn_params=conf,
            database=conf["database"]
        )

        # Consulta SQL para obtener la tabla y columna PRIMARY KEY
        sql: str = f"""
            SELECT TABLE_NAME, COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = "{conf["database"]}" AND CONSTRAINT_NAME = "PRIMARY"
        """

        try:
            # Ejecutar la consulta y obtener el resultado en un DataFrame
            self.df_information_schema: pd.DataFrame = pd.read_sql(sql, self.engine)
        except OperationalError as e:
            logger.error("❌ Error en la conexión a la BBDD (OperationalError).")
            logger.error(e)
            logger.error(traceback.format_exc())
            sys.exit(1)
        except DBAPIError as e:
            logger.error("❌ Error en la conexión a la BBDD (DBAPI o Interface).")
            logger.error(e)
            logger.error(traceback.format_exc())
            sys.exit(1)
        except Exception as e:
            logger.error("❌ Ocurrió un error inesperado al conectar con la BBDD.")
            logger.error(e)
            logger.error(traceback.format_exc())
            sys.exit(1)

    def salida_sql(self) -> List[str]:
        """
        Genera sentencias SQL para actualizar el valor de AUTO_INCREMENT en las tablas de la BBDD.

        Returns:
            List[str]: Lista de sentencias SQL para actualizar el valor de AUTO_INCREMENT en las tablas de la BBDD.
        """
        sql_salida: List[str] = []
        # Recorrer el DataFrame y crear sentencias INSERT
        for index, row in self.df_information_schema.iterrows():
            # Consulta SQL para obtener el valor máximo de la columna PRIMARY KEY
            sql: str = f"SELECT MAX({row['COLUMN_NAME']}) AS ID_MAX FROM {row['TABLE_NAME']}"
            df_max: pd.DataFrame = pd.read_sql(sql, self.engine)

            # Obtener el valor máximo de la columna PRIMARY KEY
            max_id_value: Any = df_max.at[0, "ID_MAX"]

            if max_id_value is None or max_id_value == -1:
                # Si el valor máximo es None o -1, se establece el valor de AUTO_INCREMENT en 1
                max_id: int = 1
            else:
                # Se incrementa el valor máximo en 1
                max_id: int = int(max_id_value) + 1

            # Sentencia SQL para actualizar el valor de AUTO_INCREMENT en la tabla
            sql_update: str = f"ALTER TABLE {row['TABLE_NAME']} AUTO_INCREMENT = {max_id};"
            sql_salida.append(sql_update)

        return sql_salida

