# Mensaje para Commit y Push a GitHub

## Commit Message (Conventional Commits)

```
chore(migrate): collation MariaDB por defecto utf8mb4_uca1400_ai_ci

Cambia el valor por defecto de la collation para destinos MariaDB de
utf8mb4_unicode_ci a utf8mb4_uca1400_ai_ci (UCA 14.0.0, acento- y
mayúsculas-insensible). El charset por defecto sigue siendo utf8mb4.

### Cambios de código

- migrate/charset.py: DEFAULT_COLLATION = "utf8mb4_uca1400_ai_ci".
- migrate/charset.py: utf8mb4_uca1400_ai_ci añadida a VALID_COLLATIONS y a
  CHARSET_COLLATION_MAP["utf8mb4"] para que el nuevo default supere la
  validación del constructor de MigrationPlanner.
- migrate/__init__.py: docstrings de ejemplo (3×) actualizados al nuevo default.

### Documentación

- README.md, docs/DDL_MIGRATION_GUIDE.md, docs/examples/migrate-postgresql-source.py
  y docs/examples/migrate-sqlserver-source.md: nuevo default + nota
  "requiere MariaDB >= 10.10".

### Compatibilidad

- utf8mb4_uca1400_ai_ci solo existe en MariaDB >= 10.10. Las migraciones generadas
  con el default ahora requieren esa versión mínima. Para MariaDB < 10.10 o MySQL,
  pasar collation= explícito; utf8mb4_unicode_ci sigue siendo una opción válida.

### Validación

- pytest -k "charset or migrate": 1346 passed, 2481 deselected.

### CHANGELOG

- Entrada en [Unreleased] › Changed con aviso de cambio de comportamiento
  (potencialmente breaking para MariaDB < 10.10).

### Trazabilidad

- .ai/sessions/2026-06-04-mariadb-default-collation-uca1400/ + entrada en INDEX.md.
```

---

## Comandos sugeridos (NO ejecutados — requieren confirmación)

> Estás en la rama `develop` (no es la rama por defecto `main`), por lo que se
> puede commitear directamente.

```bash
# 1. Revisar qué se va a incluir
git status

# 2. Añadir código, docs y trazabilidad (NO incluye .claude/settings.json — ver nota)
git add src/util_bbdd/migrate/charset.py \
        src/util_bbdd/migrate/__init__.py \
        CHANGELOG.md \
        README.md \
        docs/DDL_MIGRATION_GUIDE.md \
        docs/examples/migrate-postgresql-source.py \
        docs/examples/migrate-sqlserver-source.md \
        .ai/sessions/

# 3. Commit
git commit -F .ai/sessions/2026-06-04-mariadb-default-collation-uca1400/GITHUB_COMMIT_MESSAGE.md
# (o pegar solo el bloque de Conventional Commits)

# 4. Push
git push origin develop
```

---

## Puntos de decisión antes de subir

1. **`.claude/settings.json` (modificado)**: el working tree arrastra cambios en hooks
   (quitar `optional` de mypy/pytest) y un bloque `permissions.allow`. Es configuración
   local/de herramientas, ajena a este cambio funcional. NO está incluido en el `git add`
   sugerido. Decide si lo commiteas aparte (p.ej. `chore(claude): ...`).

2. **CHANGELOG.md**: ✅ AÑADIDO — entrada en [Unreleased] › Changed con aviso de cambio
   de comportamiento (potencialmente breaking para MariaDB < 10.10).

3. **Sin bump de versión**: `pyproject.toml` sigue en 0.10.0. Si se considera el cambio de
   default como relevante para consumidores, valorar bump MINOR.
```
