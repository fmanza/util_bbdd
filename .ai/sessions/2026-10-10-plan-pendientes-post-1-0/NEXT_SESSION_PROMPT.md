# Prompt para la siguiente sesión (tras v1.1.0)

Copiar el bloque en una sesión nueva de Claude Code abierta en la raíz del repositorio.

````text
Sesión nueva: revisión página a página de la documentación restante de util_bbdd (nivel 2, pendiente D2).

Base: develop = main = v1.1.0 (e4467d25), publicada con tag. Python 3.12+, API pública estable bajo SemVer.

Lee primero:
- .ai/sessions/2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md (método y tipos de error encontrados)
- .ai/sessions/2026-10-10-api-1-0-final/02_DOC_REVIEW.md (método original)
- .ai/sessions/2026-10-10-plan-pendientes-post-1-0/03_DOCS_PENDIENTES.txt (las 82 páginas que faltan)
- .github/DOCUMENTATION_STANDARD.md y .github/instructions/docs.instructions.md

Alcance: las 82 páginas de 03_DOCS_PENDIENTES.txt (incluye docs/examples/migrate_*). Ya revisadas, no repetir:
las de 02_DOC_REVIEW.md de ambas sesiones, README.md, docs/index.md, docs/installation.md y docs/roadmap.md.

Método (por página):
1. Comprobador automático de imports y de métodos de los puntos de entrada (bloques recorridos por líneas, no con
   regex de fences) contra el paquete instalado.
2. Lectura completa. Verificar cada afirmación comprobable contra el código: firmas (inspect), parámetros reales
   (connection/config.py), excepciones que se lanzan de verdad, extras de pyproject.toml, CLI de los scripts
   (--help / list), códigos de aviso, rutas de ficheros.
3. Ejecutar los ejemplos que se toquen (SQLite en el scratchpad; motores reales con el banco).
4. Cifras de rendimiento: solo con su sesión de medición; si no hay fuente, se quitan o se marcan como pendientes de
   verificación. No inventar nada.
5. Errores típicos ya vistos: SQL inventado o de otro motor, CLI inexistente, `pip install util_bbdd` (no está en
   PyPI: git+…@v1.1.0), drivers antiguos (psycopg2, cx_Oracle), «wrappers» de paramstyle (obsoletos desde ADR-003),
   max_overflow en PostgreSQL, destinos de migrate sin MySQL, páginas que se repiten entre sí.

Tandas (un commit docs: por tanda, registro en 02_DOC_REVIEW.md de la sesión nueva):
1. docs/api/ (26)  2. docs/functional/ (15)  3. docs/examples/ (17, ejecutando cada ejemplo)
4. docs/guides/ (20) + docs/architecture.md, docs/downloads.md, docs/legacy_versions.md, docs/ai-config/claude.md

Si al ejecutar un ejemplo aparece un fallo de la librería (como el de asyncpg o el de pyodbc en v1.1.0), DETENTE y
pregúntame cómo tratarlo (/hotfix aparte). Si dos o más páginas repiten contenido, propónme consolidarlas antes de
corregirlas una a una.

Pendiente abierto que NO es de esta sesión: driver_name por defecto de SQL Server (ODBC Driver 17; detectar el
instalado sería /new-feature para 1.2.0).

Sesión en .ai/sessions/<fecha>-docs-review-nivel-2/ desde .ai/sessions/TEMPLATE/. Primero PLAN + AUDIT_PLAN
(inventario por tanda, riesgos) y espera mi aprobación.

Restricciones:
- Puerta al cerrar cada tanda: zensical build --strict y el comprobador de imports sin hallazgos; al cerrar la
  sesión, además ruff, ruff format, mypy, pytest completo dos veces (sin las URL del banco y con ellas:
  scripts/bench_env.example.sh + JAVA_HOME="C:/Program Files/Java/jdk-25") y python -m build.
- Commits locales con Conventional Commits; nada de git add -A (añade solo tus rutas).
- Sin push, tags ni merge a main hasta que lo autorice de forma explícita.
- Scripts con regex o \| con Write (los heredocs de Bash se comen un nivel de barras invertidas).
- Logs y salidas en build/logs/.
````
