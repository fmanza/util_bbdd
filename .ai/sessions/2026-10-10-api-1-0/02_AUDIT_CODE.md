# AUDIT_CODE — API pública 1.0, fase 0.43.0

Commits revisados: `e9690f45`, `4a929ec9`, `1f8bd47b` (sobre `676ee482`).

## Regresiones potenciales

| Punto | Revisión | Resultado |
|---|---|---|
| Identidad de los 46 alias | `test_deprecated_alias_warns_and_is_the_same_object` (parametrizado) | Mismo objeto que en la ruta nueva; `except util_bbdd.X` captura lo mismo |
| Avisos desde la propia librería | Suite completa sin y con banco: 0 mensajes «está obsoleto» de `util_bbdd`; `test_library_does_not_use_its_own_deprecated_aliases` en subproceso con avisos como error | Sin uso interno |
| Uso por `getattr(util_bbdd, …)` no visto por grep | Primera ejecución completa: 5 avisos en `tests/unit/bulk/test_audit_exception_hierarchy.py` | Corregido (`util_bbdd.exceptions`) |
| `util_bbdd.<subpaquete>` sin import explícito | `_SUBMODULES` en `__getattr__`; `test_subpackages_resolve_by_attribute_without_explicit_import` | Se mantiene |
| `from util_bbdd import *` | Ya no trae los 46 nombres (sin aviso) | Ruptura aceptada (D5); en CHANGELOG `Changed` y en la guía |
| Doble aviso en `from util_bbdd import X` | `_handle_fromlist` hace `hasattr` antes de `IMPORT_FROM` | Con el filtro por defecto se muestra uno (misma ubicación); `stacklevel=2` señala al llamante (test) |
| `close_connection` sync | Alias delega en `release_connection` con el mismo argumento; el ejecutor interno usa `release_connection` | Test con `session_manager` simulado; integración TLS MariaDB en verde con el banco |
| `SyncDatabaseManager.init()` | Devuelve `self`; no crea pool ni conexión | `test_sync_init_is_idempotent_and_returns_self` |

## Contratos públicos sync/async

- Nombres comunes: `init`, `get_connection`, `release_connection`, `close`, `get_supported_db_types`,
  `is_db_type_supported`, `validate_db_type_static`, `get_db_type_info_static` (`test_manager_symmetry`).
- Diferencia intencional documentada: `get_query_info`, `get_available_queries` y `get_database_info` son corrutinas en
  el async (D4).

## Cobertura preservada

- 30 ficheros de tests + 1 (jerarquía de auditoría) cambian solo imports; mismos tests, mismos asserts.
- Nuevos: `test_top_level_exports.py` (reescrito, 70 casos con la parametrización) y `test_manager_symmetry.py` (18).

## Tipado

- mypy sin errores (332 ficheros). Los 13 de la raíz tipados vía `TYPE_CHECKING`; los 46 alias resuelven a `Any` por
  `__getattr__ -> Any` (aceptable: desaparecen en 1.0.0).
- `async_utils` declara `__all__` (submódulo público).

## Rendimiento

`python -X importtime -c "import util_bbdd"`: antes 1 103 847 / 1 076 393 µs (caliente), después 307 406 / 304 590 /
321 191 µs (`build/logs/api10_importtime_{before,after}_*.txt`). Sin pandas, openpyxl, docx, jinja2 ni numpy
(`test_import_does_not_load_heavy_dependencies`).

## Pendiente para 1.0.0 (no bloquea)

- Retirar `_DEPRECATED`, `SyncDatabaseManager.close_connection()` y sus tests.
- `__module__` de las excepciones sigue siendo `util_bbdd._core.exceptions` (trazas y `repr`); valorar fijarlo a
  `util_bbdd.exceptions` en 1.0.0 (afecta a `pickle` de excepciones ya serializadas).

## Veredicto

**GO** — sin regresiones; la única ruptura (`import *`) está aceptada (D5) y documentada.
