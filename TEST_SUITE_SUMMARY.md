# Test Suite Summary - util_bbdd

## Estado del documento

Este archivo se conserva como referencia historica de una etapa inicial de la suite. Sus cifras y ejemplos ya no describen el estado actual del repositorio.

## Fuente de verdad vigente

- La configuracion activa de pytest esta en `pytest.ini`.
- La validacion automatizada de GitHub esta en `.github/workflows/tests.yml`.
- El estado real de la suite debe comprobarse ejecutando `python -m pytest` en el workspace actual.
- Los comandos de validacion recomendados para contribucion estan en `.github/CONTRIBUTING.md`.

## Uso recomendado

Para revisar calidad y empaquetado del proyecto usa este flujo local:

```bash
python -m ruff check src tests
python -m mypy src
python -m pytest
python -m build
```

## Nota de mantenimiento

Si se necesita un resumen vivo de cobertura, suites o tiempos, debe generarse a partir de la ejecucion actual y no mantenerse manualmente en este archivo.
