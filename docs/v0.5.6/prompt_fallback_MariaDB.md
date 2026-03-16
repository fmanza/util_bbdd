# Prompt v0.5.6: eliminar flujo fragmentado y fallback funcional de MariaDB

## 1. Resumen ejecutivo

Se debe preparar e implementar una ampliacion para la version `v0.5.6` cuyo objetivo es eliminar el flujo fragmentado de consultas de MariaDB para inventario de objetos y almacenamiento, sustituyendolo por una unica extraccion SQL interna y una particion posterior en Python apoyada en cache central.

La decision ya esta tomada y no debe volver a discutirse durante la implementacion:

- MariaDB debe resolver su inventario estructural y de almacenamiento desde una sola extraccion SQL interna.
- Se mantiene el contrato externo actual consumido por managers y documentacion.
- La separacion por tipos de objeto deja de depender de multiples queries MariaDB independientes y pasa a hacerse en la capa Python.
- Cuando MariaDB no exponga una pieza de metadata, la salida debe ser explicita (`not_supported`, `sin datos`, o mensaje equivalente), nunca un error generico ni una excepcion silenciosa.

El trabajo debe quedar documentado y cerrado para release `v0.5.6`, incluyendo actualizacion de `README.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md` y `pyproject.toml`.

## 2. Diagnostico actual del repositorio

La implementacion debe partir de estos hechos observados en el codigo actual:

- `src/util_bbdd/data/sql_queries.json` define en MariaDB consultas separadas para:
  - `obtener_tablas`
  - `obtener_vistas`
  - `obtener_rutinas`
  - `ficheros_fisicos`
- No existe hoy una query unificada MariaDB para inventario global de objetos y almacenamiento.
- `src/util_bbdd/managers/sync_mgr.py` y `src/util_bbdd/managers/async_mgr.py` mantienen un contrato de almacenamiento basado en:
  - `primary`
  - `secondary`
  - `temp_tablespaces` solo cuando aplica
- En MariaDB, la rama actual sigue resolviendo `secondary` mediante `ficheros_fisicos_adicional`.
- `src/util_bbdd/doc/database_documentation.py` genera tres secciones diferenciadas de almacenamiento:
  - `ficheros_fisicos`
  - `ficheros_fisicos_adicional`
  - `temp_tablespaces`
- La capa documental ya sabe representar estados controlados como:
  - `not_supported`
  - `missing_params`
  - `error`

Conclusion obligatoria: el cambio no puede limitarse a una query SQL. Tambien debe reorganizar managers, cache y adaptacion a documentacion para mantener intacto el contrato externo.

## 3. Objetivo tecnico cerrado

Se debe crear una **query interna unificada de inventario MariaDB** que obtenga en una sola ejecucion todos los elementos necesarios para derivar:

- tablas
- vistas
- rutinas
- almacenamiento principal
- almacenamiento adicional, solo si MariaDB realmente lo soporta
- temp tablespaces, solo si MariaDB realmente lo soporta

Esta query unificada sera una capacidad interna del motor MariaDB. No se exige extender el mismo patron a Oracle, PostgreSQL, SQLite, HSQLDB o SQL Server dentro de esta tarea.

### Restricciones no negociables

- Se reutiliza la cache central de `src/util_bbdd/metadata/cache.py`.
- No se crean caches paralelas ni caches ad hoc en documentacion.
- Se mantiene la API publica actual de managers.
- Se mantiene la forma de salida actual usada por Word, Excel y HTML.
- No se mantiene compatibilidad hacia atras con rutas internas obsoletas de MariaDB si quedan reemplazadas por la query unificada.

## 4. Contrato interno obligatorio del dataset unificado

La query unificada MariaDB debe normalizar su salida a un shape unico y estable, suficiente para que Python separe resultados sin decisiones abiertas. El dataset debe exponer, como minimo, las siguientes columnas logicas:

- `item_kind`
- `object_name`
- `object_comment`
- `routine_type`
- `engine`
- `charset`
- `collation`
- `data_mb`
- `index_mb`
- `total_mb`
- `storage_name`
- `storage_file`
- `storage_size_mb`
- `status`
- `supported`

### Reglas de modelado

- `item_kind` solo puede tomar estos valores:
  - `table`
  - `view`
  - `routine`
  - `storage_primary`
  - `storage_secondary`
  - `temp_tablespace`
- Los campos no aplicables deben devolverse como `NULL`, no como cadenas vacias inventadas salvo que una capa publica exija texto final.
- `supported` debe permitir distinguir entre:
  - dato soportado y presente
  - dato soportado pero sin filas
  - dato no soportado por MariaDB o por la variante concreta inspeccionada
- `status` debe ser util para traducir la salida interna a mensajes claros en documentacion.
- La separacion por tablas, vistas, rutinas y almacenamiento debe ocurrir despues de leer este dataset, nunca relanzando nuevas queries MariaDB para esos grupos.

## 5. Diseno y arquitectura que se debe imponer

### 5.1 Catalogo SQL

- Añadir al catalogo una query unificada MariaDB especifica para inventario global.
- Marcar como obsoletas, a nivel interno MariaDB, las rutas fragmentadas hoy usadas para poblar tablas, vistas, rutinas y almacenamiento cuando toda esa informacion pueda salir del dataset unificado.
- Si alguna query legacy MariaDB debe sobrevivir temporalmente por compatibilidad de otra ruta no cubierta, debe quedar documentada como transitoria y con criterio claro de retirada.

### 5.2 Managers sync/async

Se deben adaptar `src/util_bbdd/managers/sync_mgr.py` y `src/util_bbdd/managers/async_mgr.py` para que, en MariaDB:

- `get_tables()`
- `get_views()`
- `get_routines()`
- `get_storage_inventory()`

lean desde el dataset unificado cacheado.

#### Contrato externo que no puede romperse

`get_storage_inventory()` debe seguir devolviendo la forma actual:

- `primary`
- `secondary`
- `temp_tablespaces` cuando corresponda

La diferencia es interna: `primary`, `secondary` y `temp_tablespaces` saldran de la particion del dataset unificado, no de multiples consultas separadas.

### 5.3 Cache

- La primera consulta MariaDB al inventario unificado poblara cache central.
- Las llamadas posteriores a tablas, vistas, rutinas y almacenamiento deben leer del mismo dataset cacheado mientras el contexto sea el mismo.
- La invalidacion debe apoyarse en los mecanismos ya existentes de cache por contexto.
- No se admite duplicar datos cacheados en estructuras paralelas salvo que sea una vista derivada efimera y no persistida.

### 5.4 Documentacion

`src/util_bbdd/doc/database_documentation.py` debe seguir recibiendo secciones separadas para:

- `ficheros_fisicos`
- `ficheros_fisicos_adicional`
- `temp_tablespaces`

pero internamente dichas secciones deben poder derivarse del dataset unificado MariaDB.

Regla obligatoria:

- si MariaDB no ofrece `storage_secondary` o `temp_tablespace`, la documentacion debe producir una seccion controlada de "no disponible" o "sin datos", nunca un traceback ni un mensaje de error generico de bajo nivel.

### 5.5 Word, Excel y HTML

Se debe revisar compatibilidad de plantillas, headers y renderizado si aparecen nuevos campos visibles:

- `engine`
- `charset`
- `collation`

La ampliacion debe ser consistente en los tres formatos:

- Word
- Excel
- HTML

Si la visibilidad de estos campos requiere reorganizar columnas, cabeceras o tablas, el cambio debe hacerse de forma uniforme.

## 6. Estrategia tecnica recomendada

La implementacion debe seguir esta estrategia salvo que durante el desarrollo se detecte un impedimento tecnico objetivo y documentado:

### 6.1 Construccion de la query unificada

- Basarse en `information_schema` de MariaDB.
- Construir un dataset homogeneo con `UNION ALL` entre los bloques que representen:
  - tablas
  - vistas
  - rutinas
  - almacenamiento principal
  - almacenamiento adicional, si existe fuente fiable
  - temp tablespaces, si existe fuente fiable
- Normalizar tipos y aliases en SQL para que todas las filas compartan el mismo contrato de columnas.
- Incluir `engine`, `charset` y `collation` directamente para tablas cuando el motor los exponga.

### 6.2 Tratamiento de soporte parcial

Si MariaDB no ofrece una fuente estable para alguna categoria:

- la query unificada puede devolver filas sinteticas con `supported = 0` y `status = 'not_supported'`, o
- la capa Python puede traducir ausencia de filas de cierto `item_kind` a seccion `not_supported`

La decision concreta debe ser unica y consistente en todo el flujo. No mezclar estrategias sin justificacion.

### 6.3 Particion del dataset

La capa Python debe exponer funciones o helpers dedicados para derivar, al menos:

- lista normalizada de tablas
- lista normalizada de vistas
- lista normalizada de rutinas
- `storage_primary`
- `storage_secondary`
- `temp_tablespaces`

Se debe aplicar responsabilidad unica:

- una responsabilidad para cargar dataset
- una responsabilidad para cachearlo
- una responsabilidad para convertirlo a modelos/rows publicos
- una responsabilidad para traducirlo a las secciones de documentacion

## 7. Ficheros y zonas candidatas a cambio

Revisar y modificar lo necesario, incluyendo como minimo:

- `src/util_bbdd/data/sql_queries.json`
- `src/util_bbdd/managers/sync_mgr.py`
- `src/util_bbdd/managers/async_mgr.py`
- `src/util_bbdd/metadata/cache.py`
- `src/util_bbdd/doc/database_documentation.py`
- `src/util_bbdd/doc/word_generator.py`
- `src/util_bbdd/doc/excel_generator.py`
- `src/util_bbdd/doc/html_generator.py`
- `src/util_bbdd/doc/data/headers_config.json`
- `README.md`
- `docs/ARCHITECTURE.md`
- `CHANGELOG.md`
- `pyproject.toml`

Si para cumplir SRP es necesario crear nuevos modulos o helpers, se debe hacer sin miedo, evitando concentrar toda la logica en managers o en `database_documentation.py`.

## 8. Plan de implementacion por fases

### Fase 1. Inventario y puntos de consumo

Objetivo:

- localizar todas las rutas MariaDB que hoy dependen de consultas fragmentadas o fallback funcional

Trabajo esperado:

- inventariar queries actuales MariaDB en `sql_queries.json`
- identificar que metodos sync/async consumen tablas, vistas, rutinas y almacenamiento
- confirmar que la documentacion depende del contrato `primary`/`secondary` y de secciones separadas
- registrar cualquier ruta legacy adicional que siga llamando a consultas MariaDB independientes

Resultado de salida:

- mapa claro de dependencias actuales
- lista de puntos exactos a migrar al dataset unificado

### Fase 2. Query unificada y normalizacion interna

Objetivo:

- introducir la query unificada MariaDB y conectarla a cache central

Trabajo esperado:

- añadir query unificada al catalogo SQL
- crear carga centralizada del dataset unificado
- almacenar su resultado en cache por contexto MariaDB
- definir helpers puros para separar filas por `item_kind`
- documentar claramente cualquier categoria sin soporte real

Resultado de salida:

- una sola extraccion SQL MariaDB para inventario global
- una unica fuente cacheada de verdad para tablas, vistas, rutinas y almacenamiento

### Fase 3. Derivacion para managers y documentacion

Objetivo:

- reemplazar el consumo de rutas fragmentadas sin romper el contrato externo

Trabajo esperado:

- adaptar managers sync/async para derivar tablas, vistas y rutinas del dataset unificado
- adaptar `get_storage_inventory()` para seguir entregando `primary` y `secondary`
- garantizar que `database_documentation.py` siga generando secciones separadas
- eliminar o dejar obsoletas las ramas internas que ya no aporten valor en MariaDB

Resultado de salida:

- mismo contrato publico
- distinta arquitectura interna
- menos consultas MariaDB y menos errores de compatibilidad

### Fase 4. Renderizado, release y documentacion

Objetivo:

- cerrar la release `v0.5.6` con documentacion y notas consistentes

Trabajo esperado:

- revisar Word, Excel y HTML para mostrar `engine`, `charset` y `collation` cuando apliquen
- actualizar README con el nuevo comportamiento
- actualizar arquitectura con la nueva fuente unificada de metadata MariaDB
- actualizar CHANGELOG
- subir version en `pyproject.toml`

Resultado de salida:

- release documentada de forma coherente
- documentacion funcional sin rutas legacy ocultas

## 9. Casos de prueba obligatorios

La implementacion debe cubrir, como minimo, estos escenarios:

### Dataset unificado MariaDB

- MariaDB devuelve tablas con `engine`, `charset` y `collation` sin lanzar queries extra.
- Vistas y rutinas se recuperan desde la query unificada y quedan correctamente particionadas.
- La particion por `item_kind` no pierde filas ni mezcla categorias.

### Managers

- `get_tables()` en MariaDB usa el dataset unificado cacheado.
- `get_views()` en MariaDB usa el dataset unificado cacheado.
- `get_routines()` en MariaDB usa el dataset unificado cacheado.
- `get_storage_inventory()` en MariaDB conserva `primary` y `secondary`.
- Sync y async mantienen el mismo contrato observable.

### Cache

- La primera carga consulta MariaDB.
- Las siguientes lecturas del mismo contexto reutilizan cache.
- La invalidacion por contexto sigue funcionando.

### Documentacion

- Word no falla al introducir o reordenar columnas visibles.
- Excel no falla al introducir o reordenar columnas visibles.
- HTML no falla al introducir o reordenar columnas visibles.
- Si no existe soporte real para `storage_secondary`, la seccion aparece como no disponible o sin datos.
- Si no existe soporte real para `temp_tablespaces`, la seccion aparece como no disponible o sin datos.

### Errores y regresiones

- No se devuelve error generico por ausencia de metadata MariaDB no soportada.
- No se rompe el flujo actual de generacion documental.
- No se introducen nuevas caches paralelas.

## 10. Criterios de aceptacion

- MariaDB deja de depender de multiples queries independientes para construir su inventario global de objetos y almacenamiento.
- Existe una unica extraccion SQL interna y cacheada para ese inventario.
- El contrato externo de managers no cambia.
- Word, Excel y HTML siguen funcionando.
- Los casos no soportados se representan de manera explicita y controlada.
- Se documentan claramente los cambios en README, arquitectura, changelog y version.
- La solucion es estructural, no un fix puntual.

## 11. Riesgos que se deben vigilar

- Acoplar demasiada logica al manager en lugar de extraer helpers con SRP.
- Duplicar en Python una segunda cache no alineada con la cache central.
- Romper el contrato de `get_storage_inventory()` al introducir un dataset nuevo.
- Introducir nuevos campos visibles sin revisar headers o plantillas documentales.
- Ocultar fallos reales con `except Exception` demasiado amplios.

Cada riesgo debe mitigarse con codigo claro, tests y documentacion de la decision tomada.

## 12. Actualizaciones de release obligatorias

Al cerrar esta tarea se debe dejar reflejado en `v0.5.6`:

- `CHANGELOG.md` con el cambio funcional y arquitectonico
- `README.md` con comportamiento actualizado y ejemplos si procede
- `docs/ARCHITECTURE.md` con la nueva arquitectura MariaDB basada en dataset unificado
- `pyproject.toml` con la version `v0.5.6`

## 13. Suposiciones y defaults fijados

- Este documento es deliberadamente largo y accionable; no es un borrador corto.
- Se conserva el contrato actual de salida; no se rediseña la API publica.
- La unificacion es interna para MariaDB y no obliga a rehacer otros motores en esta tarea.
- No se exige compatibilidad hacia atras con rutas internas obsoletas reemplazadas por la nueva arquitectura.
- Si un dato no existe en MariaDB, se informa con salida controlada, no con error generico.

## 14. Resultado esperado al finalizar

El proyecto debe quedar preparado para que MariaDB obtenga tablas, vistas, rutinas y almacenamiento desde una sola fuente SQL interna, cacheada y particionada en Python, manteniendo intacto el contrato que hoy consumen los managers y la generacion de documentacion.
