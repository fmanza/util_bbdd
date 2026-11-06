# ADR-006: `catalog.json` de la documentación Markdown como contrato versionado

## 1. Contexto y Problema

Desde 5.3.0, `DatabaseDocumentation(formatos=["markdown"])` genera un fichero `.md` por tabla, vista y rutina para
publicarlo con Zensical o MkDocs y para que una IA lo interprete y lo trace con el código y con la documentación
funcional y técnica (sesión `2026-11-05-doc-markdown`).

Las páginas sirven a las personas, pero no son una buena fuente para máquinas:

- las tablas Markdown dependen de las cabeceras de `headers_config.json`, que el usuario puede cambiar;
- el texto está escapado;
- para conocer el esquema completo hay que leer cientos de ficheros.

Además, la comparación entre dos generaciones (`CHANGES.md`) no puede usar `SchemaComparator`: necesita dos
conexiones vivas y el snapshot de metadatos no se serializa. Hace falta un catálogo estructurado que se guarde con
cada generación y que siga siendo legible por versiones futuras de la librería, por util_bbdd_web y por herramientas
externas.

## 2. Decisión

Cada generación Markdown escribe `docs/catalog.json`. Por defecto está activado; se desactiva con
`imprimir["markdown"]["catalog_json"] = False`. Es un **contrato público versionado**:

1. **Identificación**:
   - `"format": "util_bbdd.doc.catalog"` y `"format_version": 1`;
   - `engine`, `schema` y `database`;
   - `selection`: los tipos de objeto pedidos (`tables`, `views`, `procedures`, `functions`), para no confundir un
     objeto no pedido con uno borrado.
2. **Objetos**:
   - `objects`: solo los documentados, ordenados por tipo (tablas, vistas, rutinas) y por nombre sin distinguir
     mayúsculas;
   - cada objeto lleva `id` (`<kind>:<schema>.<nombre>`), `kind`, `name`, `schema`, `comment`, `path` (relativa a
     `docs/`) y `hash` (sha256 del registro en JSON canónico);
   - las tablas añaden `columns` (`name`, `ordinal`, `type`, `nullable`, `default`, `comment`, `identity`,
     `generated`), `pk`, `fk_out` (con `ref` como id y las acciones `on_delete`/`on_update`), `fk_in`, `uniques` e
     `indexes`;
   - las vistas añaden `columns` y `definition_hash`;
   - las rutinas añaden `signatures` y `definition_hash`;
   - las definiciones completas no se guardan: están en la página del objeto.
3. **Coherencia con las páginas**: el front matter de cada página publica el mismo `id` y el mismo `hash` que el
   catálogo.
4. **Determinismo**: sin fechas ni datos de la ejecución; JSON con claves ordenadas, `indent=2` y UTF-8. La fecha de
   generación está solo en `manifest.json`, fuera de `docs/`.
5. **Compatibilidad**:
   - `format_version` sube **solo** con cambios incompatibles: quitar o renombrar un campo, o cambiar su tipo o su
     significado;
   - los campos nuevos opcionales no la suben, así que los lectores deben ignorar los campos que no conozcan;
   - la librería sabe leer todas las versiones publicadas para comparar con generaciones anteriores;
   - `id` y `path` son estables mientras no cambie el nombre del objeto.

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Una IA o una herramienta lee el esquema completo con una sola lectura, sin depender de cabeceras ni del escape del Markdown |
| Ventaja | Comparar dos generaciones (`CHANGES.md`) no necesita conexión a la base de datos |
| Ventaja | El `id` estable permite referenciar objetos desde el código, los requisitos o el mapa de trazabilidad |
| Compromiso | Cambiar la estructura obliga a versionar y a mantener la lectura de versiones antiguas |
| Compromiso | Con miles de tablas y muchas columnas, el fichero crece (sin definiciones completas, del orden de 1 KB por columna en el peor caso) |
| Riesgo aceptado | Sin JSON Schema formal en 5.3.0: el contrato lo fijan este ADR y los tests (`tests/unit/test_doc_markdown_catalog.py`) |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| Solo front matter en cada página | Sin fichero adicional | Exige leer cientos de ficheros; el front matter se limita a lo esencial para no cargar las páginas | Insuficiente para máquinas y para comparar generaciones |
| Serializar `SchemaSnapshot` (`metadata/`) | Reutilizable por `comparar` y la web | Contrato interno de `metadata/` expuesto; cambio mayor fuera del alcance | Queda como fase posterior (comparación por snapshots) |
| JSON Lines (un objeto por línea) | Lectura en streaming | Menos legible en revisiones de git y para personas | El tamaño esperado no lo justifica |
| Incluir definiciones completas de vistas y rutinas | Comparación de texto sin leer páginas | Duplica el contenido de las páginas y multiplica el tamaño | Basta el hash para detectar cambios |

## 5. Estado y Revisión

**Estado:** ACEPTADO

Redactado en el grupo C de la sesión `2026-11-05-doc-markdown` y aprobado por el usuario el 2026-11-06 (condición
CC1 del grupo).

### Enmienda 2026-11-06 (5.4.0): `manifest.json` → `pages`

`catalog.json` sigue siendo el catálogo de **objetos**; no gana páginas auxiliares. El índice de **todas** las
páginas (portada, índices, letras, objetos, base de datos, trazabilidad y cambios) va en `manifest.json`, que pasa a
ser también un contrato versionado (`format: util_bbdd.doc.markdown`, `format_version` 2; G51 de util_bbdd_web):

- `pages`: una entrada por cada `.md` de `docs/`, en el orden de la `nav`; `path`, `title` (texto plano, sin escapes:
  texto no confiable de la BD), `section`, `role` y, según el papel, `letter` o `id` + `kind` (los mismos que
  `catalog.json`).
- Aditivo: un lector del v1 sigue funcionando y util_bbdd sigue leyendo un manifiesto v1 para limpiar huérfanos.
- Se descartó un `nav.json` aparte en `docs/` (un fichero más en el sitio publicado) y ampliar `catalog.json` (rompería
  su sentido de catálogo de objetos y su comparación entre generaciones).

Sesión `2026-11-06-gaps-g50-g51`.

Fecha de última revisión: 2026-11-06
