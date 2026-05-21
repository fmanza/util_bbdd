# REQUEST

## Session metadata
- id: 2026-05-22b-comparar-ip-hostname
- fecha: 2026-05-22
- rama: develop
- skill: refactor
- fase solicitada: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Solicitud original saneada
En el nuevo nombre (stem de fichero de reporte) el host se recogen los dos primeros
caracteres de la IP. Quiero que si el host es una IP se recogan los últimos y si es
un nombre que se recoja tal cual.

## Objetivo operativo de esta sesión
- Cambiar la extracción del host en `_build_short_label()`: si es IPv4 → último octeto;
  si es nombre DNS → nombre completo sin truncar.
- Actualizar el test `test_host_abbreviated_to_first_segment` con el nuevo comportamiento.
- Añadir test para host IP.

## Restricciones explícitas
- Solo cambia la lógica de `host_short` dentro de `_build_short_label()`.
- No tocar `_build_label()`, modelos, reporters ni ningún otro método.
- API pública SIN CAMBIOS.

## Resultado esperado
- `_build_short_label` con `host = "192.168.1.10"` → `host_short = "10"` (último octeto).
- `_build_short_label` con `host = "server.company.internal"` → `host_short = "server.company.internal"` (tal cual).
- 12 tests en `TestBuildShortLabel` verdes, 275/275 totales.
