# Ejemplo: Verificar las Condiciones del Motor

## 1. Contexto del Ejemplo

Antes de una carga masiva conviene saber si la configuración de conexión y la del servidor la van a frenar o a poner en
riesgo: un pool demasiado pequeño, un `timeout` corto o un modo de diario que bloquea a los escritores concurrentes.
`EngineReadinessAdvisor` lo revisa en modo solo lectura y devuelve hallazgos con su nivel (`OK`, `INFO`, `WARNING`,
`CRITICAL`) y una recomendación.

El ejemplo muestra las tres formas de uso sobre SQLite, sin servidor externo: checks estáticos sin conectar, el informe
completo de un manager con los checks dinámicos y el informe de un motor sin checks.

## 2. Implementación de Referencia

```python
--8<-- "examples/engine_readiness_advisor.py"
```

## 3. Explicación del Código

- **Checks estáticos (`check`)**: solo leen `conn_params`, así que sirven para validar una configuración antes de
  abrir ninguna conexión. Aquí `timeout=2.0` da un `WARNING` (por debajo de 5 s hay riesgo de `database is locked`).
- **Informe del manager (`get_engine_readiness`)**: llama a `assess` con los `conn_params` del manager y una conexión
  de su engine, por lo que añade los checks dinámicos (en SQLite, `PRAGMA journal_mode`, `synchronous` y
  `cache_size`). El manager usa `timeout=5.0` por defecto: el mismo check sale ahora `OK`.
- **`EngineReadinessReport` distingue «sin hallazgos» de «no verificado»**: `supported=False` indica que el motor no
  tiene checks (HSQLDB), `dynamic=False` que no hubo conexión y `error` el motivo, solo con el tipo de la excepción.
- **Nunca lanza**: un fallo del servidor o del driver omite ese check; la verificación no detiene la carga.
- **Orden**: los hallazgos se devuelven de mayor a menor severidad.
- **Base de datos en fichero**: con `:memory:` el advisor informa `INFO` sobre `database` y omite el check de
  `journal_mode`, que no aplica a una base en memoria.

Para cargas reales no hace falta llamarlo a mano: `BulkCrud` verifica su engine al crearse (una vez por engine en el
proceso) y `DumpOrchestrator` verifica origen y destino al empezar.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/engine_readiness_advisor.py

# Ejecución (crea y borra carga.db en el directorio actual)
python docs/examples/engine_readiness_advisor.py
```

Resultado esperado:

```text
WARNING  timeout = 2.0s
         → Riesgo de 'database is locked' bajo escritura concurrente; recomendado ≥5 s
OK       database = carga.db
motor=sqlite soportado=True dinámico=True error=None
WARNING  journal_mode = delete
INFO     synchronous = FULL
INFO     cache_size = -2000 (2000 KB)
OK       database = carga.db
OK       timeout = 5.0s
hsqldb soportado=False hallazgos=0
```

El valor de `cache_size` es el que trae compilado el SQLite del intérprete (`-2000` en las distribuciones habituales).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Condiciones del Motor](../functional/engine_readiness.md) — qué se verifica y por qué
- **Referencia técnica**: [Condiciones del Motor (EngineReadinessAdvisor)](../api/engine_readiness_advisor.md) — API,
  contratos y errores
- **Guía**: [Validación de parámetros de rendimiento](../guides/performance_readiness_guide.md) — umbrales por motor
- **Ejemplos relacionados**: [Validación de Variables MySQL/MariaDB](mysql_variables_example.md) — lectura de las
  variables del servidor en MySQL/MariaDB
