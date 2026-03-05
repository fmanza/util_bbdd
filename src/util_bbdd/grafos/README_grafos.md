# Generador de Grafos de Relaciones entre Tablas

Esta herramienta genera grafos visuales de las relaciones de primer nivel entre tablas de bases de datos.

## 🚀 Instalación de Dependencias

### Opción 1: Graphviz (Recomendado)
```bash
# Instalar librería Python
pip install graphviz

# Instalar ejecutable Graphviz
# Windows:
# 1. Descargar desde https://graphviz.org/download/
# 2. Instalar y agregar al PATH
# 3. Reiniciar terminal

# Linux/Mac:
sudo apt-get install graphviz  # Ubuntu/Debian
brew install graphviz              # macOS
```

### Opción 2: Matplotlib + NetworkX
```bash
pip install matplotlib networkx
```

### Opción 3: Ambas (Máxima Compatibilidad)
```bash
pip install graphviz matplotlib networkx
```

## 📋 Características

- **Multi-base de datos**: MariaDB, Oracle, PostgreSQL, HSQLDB
- **Relaciones de primer nivel**: FKs salientes y entrantes
- **Múltiples formatos**: Graphviz y Matplotlib
- **Reportes detallados**: JSON con información completa
- **Procesamiento por lote**: Generar grafos para todas las tablas
- **Integración modular**: Compatible con arquitectura existente

## 🎯 Uso Básico

### Generar grafo para una tabla específica

```python
from pathlib import Path
from conn_params_builder import build_conn_params
from database_manager import DatabaseManager
from relationship_generator import DatabaseRelationshipGenerator

# Parámetros de conexión (ajusta según tu BD)
conn_params = build_conn_params(
  "postgresql",
  user="tu_usuario",
  password="tu_password",
  host="localhost",
  port=5432,
  database="tu_base_de_datos",
  schema="public",
)

# Crear gestor de base de datos
db_manager = DatabaseManager(
    db_type="postgresql",  # mariadb, oracle, postgresql, hsqldb
  conn_params=conn_params
)

# Crear generador con el DatabaseManager
graph_gen = DatabaseRelationshipGenerator(db_manager=db_manager)

# Listar tablas disponibles
tablas = graph_gen.list_available_tables()
print(f"Tablas: {tablas}")

# Generar grafo para una tabla
if tablas:
    tabla = tablas[0]
    archivos = graph_gen.generate_table_graph(
        tabla,
        formats=['graphviz', 'matplotlib']
    )
    print(f"Archivos generados: {archivos}")

# Obtener resumen de relaciones
resumen = graph_gen.get_table_relations_summary(tabla)
print(f"Relaciones de {tabla}:")
print(f"  Total: {resumen['total_relaciones']}")
print(f"  Salientes: {resumen['relaciones_salientes']}")
print(f"  Entrantes: {resumen['relaciones_entrantes']}")
```

### Generar grafos para todas las tablas

```python
# Generar grafos para todas las tablas
resultados = graph_gen.generate_all_tables_graphs(
    formats=['graphviz']  # Solo un formato para velocidad
)

print(f"Procesadas {len(resultados)} tablas")
```

## 📊 Formatos de Salida

### Archivos Generados

Por cada tabla se generan:

1. **Grafo Graphviz**: `{tabla}_relations_graphviz.png`
   - Visualización profesional
   - Configurable con DOT
   - Soporta múltiples formatos (PNG, SVG, PDF)

2. **Grafo Matplotlib**: `{tabla}_relations_matplotlib.png`
   - Mayor compatibilidad
   - Sin dependencias externas
   - Bueno para integración web

3. **Reporte JSON**: `{tabla}_relations_report.json`
   ```json
   {
     "table_name": "usuarios",
     "total_relations": 3,
     "outgoing_relations": {
       "count": 2,
       "details": [
         {
           "target_table": "perfiles",
           "constraint_name": "fk_usuario_perfil",
           "source_column": "perfil_id",
           "target_column": "id"
         }
       ]
     },
     "incoming_relations": {
       "count": 1,
       "details": [...]
     },
     "related_tables": ["perfiles", "roles"],
     "database_type": "postgresql"
   }
   ```

## 🎨 Visualización de Grafos

### Elementos del Grafo

- **Nodos**: Representan tablas
  - **Tabla principal**: Color coral, más grande
  - **Tablas relacionadas**: Color azul estándar

- **Aristas**: Representan relaciones FK
  - **Etiquetas**: `columna_origen → columna_destino`
  - **Nombre de constraint**: Abajo de la etiqueta

- **Layout**: Izquierda a derecha (LR) para mejor lectura

## 🔧 Configuración por Tipo de Base de Datos

### MariaDB
```python
conn_params = build_conn_params(
  "mariadb",
  user="usuario",
  password="password",
  host="localhost",
  port=3306,
  database="base_de_datos",
)
```

### PostgreSQL
```python
conn_params = build_conn_params(
  "postgresql",
  host="localhost",
  port=5432,
  database="base_de_datos",
  user="usuario",
  password="password",
  schema="public",
)
```

### Oracle
```python
conn_params = build_conn_params(
  "oracle",
  user="usuario",
  password="password",
  dsn="localhost:1521/servicio",
)
```

### HSQLDB
```python
conn_params = build_conn_params(
  "hsqldb",
  jdbc_driver="org.hsqldb.jdbcDriver",
  jdbc_url="jdbc:hsqldb:file:/ruta/bd;shutdown=true",
  jdbc_jar="/ruta/hsqldb.jar",
  user="SA",
  password="",
  schema="PUBLIC",
)
```

## 📝 Ejemplos de Uso

### Ejecutar ejemplo básico
```bash
python ejemplo_grafos.py
```

### Generar grafos para tabla específica
```python
# Obtener resumen detallado
resumen = graph_gen.get_table_relations_summary("usuarios")

# Mostrar relaciones salientes
print("Relaciones salientes:")
for rel in resumen['detalle_salientes']:
    print(f"  → {rel}")

# Mostrar relaciones entrantes
print("Relaciones entrantes:")
for rel in resumen['detalle_entrantes']:
    print(f"  ← {rel}")
```

### Procesamiento por lote con filtro
```python
tablas = graph_gen.list_available_tables()

# Filtrar tablas que contienen "user"
user_tables = [t for t in tablas if 'user' in t.lower()]

for tabla in user_tables:
    try:
        archivos = graph_gen.generate_table_graph(tabla, ['graphviz'])
        print(f"✓ {tabla}: {archivos.get('graphviz', 'Error')}")
    except Exception as e:
        print(f"✗ {tabla}: {e}")
```

## 🐛 Solución de Problemas

### Error: "Graphviz no disponible"
```bash
# Instalar Graphviz
pip install graphviz

# Verificar instalación
python -c "import graphviz; print('✓ Graphviz disponible')"
```

### Error: "Tablas no encontradas"
- Verificar nombre de base de datos/esquema
- Comprobar permisos del usuario
- Usar `list_available_tables()` para verificar

### Error: "Cannot connect to database"
- Verificar parámetros de conexión
- Comprobar que el servicio de BD esté activo
- Validar credenciales y firewall

## 📚 Referencia de API

### DatabaseRelationshipGenerator

#### Métodos Principales
- `list_available_tables()`: Lista tablas disponibles
- `generate_table_graph(table, formats)`: Genera grafo para una tabla
- `generate_all_tables_graphs(formats)`: Genera para todas las tablas
- `get_table_relations_summary(table)`: Obtiene resumen de relaciones
- `close()`: Cierra conexión a BD

#### Parámetro de Constructor
- `db_manager`: Instancia de DatabaseManager configurada

## 🔄 Integración con Arquitectura Modular

El generador de grafos se integra perfectamente con la arquitectura modular existente recibiendo una instancia ya configurada de DatabaseManager:

```python
from conn_params_builder import build_conn_params
from database_manager import DatabaseManager
from relationship_generator import DatabaseRelationshipGenerator

# Crear DatabaseManager con configuración específica
db_manager = DatabaseManager(
    db_type="postgresql",
  conn_params=build_conn_params(
    "postgresql",
    host="localhost",
    user="usuario",
    password="pass",
    database="mi_bd",
    schema="public",
  )
)

# Pasar DatabaseManager al generador de grafos
graph_generator = DatabaseRelationshipGenerator(db_manager=db_manager)

# Generar grafos usando la misma conexión
tablas = graph_generator.list_available_tables()
resultados = graph_generator.generate_all_tables_graphs(['graphviz'])
```

## 📈 Mejoras Futuras

- [ ] Soporte para relaciones de niveles profundos
- [ ] Filtros por tipo de relación
- [ ] Exportación a otros formatos (PlantUML, Mermaid)
- [ ] Interfaz web para exploración interactiva
- [ ] Integración con sistemas de documentación
