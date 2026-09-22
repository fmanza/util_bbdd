# Guía del diagrama de arquitectura — `gen_arquitectura_capas.py`

## 1. Objetivo

Regenerar la figura «Capas e imports reales» de [Arquitectura del Sistema](../architecture.md#capas-e-imports-reales) después de cambiar los imports entre los paquetes de `src/util_bbdd/`. La figura no se edita a mano: se calcula desde el código.

El script `scripts/gen_arquitectura_capas.py` encadena tres pasos:

1. **Medir** — recorre con `ast` los ficheros de `src/util_bbdd/` y cuenta los imports entre paquetes de primer nivel, separando los de módulo, los perezosos (dentro de una función) y los que están bajo `TYPE_CHECKING`.
2. **Verificar** — comprueba que cada flecha dibujada existe en el código y que no falta ninguna flecha real. Si algo no coincide, falla y no escribe nada.
3. **Escribir** — reescribe `docs/assets/diagrams/arquitectura-capas.svg`, `docs/assets/css/arquitectura-capas.css` y la tabla de capas `docs/assets/diagrams/arquitectura-capas-tabla.txt` (la incrusta `docs/architecture.md`).

La colocación de los nodos, la capa de cada paquete y la marca numerada son manuales. El script solo comprueba que siguen siendo ciertas.

---

## 2. Requisitos Previos

- Python 3.12 o superior. El script usa solo la biblioteca estándar.
- Repositorio `util_bbdd` clonado. Las rutas son relativas a la raíz del repositorio, así que puede lanzarse desde cualquier directorio.
- Para la verificación de la sección 4: `zensical` o `mkdocs` instalado (`pip install -e ".[docs]"`).

---

## 3. Pasos

1. **Cambia el código.** Añade, mueve o elimina un paquete de primer nivel de `src/util_bbdd/`, o un import entre paquetes.
2. **Ejecuta el script.**

    ```bash
    python scripts/gen_arquitectura_capas.py
    ```

3. **Lee el resultado.**
    - Si termina bien, lista los ficheros escritos y lo medido:

        ```text
        [gen_arquitectura_capas] wrote docs/assets/diagrams/arquitectura-capas.svg
        [gen_arquitectura_capas] wrote docs/assets/css/arquitectura-capas.css
        [gen_arquitectura_capas] wrote docs/assets/diagrams/arquitectura-capas-tabla.txt
        [gen_arquitectura_capas] measured 338 files; 9 packages import from Foundation.
        [gen_arquitectura_capas] Update the figcaption in docs/architecture.md if the version, date or file count changed.
        ```

    - Si falla, no ha escrito nada y enumera cada discrepancia (tabla de la sección 5):

        ```text
        [gen_arquitectura_capas] The figure no longer matches the code; nothing was written:
          - found in the code but not drawn: dump -> managers
        Run with --edges to see the measured table.
        ```

4. **Si el fallo es legítimo** (el código es correcto y el dibujo está desfasado), edita el dibujo en `scripts/gen_arquitectura_capas.py` y vuelve al paso 2:
    - `LAYER`: capa de cada paquete (de ella se derivan `LEVEL`, las notas de banda y la tabla generada). Actualiza también la tabla de `.ai/architecture.md` § Capas. `LEVEL_OF_LAYER`: nivel de cada capa.
    - `DRAWN`: pares de paquetes con flecha.
    - `EXCLUDED`: módulos que no forman parte de la librería y quedan fuera de la figura.
    - `render_svg()`: nodos (`s.node`), flechas (`s.edge`) y marcas numeradas (`s.badge`).

    Si el fallo indica un import que no debería existir, corrige el código en lugar del dibujo.
5. **Actualiza el pie de figura** de `docs/architecture.md` si han cambiado la versión, la fecha o el número de ficheros medidos («Instantánea de v0.10.0 (…) medida con `ast` sobre N ficheros»).
6. **Revisa la lista «Cómo leerlo»** de esa misma sección si la figura ha ganado o perdido una marca numerada.

---

## 4. Verificación

```bash
python scripts/gen_arquitectura_capas.py
git status --short docs/assets
```

Con el código sin cambios de imports, una segunda ejecución no modifica `docs/assets/`: la salida es determinista y usa saltos de línea LF en cualquier sistema.

Para confirmar que la figura queda incrustada en el sitio:

```bash
zensical build
grep -c '<svg class="arq"' site/architecture/index.html
# 1
```

---

## 5. Variantes y Solución de Problemas

### Ver la tabla medida

```bash
python scripts/gen_arquitectura_capas.py --edges
```

Imprime, por cada par de paquetes, cuántos imports son de módulo, perezosos o de tipado, y sale sin escribir nada. Incluye las filas del `__init__.py` raíz, que la figura no dibuja.

```text
from          -> to            module  lazy  typing
__init__      -> _core              1     0       0
__init__      -> async_utils        1     0       0
```

### Qué no se dibuja

- El `__init__.py` raíz: solo re-exporta la API pública.
- Las flechas de los niveles 2 y 3 hacia Foundation: se resumen en una sola flecha con el número de paquetes que importan de allí.
- Los módulos de `EXCLUDED`, hoy `docs_build_plugin` (plugin de MkDocs).

### Mensajes de error

| Mensaje | Causa probable | Solución |
|---|---|---|
| `package not placed in any layer (add it to LAYER and draw it): X` | Hay un paquete o módulo nuevo en `src/util_bbdd/` | Añádelo a `LAYER` (y a la tabla de `.ai/architecture.md`), dibújalo en `render_svg()` y añade sus flechas a `DRAWN`. Si no forma parte de la librería, añádelo a `EXCLUDED` |
| `package drawn but no longer in src/: X` | Paquete renombrado o eliminado | Quítalo de `LAYER`, de `DRAWN` y de `render_svg()` |
| `drawn but not found in the code: A -> B` | Se eliminó un import, por ejemplo al corregir un desvío | Quita la flecha de `render_svg()` y el par de `DRAWN`. Si era una flecha marcada, retira también su marca y su viñeta en `docs/architecture.md` |
| `found in the code but not drawn: A -> B` | Hay un import nuevo entre paquetes | Añade la flecha en `render_svg()` y el par en `DRAWN`. Si va contra una regla de nivel, revisa primero el import (Regla #6 de `architecture.instructions.md`) |
| `imports that do not go to a strictly lower layer (Regla #6): [...]` | Aparece un import a una capa igual o superior (de módulo, perezoso o de tipado) | Es una violación de la Regla #6: corrígelo en el código; el script no la dibuja |
| `ERROR: cannot parse <fichero>` | Error de sintaxis en un fichero de `src/` | Corrige el fichero; el script no escribe nada con la medición incompleta |
