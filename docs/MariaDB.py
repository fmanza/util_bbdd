import sys

import mariadb

# Configuración de la conexión
config = {
    "host": "192.168.1.103",
    "port": 3306,
    "user": "root",
    "password": "c[2d-Qp-.5B%SN_#",
    "database": "SOCYALPRO",
}

config = {
    "host": "10.20.0.245",
    "port": 3306,
    "user": "SOCYALPRO",
    "password": "SOCYALPRO",
    "database": "SOCYALPRO",
}


try:
    # 1. Conectar al servidor
    conn = mariadb.connect(**config)
    print("Conexión exitosa a MariaDB")

    # 2. Crear un cursor
    cur = conn.cursor()

    # 3. Ejecutar una query sencilla
    sql = """SELECT
            column_name,
            column_type,
            is_nullable,
            column_key,
            column_default,
            extra,
            column_comment
        FROM
            information_schema.columns
        WHERE table_schema = 'SOCYALPRO' AND table_name = 'ACM_INTEGRACION'
        ORDER BY
            ordinal_position"""

    sql = """SHOW CREATE PROCEDURE AVANZAR_CONTADOR"""

    sql = """SELECT ROUTINE_NAME, ROUTINE_DEFINITION
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'SOCYALPRO'
  AND ROUTINE_TYPE = 'PROCEDURE';"""

    cur.execute(sql)

    # 4. Recuperar y mostrar los resultados
    print("\nResultados de la consulta:")
    for row in cur:
        print(row)
    # for column_name, column_type, is_nullable, column_key, column_default, extra, column_comment in cur:
    #    print(
    #        f"column_name: {column_name} | column_type: {column_type} | is_nullable: {is_nullable} | column_key: {column_key} | column_default: {column_default} | extra: {extra} | column_comment: {column_comment}"
    #    )

except mariadb.Error as e:
    print(f"Error conectando a MariaDB: {e}")
    conn.close()
    sys.exit(1)

finally:
    # 5. Cerrar la conexión siempre al terminar
    if "conn" in locals():
        conn.close()
        print("\nConexión cerrada.")
