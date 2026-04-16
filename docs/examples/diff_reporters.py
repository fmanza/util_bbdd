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
    print("\n📦 Creando esquemas de demo...")
    source_engine, target_engine = setup_demo_databases()

    # 2. Crear inspectors
    source_inspector = inspect(source_engine)
    target_inspector = inspect(target_engine)

    # 3. Comparar esquemas
    print("\n🔍 Comparando esquemas...")
    comparator = SchemaComparator()
    schema_diff = comparator.compare(
        source=source_inspector,
        target=target_inspector,
        include_tables=True,
        include_indices=True,
        include_foreign_keys=True,
    )

    print(f"✅ Comparación completada: {schema_diff.summary}")

    # 4. Generar reportes
    print("\n📝 Generando reportes...")

    # Crear directorio de salida
    output_dir = Path("./demo_reports")
    output_dir.mkdir(exist_ok=True)

    # Usar SchemaDiffReporter (fachada)
    reporter = SchemaDiffReporter(schema_diff)

    # --- HTML (Interactivo) ---
    print("\n  [1/6] HTML...", end="", flush=True)
    html_content = reporter.render_html()
    html_file = output_dir / "schema_diff.html"
    html_file.write_text(html_content, encoding="utf-8")
    print(f" ✅ {html_file}")

    # --- SQL (PostgreSQL) ---
    print("  [2/6] SQL (PostgreSQL)...", end="", flush=True)
    sql_content_pg = reporter.render_sql(dialect="postgresql")
    sql_file_pg = output_dir / "schema_diff_postgresql.sql"
    sql_file_pg.write_text(sql_content_pg, encoding="utf-8")
    print(f" ✅ {sql_file_pg}")

    # --- SQL (Oracle) ---
    print("  [3/6] SQL (Oracle)...", end="", flush=True)
    sql_content_oracle = reporter.render_sql(dialect="oracle")
    sql_file_oracle = output_dir / "schema_diff_oracle.sql"
    sql_file_oracle.write_text(sql_content_oracle, encoding="utf-8")
    print(f" ✅ {sql_file_oracle}")

    # --- Markdown ---
    print("  [4/6] Markdown...", end="", flush=True)
    md_content = reporter.render_markdown()
    md_file = output_dir / "schema_diff.md"
    md_file.write_text(md_content, encoding="utf-8")
    print(f" ✅ {md_file}")

    # --- Excel ---
    print("  [5/6] Excel...", end="", flush=True)
    excel_file = output_dir / "schema_diff.xlsx"
    reporter.render_excel(str(excel_file))
    print(f" ✅ {excel_file}")

    # --- Word ---
    print("  [6/6] Word...", end="", flush=True)
    word_file = output_dir / "schema_diff.docx"
    reporter.render_word(str(word_file))
    print(f" ✅ {word_file}")

    # 5. Usar render_all() (método rápido)
    print("\n📦 Alternativa rápida (render_all)...")
    files = reporter.render_all(
        output_dir=str(output_dir),
        basename="schema_comparison_v2",
        include_sql=True,
        sql_dialect="mariadb",  # Generar SQL para MariaDB
    )

    print("\n✅ Archivos generados:")
    for format_name, file_path in files.items():
        size = Path(file_path).stat().st_size
        print(f"   • {format_name.upper():12} {size:>8} bytes  →  {file_path}")

    # 6. Leer y mostrar preview del Markdown
    print("\n" + "=" * 70)
    print("PREVIEW: Primeras líneas del reporte Markdown")
    print("=" * 70)
    md_preview = md_file.read_text(encoding="utf-8").split("\n")[:30]
    print("\n".join(md_preview))

    print("\n" + "=" * 70)
    print("✅ Demo completada. Reportes guardados en:", output_dir.absolute())
    print("=" * 70)


if __name__ == "__main__":
    compare_and_generate_reports()
