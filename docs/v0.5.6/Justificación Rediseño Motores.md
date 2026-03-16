Estado Actual

Ahora mismo el diseño está en un punto razonable. La lógica específica de MariaDB ya no vive mezclada en los métodos públicos, sino repartida entre:

helpers puros en common.py, tables.py y routines.py
adaptadores de orquestación en sync_adapter.py y async_adapter.py
dispatchers privados en sync_mgr.py y async_mgr.py

Nomenclatura actual preferida:

SyncDatabaseManager como clase canónica sync
AsyncDatabaseManager como clase canónica async
DatabaseManager retirado como alias público para evitar duplicidad nominal
Lo que queda duplicado no es la lógica MariaDB “difícil”, sino la selección de estrategia:

_get_routines_fetcher
_get_table_ddl_fetcher
_get_view_ddl_fetcher
_get_columns_fetcher
_get_routine_parameters_fetcher
_get_routine_ddl_fetcher
_get_storage_inventory_handler
Eso es duplicación real, pero es duplicación bastante superficial.

Qué ganarias si extraes los dispatchers

Beneficios:

Un solo punto para decidir qué motor usa qué estrategia.
Menor riesgo de que sync y async diverjan al añadir un nuevo caso especial.
Los managers quedarían aún más centrados en caché, logging y ejecución.
Beneficio real esperado:

Mantenimiento algo mejor.
Menos diff en futuros cambios de estrategia.
Menos repetición visual en sync_mgr.py y async_mgr.py.
Qué coste tiene

Aquí está el punto importante: el coste no es pequeño para el beneficio que aporta.

Si lo extraes bien, necesitas una capa compartida nueva, algo como:

metadata/dispatchers/
o un módulo común con factories de estrategia
o una abstracción basada en protocolo/genéricos para sync y async
Eso implica:

más tipos genéricos o más Any/cast
más indirección mental
más superficie de tests
más riesgo de que el código sea “más abstracto que útil”
El problema de fondo es que sync y async no comparten solo nombres; comparten intención, pero no la misma firma:

sync devuelve valores inmediatos
async devuelve Awaitable
los wrappers de logging y caché también son distintos
el typing se vuelve bastante más feo si intentas unificarlos de verdad
En otras palabras: la extracción siguiente ya no es “mover lógica”, es “introducir framework interno”.

Impacto Técnico del Cambio

Si decides hacerlo, el impacto tocaría al menos:

sync_mgr.py
async_mgr.py
probablemente un nuevo módulo compartido de dispatch
tests de managers sync/async
tests de contrato de DDL/rutinas/storage
Riesgos:

regresiones en cacheado por closures/contexto
más warnings de tipado, no menos
pérdida de legibilidad local al seguir el flujo
abstracción prematura si MariaDB sigue siendo el único motor con tratamiento especial amplio
Mi recomendación

Pararía aquí por ahora.

Razón:

la lógica compleja ya está fuera
los métodos públicos ya están limpios
lo que queda duplicado es aceptable y entendible
el siguiente salto mejora arquitectura “en papel”, pero no da una mejora proporcional en valor real
Cuándo sí merece la pena dar el siguiente paso

Si otro motor además de MariaDB empieza a necesitar rutas especiales en 3 o más operaciones.
Si vas a añadir más operaciones especiales del mismo estilo.
Si ves cambios repetidos en sync y async en varias releases seguidas.
Si quieres invertir específicamente en una capa interna de estrategia por motor como objetivo del sprint.
Opción intermedia de bajo riesgo
En vez de extraer una capa completa, puedes hacer solo esto:

mantener los dispatchers donde están
normalizar sus nombres y orden entre sync y async
añadir una prueba de paridad estructural básica entre ambos managers
Eso te da disciplina arquitectónica sin abrir otra capa.

Mi lectura: hoy el coste de extraerlos a una capa compartida es mayor que el beneficio. Si quieres, puedo dejarte una propuesta concreta de diseño para esa capa futura, pero sin implementarla todavía.
