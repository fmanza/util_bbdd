# Conexiones

`util_bbdd.connection` normaliza los parámetros de conexión (`build_conn_params`) y crea conexiones y pools por motor
(`ConnectionFactory`). Referencia curada: [Factory de Conexiones](connection_factory.md).

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
