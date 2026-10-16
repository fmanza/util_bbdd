# Conexiones

`util_bbdd.connection` normaliza los parámetros de conexión (`build_conn_params`) y crea conexiones y pools por motor
(`ConnectionFactory`); `util_bbdd.factory` añade los pools (`PoolFactory`) y los engines SQLAlchemy. Referencia
curada: [Factory de Conexiones](connection_factory.md).

---

## build_conn_params

::: util_bbdd.connection.builder.build_conn_params
    options:
      show_source: false
      heading_level: 3

---

## ConnectionFactory

::: util_bbdd.connection.factory.ConnectionFactory
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ConnectionParamsManager

::: util_bbdd.connection.params.ConnectionParamsManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## PoolFactory

::: util_bbdd.factory.pool_factory.PoolFactory
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## Engines SQLAlchemy

::: util_bbdd.factory.sqlalchemy_engine_factory.SQLAlchemyEngineFactory
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

::: util_bbdd.factory.async_sqlalchemy_engine_factory.AsyncSQLAlchemyEngineFactory
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
