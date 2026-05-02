# Prompt: functional_doc — Documentación funcional (Product Owner)

Genera documentación funcional para módulos de **util_bbdd** (framework multi-base de datos para introspección de esquemas, operaciones bulk y documentación de BD).

## Instrucción al modelo

```
Actúa como Senior Product Owner especializado en herramientas de datos e infraestructura.

Analiza el módulo Python proporcionado de util_bbdd.
util_bbdd es un framework multi-base de datos que conecta a PostgreSQL, MySQL, MariaDB, Oracle,
SQL Server, SQLite, Snowflake y Redshift. Permite extraer metadatos de esquemas, ejecutar
operaciones bulk desde DataFrames, comparar esquemas entre dos bases de datos (generando
diferencias en formato HTML, Excel, Word, Markdown y script SQL de nivelación) y generar
documentación técnica de BD en Word, Excel y HTML.
Sus usuarios son desarrolladores, ingenieros de datos, DBAs y equipos DevOps.

Genera un documento Markdown con estas secciones en este orden exacto:

## Objetivo de negocio
Qué problema de negocio resuelve este módulo específico (1-2 párrafos).
Evita jerga técnica. Habla en términos de valor para el usuario final.

## Precondiciones
Lista de requisitos que deben cumplirse antes de usar este módulo.
Incluye: datos de entrada, configuraciones previas, dependencias externas.

## Flujo principal del usuario
Un diagrama Mermaid sequenceDiagram que muestre la interacción entre:
- El actor principal (usuario, pipeline CI/CD, etc.)
- Los componentes del módulo (sin nombres de clases internas)
- El sistema externo relevante (base de datos: PostgreSQL/MySQL/Oracle/etc., sistema de ficheros)
- La salida generada

## Reglas de negocio críticas
Tabla con columnas: | Regla | Descripción | Impacto si se viola |
Incluye solo las reglas con impacto en la corrección del resultado.

## Límites y exclusiones
Qué NO hace este módulo. Máximo 5 ítems en lista.

---

Restricciones:
- NO expliques nombres de variables, clases internas ni implementación
- NO menciones rutas de archivos a menos que sean de configuración del usuario
- USA terminología de negocio, no técnica
- Responde SOLO con el Markdown, sin texto introductorio ni cierre
```

## Cómo usar este prompt

### En Claude Code

```
Lee el archivo [ruta_del_módulo] y genera la documentación funcional usando el
prompt en .github/prompts/functional_doc.prompt.md.
Guarda el resultado en docs/functional/[nombre_módulo].md
```

### En Copilot Chat

```
#file:.github/prompts/functional_doc.prompt.md
#file:[ruta_del_módulo]

Genera la documentación funcional del módulo indicado.
```

### Con API de Anthropic (Claude)

```python
import anthropic

client = anthropic.Anthropic()

with open("src/util_bbdd/metadata/manager.py") as f:
    codigo = f.read()

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[
        {
            "role": "user",
            "content": f"""Actúa como Senior Product Owner especializado en herramientas de DevOps.

Analiza el siguiente módulo Python de util_bbdd y genera documentación funcional.

MÓDULO:
```python
{codigo}
```

Genera un documento Markdown con:
1. **Objetivo de negocio** — qué problema resuelve (1-2 párrafos, sin jerga técnica)
2. **Precondiciones** — lista de lo que debe existir antes de usar el módulo
3. **Flujo principal** — diagrama Mermaid sequenceDiagram (actor → módulo → salida)
4. **Reglas de negocio críticas** — tabla: Regla | Descripción | Impacto si se viola
5. **Límites** — qué NO hace este módulo (máx. 5 ítems)

Responde SOLO con el Markdown."""
        }
    ]
)
print(message.content[0].text)
```

### Con API de OpenAI

```python
from openai import OpenAI

client = OpenAI()

with open("src/util_bbdd/metadata/manager.py") as f:
    codigo = f.read()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "Eres un Senior Product Owner especializado en herramientas DevOps. Generas documentación funcional clara para equipos no técnicos."
        },
        {
            "role": "user",
            "content": f"""Analiza el módulo Python de util_bbdd y genera documentación funcional en Markdown.

MÓDULO:
```python
{codigo}
```

Secciones requeridas:
1. Objetivo de negocio (sin jerga técnica)
2. Precondiciones (lista)
3. Flujo principal (diagrama Mermaid sequenceDiagram)
4. Reglas de negocio críticas (tabla)
5. Límites del módulo (lista, máx. 5)

Responde SOLO con el Markdown."""
        }
    ]
)
print(response.choices[0].message.content)
```

## Output esperado

Un fichero Markdown con las 5 secciones, con al menos un diagrama Mermaid `sequenceDiagram`
y una tabla de reglas de negocio. El lenguaje debe ser comprensible por un jefe de proyecto
sin conocimientos de Python.
