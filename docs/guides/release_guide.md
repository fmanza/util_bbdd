# Publicar una versión

Pasos para publicar una versión de util_bbdd desde que el desarrollo está terminado en `develop`: comprobar, subir la
versión, construir el wheel, avanzar `main`, crear el tag y completar la release de GitHub. Todos los comandos son
para **Git Bash** (Windows) desde la raíz del repositorio; en Linux o macOS son los mismos salvo donde se indica.

util_bbdd no se publica en PyPI: se instala desde el tag (`pip install "util_bbdd @ git+…@vX.Y.Z"`) y util_bbdd_web
consume el **wheel adjunto a la release** (su ADR-006). Por eso la release no está completa hasta que lleva el wheel
y su `.sha256`.

## 1. Qué se publica y quién lo hace

| Pieza | Dónde | Quién la crea |
|---|---|---|
| Commit `release: vX.Y.Z - <resumen>` | `develop` y `main` | Tú (o `/version-closure`) |
| Tag anotado `vX.Y.Z` | GitHub | Tú |
| Release `vX.Y.Z` con el ZIP de la documentación | GitHub Releases | El workflow `docs-release.yml`, al subir el tag |
| Wheel `util_bbdd-X.Y.Z-py3-none-any.whl` y su `.sha256` en esa release | GitHub Releases | Tú (paso 6) |
| Notas de la release (sección `X.Y.Z` del CHANGELOG) | GitHub Releases | Tú (paso 6) |
| Sitio de documentación | Rama `gh-pages` | El workflow `docs.yml`, al llegar a `main` |
| Release aparte `docs-vX.Y.Z` (ZIP offline) | GitHub Releases | El workflow `docs-zip-release.yml` ([Descarga de la documentación](docs_offline_zip_guide.md)) |

Ramas: solo `main` (lo publicado) y `develop` (integración). `main` avanza siempre por **fast-forward** desde
`develop`: así los hashes de los commits no cambian y lo que se publica es exactamente lo probado.

## 2. Antes de empezar

- `develop` local al día y sin cambios pendientes.
- El CI de `develop` en verde (pestaña *Actions*, workflow `CI`).
- GitHub CLI con sesión iniciada. Si Git Bash no encuentra `gh`:

```bash
export PATH="$PATH:/c/Program Files/GitHub CLI"                       # solo esta terminal
echo 'export PATH="$PATH:/c/Program Files/GitHub CLI"' >> ~/.bashrc   # permanente (terminales nuevas)
gh auth status
```

Variables que usan los pasos siguientes (cámbialas en cada versión):

```bash
cd /c/Desarrollo/python/libs/util_bbdd
OLD=4.6.0      # versión publicada anterior
NEW=4.7.0      # versión que se publica (SemVer: MAJOR rompe la API pública, MINOR añade, PATCH corrige)
git switch develop
git pull --ff-only origin develop
git status                                   # «nothing to commit, working tree clean»
```

## 3. Comprobaciones

Con el entorno de referencia (`pip install -e ".[dev-full]"`, Graphviz y, en Linux, `libmariadb-dev`):

```bash
mkdir -p build/logs
python -m ruff format --check src tests
python -m ruff check src tests
python -m mypy src tests/unit/test_protocol_conformance.py
python -m pytest > build/logs/release_${NEW}_pytest.txt; tail -1 build/logs/release_${NEW}_pytest.txt
zensical build --strict && rm -rf site
python scripts/gen_arquitectura_capas.py     # falla si el diagrama de capas no coincide con el código
```

Si la versión toca motores reales (migración, volcado, carga), ejecuta también la integración con el banco
levantado: `python -m pytest -m integration > build/logs/release_${NEW}_integration.txt`.

## 4. Commit de versión

Con Claude Code, `/version-closure` lo prepara (CHANGELOG, versión y trazabilidad). A mano, son estos cambios
(la lista completa y su porqué: `.github/instructions/sync.instructions.md`):

| Fichero | Cambio |
|---|---|
| `CHANGELOG.md` | `## [Unreleased]` → `## [X.Y.Z] - AAAA-MM-DD` |
| `pyproject.toml` | `version = "X.Y.Z"` |
| `README.md` | `**Version:** X.Y.Z` y `**Current Version: vX.Y.Z** (<resumen>)` |
| `docs/index.md` | `**Version:** X.Y.Z` |
| `docs/roadmap.md` | `**Versión vigente: vX.Y.Z.**` |
| `docs/architecture.md` | Pie de figura: versión, fecha y número de ficheros que da `gen_arquitectura_capas.py` |
| README y `docs/` | Líneas de instalación `…util_bbdd.git@vX.Y.Z` |
| `.ai/CURRENT_STATE.md`, `.ai/sessions/SESSIONS_DIGEST.md` | Fila de la versión y recuento de tests |

Las líneas de instalación se cambian de una vez:

```bash
grep -rl "@v${OLD}" README.md docs | grep -v '^docs/v0.8.0/' | xargs sed -i "s/@v${OLD}/@v${NEW}/g"
grep -rn "@v${OLD}" README.md docs | grep -v '^docs/v0.8.0/'    # no debe salir nada
```

`tests/unit/test_docs_version.py` comprueba que CHANGELOG, README, `docs/index.md`, `docs/roadmap.md` y el pie de
figura coinciden con `pyproject.toml`:

```bash
python -m pytest -q tests/unit/test_docs_version.py
git add CHANGELOG.md pyproject.toml README.md docs .ai        # revisa antes con git status; nunca git add -A
git commit -m "release: v${NEW} - <resumen>"
```

## 5. Wheel y checksum

```bash
rm -rf dist
python -m build                                      # dist/util_bbdd-X.Y.Z-py3-none-any.whl y .tar.gz
(cd dist && sha256sum "util_bbdd-${NEW}-py3-none-any.whl" > "util_bbdd-${NEW}-py3-none-any.whl.sha256")
cat "dist/util_bbdd-${NEW}-py3-none-any.whl.sha256"
```

Prueba el wheel en un entorno limpio, fuera del repositorio (en Linux o macOS, `bin/` en lugar de `Scripts/`):

```bash
python -m venv /tmp/ubb_${NEW}
/tmp/ubb_${NEW}/Scripts/python -m pip install -q "dist/util_bbdd-${NEW}-py3-none-any.whl"
(cd /tmp && /tmp/ubb_${NEW}/Scripts/python -c "import importlib.metadata as m, util_bbdd; print(m.version('util_bbdd'))")
rm -rf /tmp/ubb_${NEW}
```

Debe imprimir `X.Y.Z`.

## 6. Publicar

```bash
# 6.1 develop y main (fast-forward; si falla, para: main tiene algo que develop no tiene)
git push origin develop
git switch main
git pull --ff-only origin main
git merge --ff-only develop
git push origin main
git switch develop

# 6.2 Tag anotado sobre ese commit
git tag -a "v${NEW}" -m "util_bbdd ${NEW}"
git push origin "v${NEW}"
```

Si `git tag` responde que el tag ya existe (lo dejó creado una sesión), comprueba que apunta al commit de versión
antes de subirlo: `git rev-parse "v${NEW}^{commit}" HEAD` debe dar dos veces el mismo hash.

Al llegar el tag, `docs-release.yml` crea la release `vX.Y.Z` con el ZIP de la documentación (tarda menos de un
minuto). Esa release no lleva notas ni wheel: se completan con `gh`, que vale tanto si el workflow ya la creó como si
todavía no:

```bash
# 6.3 Notas: la sección X.Y.Z del CHANGELOG (no puede quedar vacía)
awk -v v="${NEW}" 'index($0, "## [" v "]")==1 {f=1; next} /^## \[/ {f=0} f' CHANGELOG.md > "/tmp/notas_${NEW}.md"
wc -l "/tmp/notas_${NEW}.md"

# 6.4 Crear la release o completar la que creó el workflow
if gh release view "v${NEW}" >/dev/null 2>&1; then
  gh release edit "v${NEW}" --title "v${NEW}" --notes-file "/tmp/notas_${NEW}.md" --latest
else
  gh release create "v${NEW}" --verify-tag --title "v${NEW}" --notes-file "/tmp/notas_${NEW}.md" --latest
fi

# 6.5 Wheel y checksum (--clobber sustituye si ya estaban)
gh release upload "v${NEW}" --clobber \
  "dist/util_bbdd-${NEW}-py3-none-any.whl" \
  "dist/util_bbdd-${NEW}-py3-none-any.whl.sha256"
```

`--verify-tag` impide crear la release si el tag no está en GitHub. Sin `gh`, los pasos 6.4 y 6.5 se hacen en
<https://github.com/fmanza/util_bbdd/releases>: abre la release `vX.Y.Z` (o *Draft a new release* con ese tag),
pega las notas, arrastra el `.whl` y el `.whl.sha256`, marca *Set as the latest release* y guarda.

## 7. Comprobar

```bash
gh release view "v${NEW}"                      # assets: wheel, .sha256 y util_bbdd-docs-X.Y.Z.zip
mkdir -p "/tmp/rel_${NEW}" && cd "/tmp/rel_${NEW}"
gh release download "v${NEW}" -p "util_bbdd-${NEW}-py3-none-any.whl*"
sha256sum -c "util_bbdd-${NEW}-py3-none-any.whl.sha256"     # «OK»
cd - >/dev/null
git ls-remote origin main develop "refs/tags/v${NEW}"       # main, develop y el tag en el mismo commit
```

Comprueba también en *Actions* que `CI` (main), `Docs` y `Docs Release ZIP` terminan en verde.

Después, si util_bbdd_web debe usar esta versión, sigue su guía [Publicar una versión](https://github.com/fmanza/util_bbdd_web/blob/develop/docs/guides/publicar_version.md) (paso «Subir util_bbdd»).

## 8. Si algo sale mal

| Situación | Qué hacer |
|---|---|
| `git merge --ff-only develop` falla | `main` tiene commits que `develop` no tiene. No fuerces: `git log develop..main` y llévalos a `develop` primero |
| El tag apunta a un commit equivocado y **nadie lo ha usado** | `git push origin :refs/tags/vX.Y.Z`, `git tag -d vX.Y.Z`, `gh release delete vX.Y.Z` y vuelve al paso 6.2 |
| El tag o el wheel ya se han usado (util_bbdd_web lo fijó, alguien lo instaló) | No se reutiliza una versión publicada: corrige en `develop` y publica `X.Y.Z+1` |
| El workflow `Docs Release ZIP` falló | La release se completa igual con el paso 6.4; relanza el workflow desde *Actions* (`workflow_dispatch`) |
| `gh: command not found` | Ver [Antes de empezar](#2-antes-de-empezar) o usa la web de Releases |

## 9. Ramas y Dependabot

Solo se mantienen `main` y `develop` (más `gh-pages`, que escribe el workflow `docs.yml`: no la borres a mano, el
sitio de documentación sale de ella). Las ramas `dependabot/*` existen solo mientras su PR está abierto.

`.github/dependabot.yml` limita esas ramas a **una por ecosistema y mes**:

- `schedule.interval: monthly`: una revisión al mes (también existen `quarterly`, `semiannually` y `yearly`).
- `groups` con `patterns: ["*"]`: todas las actualizaciones del ecosistema en un solo PR y una sola rama.
- `open-pull-requests-limit: 1` y `target-branch: develop`: como mucho un PR abierto, siempre contra `develop`.

Para que la rama desaparezca al cerrar su PR, activa una vez **Settings → General → Pull Requests → Automatically
delete head branches**. Los PR de seguridad (*Dependabot security updates*, en Settings → Code security) son aparte:
no siguen este calendario.

Otras opciones, si se quiere menos:

| Objetivo | Cambio en `.github/dependabot.yml` |
|---|---|
| Menos a menudo | `interval: quarterly` en cada entrada |
| Solo PR de seguridad | `open-pull-requests-limit: 0` en cada entrada (y *Dependabot security updates* activado) |
| Ninguno | Borrar el fichero y desactivar *Dependabot security updates* en Settings → Code security |

Limpiar las ramas `dependabot/*` que queden (cierra sus PR):

```bash
git fetch --prune origin
for b in $(git branch -r --format='%(refname:lstrip=3)' | grep '^dependabot/'); do git push origin --delete "$b"; done
```
