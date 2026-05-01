# Prompt: technical_doc — Documentación técnica con Mermaid

Genera diagramas Mermaid.js y documentación técnica para módulos de **util_bbdd**.

## Instrucción al modelo

```
Actúa como arquitecto de software senior especializado en Python y herramientas DevOps.

Analiza el módulo [NOMBRE_MÓDULO] de util_bbdd (extractor de timelogs de GitLab).
util_bbdd usa: python-gitlab, xlsxwriter, pandas, TOML config, Decimal para precisión.

Genera documentación técnica en Markdown con estas secciones:

## Responsabilidad del módulo
Una frase. Qué hace exactamente este módulo en el sistema.

## Diagrama
Elige el tipo de diagrama más apropiado:
- `sequenceDiagram` → si el módulo procesa requests/responses o tiene flujo I/O
- `flowchart TD` → si el módulo tiene lógica de decisión o pipeline de transformación
- `classDiagram` → si el módulo expone jerarquía de clases relevante para el consumidor

Criterios del diagrama:
- Omite: nombres de BD, puertos, variables internas, rutas de ficheros de implementación
- Incluye: actores externos, operaciones de negocio, flujo de datos, puntos de decisión
- Máximo 12 nodos para legibilidad sin zoom
- Usa etiquetas en español para actores y acciones

## API pública
Tabla con columnas: | Función/Clase | Firma simplificada | Descripción | Retorna |
Solo las funciones/clases exportadas en __all__ o __init__.py.

## Contrato de entrada
Parámetros de las funciones principales con tipos y restricciones.
Formato: tabla con columnas: | Parámetro | Tipo | Descripción | Restricciones |

## Contrato de salida
Qué retorna cada función principal. Tipos, estructura de datos, casos especiales.

## Errores y casos especiales
Qué ocurre con entradas inválidas, valores fuera de rango, o conexión fallida.

---

Restricciones:
- SOLO incluye lo exportado públicamente, no implementación interna
- El diagrama debe ser código Mermaid válido (sin bloques de código extra)
- Responde SOLO con el Markdown
```

## Cómo usar este prompt

### En Claude Code

```
Lee el archivo [ruta_del_módulo] y genera documentación técnica con diagrama Mermaid
usando el prompt en .github/prompts/technical_doc.prompt.md.
Guarda el resultado en docs/[sección_apropiada]/[nombre_módulo].md
```

### En Copilot Chat

```
#file:.github/prompts/technical_doc.prompt.md
#file:[ruta_del_módulo]

Genera la documentación técnica con diagrama Mermaid del módulo indicado.
```

### Con API de Anthropic (Claude)

```python
import anthropic

client = anthropic.Anthropic()

with open("src/util_bbdd/timelog/project_loader.py") as f:
    codigo = f.read()

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[
        {
            "role": "user",
            "content": f"""Actúa como arquitecto de software senior especializado en Python.

Analiza el siguiente módulo de util_bbdd y genera documentación técnica.

MÓDULO: project_loader.py
```python
{codigo}
```

Genera Markdown con:
1. **Responsabilidad** — una frase
2. **Diagrama** — elige entre sequenceDiagram, flowchart TD o classDiagram según el módulo.
   Criterios: omite variables internas y rutas, incluye actores y flujo de datos, máx. 12 nodos.
3. **API pública** — tabla: Función | Firma | Descripción | Retorna
4. **Contrato de entrada** — tabla: Parámetro | Tipo | Restricciones
5. **Contrato de salida** — tipos, estructura, casos especiales
6. **Errores** — qué ocurre con entradas inválidas

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

with open("src/util_bbdd/timelog/project_loader.py") as f:
    codigo = f.read()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "Eres un arquitecto de software senior. Generas documentación técnica precisa con diagramas Mermaid.js para equipos de desarrollo."
        },
        {
            "role": "user",
            "content": f"""Analiza el módulo Python y genera documentación técnica en Markdown.

MÓDULO:
```python
{codigo}
```

Secciones requeridas:
1. Responsabilidad (1 frase)
2. Diagrama Mermaid (sequenceDiagram / flowchart TD / classDiagram — elige el más apropiado)
   - Omite variables internas y rutas de implementación
   - Incluye actores y flujo de datos
   - Máximo 12 nodos
3. API pública (tabla)
4. Contrato de entrada (tabla)
5. Contrato de salida
6. Errores y casos especiales

Responde SOLO con el Markdown."""
        }
    ]
)
print(response.choices[0].message.content)
```

## Tipos de diagrama por módulo

| Módulo | Diagrama recomendado | Motivo |
|---|---|---|
| `load_gitlab.py` | `sequenceDiagram` | Flujo auth → conexión → sesión |
| `project_loader.py` | `sequenceDiagram` | Request → filtrado → lista proyectos |
| `time_utils.py` | `flowchart TD` | Lógica de decisión en parseo |
| `issue_helpers.py` | `flowchart TD` | Clasificación incidente/severidad |
| `excel_formatter.py` | `flowchart TD` | Pipeline de formateo por hojas |
| `calendar.py` | `flowchart TD` | Cálculo semana ISO/fiscal |
| `decimal_utils.py` | `classDiagram` | Contratos de funciones utilitarias |
| `crear_csv.py` | `sequenceDiagram` | Proceso datos → fichero CSV |
| `crear_json.py` | `sequenceDiagram` | Proceso datos → fichero JSON |

## Output esperado

Markdown con las 6 secciones, incluyendo un bloque mermaid válido que se renderiza
correctamente en MkDocs Material y en GitHub.
