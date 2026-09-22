# REQUEST

## Session metadata
- id: 2026-09-21-regla6-ciclo-connection-factory
- fecha: 2026-09-21 (continúa el 2026-09-22)
- rama: develop
- skill: audit_code → refactor → new_feature (reincorporación de una utilidad)
- fase solicitada: AUDIT_CODE (`/audit-code`) de un ciclo de imports declarado por el usuario

## Solicitud original saneada
`/audit-code` con el siguiente argumento:

> connection/ y factory/ se importan mutuamente. factory/ importa de connection/ en 12 puntos (2 de módulo, 10 perezosos). En sentido contrario, un único import, `connection/mariadb/update_auto_increment.py:11`, cierra el ciclo. Hoy `import util_bbdd`, `util_bbdd.factory` y `util_bbdd.connection` resuelven sin error, así que el ciclo está latente. La Regla #6 prohíbe ciclos dentro de un nivel.

Instrucciones posteriores del usuario, en orden:
1. `IMPLEMENT` para la condición 1, opción A (retirar `update_auto_increment.py`).
2. `IMPLEMENT` de las condiciones 2 (reconciliar la Regla #6) y 3 (guarda automática).
3. Pide más información sobre «confirmar la dirección de la condición 2» y una recomendación, sabiendo que desea una arquitectura «lo más limpia posible».
4. Elige los pasos 1, 2 y 3 de la recomendación (capas estrictas) y pide solo `PLAN` y `AUDIT_PLAN`.
5. «Precondición: el trabajo previo sigue sin commitear. Hazlo» (interrumpido por el punto siguiente).
6. `PLAN` y `AUDIT_PLAN`: `update_auto_increment.py` debe reincorporarse como utilidad propia de MariaDB; pide la mejor estrategia según la arquitectura actual.
7. Decisiones: firma → `Engine`; Inspector frente a proveedor → Inspector; hay un MariaDB de pruebas; reescribir antes del commit base → sí.
8. Ejecuta él mismo el test de integración contra su MariaDB (3 passed) para no exponer credenciales.
9. «Actualizar .ai\sessions» (primera versión del registro).
10. «Commit» (del registro de sesión; commit `a54ce69`).
11. «IMPLEMENT» de los pasos 1–3 de capas estrictas, sin responder a las tres decisiones abiertas: se aplicaron las recomendaciones por defecto y no se tocó la CI en ese momento.
12. «Actualizar .ai/sessions» (con los pasos 1–3 implementados).
13. «Línea de mypy en tests.yml: añadir. Tocar CI»: el paso `mypy` de CI pasa a incluir `tests/unit/test_protocol_conformance.py`.
14. «El paso mypy las dos opciones»: `exclude` de `docs_build_plugin.py` en `[tool.mypy]` y override de `mkdocs` con corrección del fichero, para dejar en verde el paso `mypy` de CI.

## Objetivo operativo de esta sesión
- Verificar la afirmación del ciclo `connection/` ⇄ `factory/` (recuentos, latencia, alcance) y emitir veredicto AUDIT_CODE.
- Eliminar el ciclo sin perder la capacidad de generar sentencias `AUTO_INCREMENT` (reincorporar la utilidad como utilidad MariaDB).
- Reconciliar la Regla #6 (niveles y política dentro de un nivel) y hacerla cumplir con una guarda automática.
- Planificar (PLAN + AUDIT_PLAN) e implementar el endurecimiento a capas estrictas, pasos 1–3.

## Restricciones explícitas
- Cada fase se ejecuta solo cuando el usuario la pide (`IMPLEMENT`, o «PLAN y AUDIT_PLAN» sin tocar código).
- Commit y push solo bajo petición expresa. El commit base se hace después de reescribir el módulo y verificarlo contra un MariaDB real.
- Ninguna URL ni clave de conexión en la conversación: la verificación real la ejecuta el usuario con `UTIL_BBDD_TEST_MARIADB_URL`.
- Solo trabajo de `util_bbdd`; el de `doc_ia` (p. ej. `convert_to_md`) no pertenece a este repositorio.

## Resultado esperado
- Carpeta `.ai/sessions/2026-09-21-regla6-ciclo-connection-factory/` con los artefactos mínimos de trazabilidad.
- Ciclo eliminado y vigilado por test; `UpdateAutoIncrement` reincorporado; Regla #6 coherente en todas las fuentes que la enuncian.
- Capas estrictas implementadas y vigiladas por test, con el plan persistido (`01_PLAN_capas_estrictas.md`).
