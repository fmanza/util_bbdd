# Guía de verificación de documentación (`--verify-tools` / `--verify-build`)

## 1. Objetivo

Comprobar, antes de publicar, que la configuración del generador estático y el HTML producido son correctos.

Existen dos opciones complementarias, ambas opt-in, que se activan incluyéndolas en el mensaje al agente `Documentation Generator`:

| Opción | Qué comprueba | Cuándo usarla |
|---|---|---|
| `--verify-tools` | Compatibilidad de plugins y directivas de `mkdocs.yml` / `zensical.toml` contra las webs oficiales | Tras actualizar el generador o añadir un plugin nuevo |
| `--verify-build` | Calidad del HTML generado: autodoc expandido, snippets resueltos, Mermaid presente, nav sin huérfanos | Tras generar o actualizar documentación |
| `--verify-build --serve` | Lo mismo que `--verify-build`, pero con el servidor activo para ver Mermaid como SVG | Cuando necesitas confirmar el renderizado final completo |

## 2. Requisitos Previos

- Repositorio `util_bbdd` con `zensical` o `mkdocs-material` instalado en el entorno virtual.
- Al menos un fichero de configuración presente: `zensical.toml` o `mkdocs.yml`.
- Claude Code activo con el agente `Documentation Generator` disponible.
- Para `--verify-build --serve`: puerto `8000` libre en localhost.

## 3. Pasos

### Opción A — Verificar configuración (`--verify-tools`)

Invoca el agente incluyendo el modificador en el mensaje:

```
@Documentation Generator

Comprueba la configuración del proyecto. --verify-tools
```

El agente hace fetch de las webs oficiales y contrasta las directivas presentes en el fichero de configuración:

| Fuente | URL consultada |
|---|---|
| MkDocs | `https://www.mkdocs.org/about/release-notes/` |
| Material for MkDocs | `https://squidfunk.github.io/mkdocs-material/plugins/` |
| Zensical | `https://zensical.org/` |

El resultado es una lista de discrepancias clasificadas por severidad:

- **Nivel 1** — plugin o directiva inexistente en la versión instalada (build roto).
- **Nivel 2** — directiva deprecada con alternativa disponible.
- **Nivel 3** — configuración subóptima o con comportamiento no documentado.

### Opción B — Verificar build, Modo A (sin servidor)

```
@Documentation Generator

Verifica el output del build. --verify-build
```

El agente ejecuta:

```bash
zensical build --strict   # o: mkdocs build --strict
```

A continuación lee los ficheros HTML de `site/` y comprueba:

| Verificación | Señal buscada |
|---|---|
| Autodoc expandido | Métodos presentes en la sección `doc-function` / `doc-class` |
| Alias bug | Sección autodoc no vacía bajo el nombre real de la clase |
| Snippets `--8<--` resueltos | Ausencia de la cadena literal `--8<--` en el HTML |
| Mermaid presente | `<code class="language-mermaid">` o SVG en el HTML |
| Nav sin huérfanos | Cada página del `nav:` existe como fichero en `site/` |
| Build limpio | `--strict` termina con código de salida 0 |

### Opción C — Verificar build, Modo B (con servidor)

```
@Documentation Generator

Verifica el sitio con el servidor activo. --verify-build --serve
```

El agente solicitará confirmación antes de arrancar el servidor:

```bash
zensical serve   # o: mkdocs serve
```

Una vez activo, usa `WebFetch` sobre `http://localhost:8000/` para comprobar las mismas páginas que en el Modo A. Los diagramas Mermaid aparecen como SVG (renderizado completo con JavaScript). Detén el servidor cuando la verificación haya finalizado.

### Combinando opciones

Es posible combinar ambos modificadores en un solo mensaje:

```
@Documentation Generator

Actualiza docs/api/managers.md y verifica configuración y build. --verify-tools --verify-build
```

## 4. Verificación

Al finalizar, el agente entrega un reporte con el siguiente formato:

```
## Verificación de build — [Modo A / Modo B]

### Hallazgos
| Página | Verificación | Estado | Detalle |
|---|---|---|---|
| api/managers.md | Autodoc expandido | ✅ OK | 12 métodos encontrados |
| api/bulk-crud.md | Alias bug | ❌ FALLO | Sección sin métodos |

### Páginas con errores de build
- [lista de warnings/errors del build --strict]

### Acciones recomendadas
- [correcciones propuestas — el agente espera confirmación antes de aplicarlas]
```

Un resultado limpio muestra todas las verificaciones en ✅ OK y ninguna entrada en "Errores de build".

## 5. Variantes y Solución de Problemas

| Escenario | Causa probable | Solución |
|---|---|---|
| `--strict` falla con WARNING en plugin desconocido | Plugin no instalado o nombre cambiado en la versión activa | Ejecutar `--verify-tools` para obtener el nombre correcto |
| Sección autodoc sin métodos (alias bug) | Directiva `:::` apunta a un alias de variable, no a la clase real | Cambiar `util_bbdd.modulo.alias` → `util_bbdd.modulo.ClaseReal` (ver [Referencia Técnica](../api/bulk-crud.md)) |
| `--8<--` aparece en el HTML como texto literal | El plugin `snippets` no está habilitado en `mkdocs.yml` | Añadir `- pymdownx.snippets` en `markdown_extensions` |
| Puerto 8000 ocupado en Modo B | Otro proceso usa el puerto | Detener el proceso o cambiar el puerto: `mkdocs serve --dev-addr=127.0.0.1:8001` |
| Mermaid no aparece como SVG en Modo A | Correcto — en build estático Mermaid requiere JS en cliente | Usar Modo B (`--serve`) para ver el SVG renderizado |
| El agente no encuentra `site/` | El build no se ha ejecutado aún | El agente lo ejecuta automáticamente con `--verify-build` |
