# TRACEABILITY — v0.35.4

**Fecha**: 2026-10-08  
**Versión target**: v0.35.4  
**Estado**: CLOSED  

## Session summary

Se cierra la sesión de arreglo del pool MariaDB y del charset detection con el ajuste definitivo para que `init_command` se extraiga antes de crear `mariadb.ConnectionPool()` y se ejecute manualmente en cada `get_connection()`. Se simplifica el valor por defecto a `SET NAMES utf8mb4` para evitar errores de parseo del driver. La corrección está validada con pruebas unitarias y con verificación de logs de producción.

## Status

- Release objetivo: v0.35.4
- Base actual antes del cierre: v0.35.3
- Estado final: cerrado y sincronizado con la versión del proyecto y el changelog
- Veredicto: CLOSED

## Files changed

- `pyproject.toml` — versión actualizada a `0.35.4`
- `CHANGELOG.md` — nueva entrada `## [0.35.4] - 2026-10-08`
- `.ai/sessions/2026-10-07-charset-detection-pool-fixes/TRACEABILITY.md` — cierre operativo con directrices y handoff

## Tests and evidence

- `python -m mypy src/util_bbdd/connection/config.py src/util_bbdd/connection/mariadb/pool_connection_mariadb.py` → success
- `python -m ruff check src tests` → success
- `python -m pytest tests/unit/connection/mariadb/test_mariadb_driver_connection.py -q` → 18/18 passed
- Verificación de expediente de producción: H1-H5 funcionando y 1,745 `SystemError` resueltos

## Known limitations

- La corrección depende de que el valor de `init_command` se ejecute en la sesión real; en drivers antiguos o con comportamiento particular, el fallback manual añade un RTT por conexión.
- El cambio es compatible con la API pública, pero no elimina la necesidad de revisar conexiones heredadas con `character_set_server=latin1` si se ejecutan cargas legacy sin `SET NAMES`.

## Pending work

- Revisar en entorno de staging si hay clientes con `init_command` personalizado que usen el literal `COLLATE utf8mb4_unicode_ci` y decidir si se deben migrar a `SET NAMES utf8mb4` explícito.
- Confirmar que no existe más documentación heredada fuera de los ejemplos actualizados.

## Directrices para Futuras IAs

**[pool-init-command]**: En MariaDB Connector/Python 1.1.14 el parámetro `init_command` se aplica durante la creación del pool, no después; por eso se extrae antes de `ConnectionPool()` y se lanza manualmente en `get_connection()`.
**[charset-default]**: El valor seguro y compatible por defecto es `SET NAMES utf8mb4`; la forma con `COLLATE utf8mb4_unicode_ci` provoca errores de parseo en el driver y no debe reutilizarse.
**[connection_charset-priority]**: La semántica de `connection_charset` tiene prioridad sobre el `character_set_server` global al diagnosticar mismatches heredados de latin1.
**[production-fix]**: La verificación del log de producción confirma que H1-H5 y el retry defensivo resuelven la mayoría de los `SystemError` observados tras la corrección.
**[release-gate]**: Antes de cerrar una release, deben pasar ruff, mypy, la prueba unitaria relevante y la validación de sincronización de versión y changelog.

## Rollback

1. Revertir el `init_command` a la versión previa si se necesita compatibilidad retroactiva con un entorno muy específico.
2. Restaurar la versión previa en `pyproject.toml` y la entrada de changelog anterior.
3. Revertir el cambio de la lógica de pool a la implementación de creación directa con `ConnectionPool()` si aparece un problema de comportamiento no cubierto.

Riesgos del rollback:
- Las conexiones heredadas con `latin1` pueden volver a generar `SystemError` y fallos de diagnóstico de charset.
- Los clientes con `init_command` personalizado pueden perder el comportamiento de sesión correcto en el primer despliegue tras el revert.

## Handoff

La sesión queda cerrada con una corrección acotada y validada para MariaDB. El siguiente paso recomendado es publicar la versión 0.35.4 y dejar la documentación de conexión sincronizada con el valor final del `init_command` para evitar reintroducir el patrón de `COLLATE` que originó el problema.

**Commit message propuesto**:
`release: v0.35.4 - fix MariaDB pool init_command timing and charset setup`

---

*Sesión cerrada 2026-10-08*
