"""
Diff Reporters — Generar reportes de diferencias entre esquemas

Este ejemplo demuestra todos los formatos disponibles para exportar comparativas de esquemas:
1. HtmlDiffReporter      — Interactivo con filtrado y búsqueda
2. SqlDiffReporter       — Script SQL para normalizar BDs
3. MarkdownDiffReporter  — Documentación portátil
4. ExcelDiffReporter     — Análisis en hojas de cálculo
5. WordDiffReporter      — Reporte profesional
6. SchemaDiffReporter    — Fachada que maneja todos los reportes
"""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from util_bbdd.comparar import SchemaComparator
from util_bbdd.comparar.reporters import SchemaDiffReporter


def setup_demo_databases():
    """Crea dos esquemas de demo en SQLite para comparar."""

    # BD origen (versión v1)
    source_engine = create_engine("sqlite:///:memory:")
    with source_engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.execute(text("CREATE INDEX idx_users_email ON users(email)"))

        conn.execute(
            text(
                """
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(200),
                content TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
            )
        )
        conn.commit()

    # BD destino (versión v2 con cambios)
    target_engine = create_engine("sqlite:///:memory:")
    with target_engine.connect() as conn:
        # Tabla users modificada (columna extra: role)
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE,
                role VARCHAR(50) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.execute(text("CREATE INDEX idx_users_email ON users(email)"))
        conn.execute(text("CREATE INDEX idx_users_role ON users(role)"))  # Nuevo índice

        # Tabla posts sin cambios
        conn.execute(
            text(
                """
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(200),
                content TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
            )
        )

        # Nueva tabla: comments
        conn.execute(
            text(
                """
            CREATE TABLE comments (
                id INTEGER PRIMARY KEY,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
            )
        )
        conn.commit()

    return source_engine, target_engine


def compare_and_generate_reports():
    """Comparar esquemas y generar todos los reportes."""

    print("=" * 70)
    print("DEMO: Diff Reporters — Generación de Reportes")
    print("=" * 70)

    # 1. Crear BDs de demo
    print("\nCreando esquemas de demo...")
    source_engine, target_engine = setup_demo_databases()

    # 2. Crear inspectors
    source_inspector = inspect(source_engine)
    target_inspector = inspect(target_engine)

    # 3. Comparar esquemas
    print("\nComparando esquemas...")
    comparator = SchemaComparator()
    schema_diff = comparator.compare(
        source=source_inspector,
        target=target_inspector,
        include_tables=True,
        include_indices=True,
        include_foreign_keys=True,
    )

    print(f"Comparacion completada: {schema_diff.summary}")

    # 4. Generar reportes
    print("\nGenerando reportes...")

    # Crear directorio de salida
    output_dir = Path("./demo_reports")
    output_dir.mkdir(exist_ok=True)

    # Usar SchemaDiffReporter (fachada)
    reporter = SchemaDiffReporter()

    # --- HTML (Interactivo) ---
    print("\n  [1/6] HTML...", end="", flush=True)
    html_file = reporter.render(schema_diff, output_dir=output_dir, format="html", filename="schema_diff.html")
    print(f" {html_file}")

    # --- SQL (PostgreSQL) ---
    print("  [2/6] SQL (PostgreSQL)...", end="", flush=True)
    reporter_pg = SchemaDiffReporter(sql_dialect="postgresql")
    sql_file_pg = reporter_pg.render(
        schema_diff,
        output_dir=output_dir,
        format="sql",
        filename="schema_diff_postgresql.sql",
    )
    print(f" {sql_file_pg}")

    # --- SQL (Oracle) ---
    print("  [3/6] SQL (Oracle)...", end="", flush=True)
    reporter_oracle = SchemaDiffReporter(sql_dialect="oracle")
    sql_file_oracle = reporter_oracle.render(
        schema_diff,
        output_dir=output_dir,
        format="sql",
        filename="schema_diff_oracle.sql",
    )
    print(f" {sql_file_oracle}")

    # --- Markdown ---
    print("  [4/6] Markdown...", end="", flush=True)
    md_file = reporter.render(schema_diff, output_dir=output_dir, format="markdown", filename="schema_diff.md")
    print(f" {md_file}")

    # --- Excel ---
    print("  [5/6] Excel...", end="", flush=True)
    excel_file = reporter.render(schema_diff, output_dir=output_dir, format="excel", filename="schema_diff.xlsx")
    print(f" {excel_file}")

    # --- Word ---
    print("  [6/6] Word...", end="", flush=True)
    word_file = reporter.render(schema_diff, output_dir=output_dir, format="word", filename="schema_diff.docx")
    print(f" {word_file}")

    # 5. Usar render_all() (método rápido)
    print("\nAlternativa rapida (render_all)...")
    files = reporter.render_all(schema_diff, output_dir=output_dir)

    print("\nArchivos generados:")
    for file_path in files:
        format_name = file_path.suffix.lstrip(".")
        size = Path(file_path).stat().st_size
        print(f"   - {format_name.upper():12} {size:>8} bytes -> {file_path}")

    # 6. Confirmar salida Markdown
    print("\n" + "=" * 70)
    print("REPORTE MARKDOWN")
    print("=" * 70)
    print(f"Archivo generado: {md_file}")

    print("\n" + "=" * 70)
    print("Demo completada. Reportes guardados en:", output_dir.absolute())
    print("=" * 70)


if __name__ == "__main__":
    compare_and_generate_reports()
