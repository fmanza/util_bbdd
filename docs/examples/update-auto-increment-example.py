"""
Ejemplo ejecutable: reajuste de AUTO_INCREMENT en MariaDB/MySQL

Genera el script que devuelve el contador AUTO_INCREMENT de cada tabla a MAX + 1, sin ejecutar nada en el servidor.

El Engine se crea a partir de la URL de SQLAlchemy indicada en la variable de entorno UTIL_BBDD_EXAMPLE_URL, por
ejemplo ``mariadb+pymysql://usuario:clave@servidor/tienda``. Sin ella el ejemplo termina explicando cómo configurarla.

Uso:
    python update-auto-increment-example.py
"""

import os
import sys

from sqlalchemy import create_engine

from util_bbdd.connection.mariadb import UpdateAutoIncrement


def generate_script(url: str) -> list[str]:
    """Devuelve las sentencias ALTER TABLE ... AUTO_INCREMENT del esquema de la URL."""
    engine = create_engine(url)
    try:
        return UpdateAutoIncrement(engine).salida_sql()
    finally:
        engine.dispose()  # el Engine es nuestro: la utilidad nunca lo cierra


def main() -> int:
    url = os.environ.get("UTIL_BBDD_EXAMPLE_URL")
    if not url:
        print("Define UTIL_BBDD_EXAMPLE_URL con la URL SQLAlchemy de un MariaDB/MySQL de pruebas.")
        return 0

    statements = generate_script(url)
    print(f"-- {len(statements)} sentencia(s); revísalas antes de ejecutarlas")
    for statement in statements:
        print(statement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
