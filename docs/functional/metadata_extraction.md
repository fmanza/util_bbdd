# Extracción de Metadatos

## 1. Descripción General

Permite consultar la estructura de cualquier base de datos conectada — tablas, columnas, claves, índices — sin escribir SQL específico para cada motor. La primera consulta va a la base de datos; las siguientes se sirven desde una caché en memoria, reduciendo la carga sobre los servidores de datos en flujos de introspección repetitivos.

Es el componente que habilita a cualquier proceso automatizado (generación de documentación, comparación de esquemas, auditoría de modelos) a conocer la estructura de la BD sin intervención humana.

**Precondiciones:**

- Conexión activa a la base de datos, previamente configurada con las credenciales correctas
- El usuario o proceso tiene permisos de lectura sobre los metadatos del esquema (`information_schema`, catálogos del motor)
- Tipo de motor declarado: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite o HSQLDB

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Caché por sesión | Los resultados se guardan en memoria durante la vida del extractor | Cambios de esquema realizados por otros procesos durante la sesión no se reflejan automáticamente |
| Normalización entre motores | Los metadatos se homogeneizan: misma estructura de resultado independientemente del motor | Código que dependa del formato nativo de un motor deja de ser portátil al cambiar de motor |
| Solo estructura, no datos | Consulta definiciones del esquema, no filas de las tablas | El resultado nunca contiene datos sensibles de negocio |
| Invalidación granular | El caché de una tabla concreta se puede limpiar sin reiniciar toda la sesión | Si se invalida el caché completo se incurre en coste de recarga de todos los metadatos |
| Forzar recarga puntual | Con la opción correspondiente se salta el caché y se va directamente a la BD | Mayor carga en BD; usar solo cuando se sabe con certeza que el esquema cambió |

## 3. Casos de Uso

### Flujo principal

```mermaid
sequenceDiagram
    actor App as Aplicación / Pipeline
    participant Meta as Extractor de Metadatos
    participant Cache as Caché en memoria
    participant BD as Base de datos

    App->>Meta: Solicitar tablas / columnas / claves / índices
    Meta->>Cache: Buscar resultado cacheado
    alt Datos ya en caché
        Cache-->>Meta: Resultado cacheado
        Meta-->>App: Estructura del esquema (sin ir a BD)
    else Primera consulta del objeto
        Meta->>BD: Consultar metadatos del esquema
        BD-->>Meta: Definiciones del objeto
        Meta->>Cache: Guardar en caché
        Meta-->>App: Estructura del esquema
    end
```

### Flujos alternativos

**Esquema cambiado durante la sesión:** Si otro proceso modifica la BD mientras el extractor está activo, el usuario puede invalidar el caché de una tabla concreta o completo para obtener metadatos actualizados.

**Límites y exclusiones:**

- No modifica ni crea objetos en la base de datos (no ejecuta DDL)
- No ejecuta consultas de datos de negocio: solo accede a la estructura del esquema
- No genera documentación ni informes: eso corresponde al módulo de documentación de BD
- No compara esquemas entre dos bases de datos distintas: eso corresponde al módulo de comparación
- No funciona sin una conexión activa previamente configurada

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Metadatos | Información descriptiva sobre la estructura de la base de datos: nombres de tablas, columnas, tipos, claves e índices; no incluye datos de negocio |
| Caché de sesión | Almacenamiento en memoria que guarda los resultados de introspección durante la vida del extractor para evitar consultas repetidas a la BD |
| Invalidación | Acción de eliminar entradas del caché para forzar que la próxima consulta vaya directamente a la base de datos |
