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

---

## Capacidades y drivers por motor (v4.6.0)

`get_engine_capabilities(db_type)` dice qué operaciones admite un motor y `get_driver_status(db_type)` qué drivers
de Python están instalados (sin importarlos). Las dos se importan desde `util_bbdd.connection`.

::: util_bbdd.core.capabilities.get_engine_capabilities
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.core.capabilities.EngineCapabilities
    options:
      show_source: false
      heading_level: 3

::: util_bbdd._drivers.driver_status.get_driver_status
    options:
      show_source: false
      heading_level: 3

::: util_bbdd._drivers.driver_status.DriverStatus
    options:
      show_source: false
      heading_level: 3
