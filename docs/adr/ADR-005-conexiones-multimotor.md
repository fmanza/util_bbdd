# ADR-005: Conexiones multimotor — validación única, pool de los Engine, charset del catálogo y TLS en MariaDB

## 1. Contexto y Problema

La auditoría `drivers-connections-audit` (FASE 1, v0.35.4) encontró que la configuración de conexión se aplicaba de
forma distinta según el camino:

- La validación de `conn_params` estaba repartida en tres capas que divergían: `connection/builder.py`, la lista
  blanca de `data/database_types.json` (`_drivers/validator.py`) y `*Config.from_params` de `connection/config.py`.
  El gestor async no pasaba por ninguna: aceptaba claves desconocidas sin aviso y, sin `schema`, leía los metadatos
  de PostgreSQL del schema con el nombre de la base de datos.
- Los Engine de SQLAlchemy (bulk, dump, comparar) tenían su propio pool con otra política: el sync ignoraba
  `pool_size` y solo reciclaba conexiones en MariaDB/MySQL; el async reciclaba cada 1800 s.
- La lectura del catálogo de MariaDB/MySQL dependía siempre de un diagnóstico de charset de 8 consultas, sin forma de
  fijar la estrategia.
- MariaDB no tenía ningún parámetro de TLS: la librería conectaba sin cifrar aunque el servidor lo ofreciera.

## 2. Decisión

Se eligió la **Opción B acotada** (consolidar sin mover ficheros ni romper imports) frente a la reorganización por
capas (Opción A), con cuatro decisiones:

1. **Validación única desde las configs** (v0.37.0). Las dataclasses de `connection/config.py` son la fuente de las
   claves aceptadas y de sus defaults: `ConnectionParamsManager.allowed_keys(db_type)` = campos de la config de
   conexión y de pool + extras declarados (`close_timeout`; `encoding` en Oracle). `build_conn_params` toma sus
   defaults de las configs. El JSON queda como documentación verificada por test (mismas claves y defaults). El
   gestor async valida igual que el sync y lanza `ValidationError`, pero sin inyectar los defaults del camino sync.
   `schema` es campo de PostgreSQL (`public`), SQL Server (`dbo`) y HSQLDB (`PUBLIC`).
2. **Política de pool común de los Engine** (v0.36.0). `factory/_pool_policy.py` (`engine_pool_kwargs`): sync y async
   toman `pool_size`, `max_overflow`, `pool_timeout` y `pool_recycle` de `conn_params` (5/10/30/3600). El Engine
   mantiene un pool propio, independiente del pool nativo del gestor (documentado; no se reutiliza el nativo).
   `close_timeout` es campo de cada `*PoolConfig`.
3. **`catalog_charset_mode`** (v0.38.0), solo MariaDB/MySQL y solo en los gestores: `auto` (diagnóstico, como antes),
   `native` o `convert` (sin diagnóstico). No se generaliza a otros motores: no hay evidencia del problema fuera de
   MariaDB/MySQL, y la sesión de MariaDB Connector/Python solo admite utf8mb4, así que no hay charset de sesión que
   elegir en sync.
4. **TLS en MariaDB** (v0.39.0): `ssl`, `ssl_ca`, `ssl_cert`, `ssl_key`, `ssl_verify_cert` en todos los caminos. Con
   `ssl_ca` se activa la verificación, porque el conector sync no exige la CA sin ella (comprobado contra MariaDB 11.4).
   En async, `ssl=True` sin `ssl_ca` cifra sin verificar y avisa.

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Un parámetro nuevo se declara en un solo sitio (la config); los tests impiden que el JSON se desincronice |
| Ventaja | Sync y async validan lo mismo y leen los metadatos del mismo schema |
| Ventaja | El tamaño y el reciclado del pool del Engine se configuran desde `conn_params` |
| Compromiso | Cambios de comportamiento en 0.36.0 (pool del Engine) y 0.37.0 (`ValidationError` en async, `search_path=public`); documentados en el CHANGELOG |
| Compromiso | El TLS async de MariaDB sin `ssl_ca` no verifica el certificado (el sync sí, por la configuración automática de MariaDB 11.4) |
| Límite del driver | Sin `ssl_verify_identity` en MariaDB: límite del conector sync, que solo tiene `ssl_verify_cert` (certificado y hostname juntos); comprobado el 2026-10-09 con CA propia. Las divergencias de URL sync/async y el `init_command` en MariaDB async se resolvieron en v0.40.0 y v0.39.2 |
| Límite del driver | `trust_cert` sin efecto con pymssql: la validación del certificado depende de FreeTDS (`freetds.conf`); desde v0.39.2 se avisa una vez por servidor y proceso. Alternativa: pyodbc/aioodbc |
| Riesgo aceptado | Doble pool (nativo + Engine) por gestor: se documenta en lugar de reutilizar el pool nativo |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| Opción A: reorganizar `connection/` y `metadata/` por capas (`_base/`, `_pool/`, `_charset/`) | Estructura más uniforme | Rompe imports (91 ficheros de tests); los pools solo comparten un 32 % de código; `CatalogExecutor` ya existía | Mismo ahorro que B con más riesgo |
| JSON como fuente única | Un solo fichero | Las reglas (regex, rangos, enums) no caben en el JSON | Las configs ya validan los valores |
| Estrategia de charset para todos los motores (`DETECT/UTF8MB4/NATIVE/CUSTOM`) | Uniformidad | Mezcla charset de sesión y lectura del catálogo; sin evidencia fuera de MariaDB/MySQL | Sobrediseño |
| Exigir `ssl_ca` en TLS async | Verificación siempre | Contra el certificado autogenerado de 11.4 obligaría a `ssl_verify_cert=False` | No mejora la seguridad real |

## 5. Estado y Revisión

**Estado:** ACEPTADO

Decisiones tomadas en la FASE 3 de `drivers-connections-audit` (2026-10-09) e implementadas en v0.35.9–v0.39.1.
Detalle: `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/decision_matrix_phase_2.md` § 6.

Fecha de última revisión: 2026-10-09
