import os
from sqlalchemy import create_engine, text, Table, MetaData, Column, Integer, String, insert
for drv in ("mariadb+pymysql", "mariadb+mariadbconnector"):
    eng = create_engine(os.environ["UTIL_BBDD_TEST_MARIADB_URL"].replace("mariadb+pymysql", drv))
    t = Table("zz_util_bbdd_lrid", MetaData(), Column("id", Integer, primary_key=True), Column("n", String(5)))
    t.drop(eng, checkfirst=True); t.create(eng)
    with eng.begin() as c:
        r1 = c.execute(text("INSERT INTO zz_util_bbdd_lrid (n) VALUES ('a')"))
        r2 = c.execute(insert(t).values(n="b"))
        raw = c.connection.driver_connection.cursor(); raw.execute("INSERT INTO zz_util_bbdd_lrid (n) VALUES ('c')")
        print(drv, "text:", r1.lastrowid, "| core:", r2.lastrowid, r2.inserted_primary_key, "| cursor del driver:", raw.lastrowid)
    t.drop(eng); eng.dispose()
