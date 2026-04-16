"""
Schema Comparison — Detectar diferencias entre BDs

Este ejemplo muestra cómo:
1. Conectar a dos BDs (o dos schemas)
2. Comparar estructura
3. Generar reporte de cambios
4. Exportar resultados a JSON
"""

import json

from sqlalchemy import create_engine, inspect, text

from util_bbdd.comparar import SchemaComparator


def demonstrate_schema_comparison():
    """Comparar dos esquemas de BD."""

    # 1. Crear BDs en memoria para demostración
    # En producción, usar BDs reales

    # BD "vieja" (origen)
    source_engine = create_engine("sqlite:///:memory:")
    with source_engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100),
                created_at TIMESTAMP
            )
        """
            )
        )
        conn.commit()

    # BD "nueva" (destino) con cambios
    target_engine = create_engine("sqlite:///:memory:")
    with target_engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100),
                age INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """
            )
        )
        conn.execute(text("CREATE INDEX idx_email ON users(email)"))
        conn.commit()

    # 2. Crear inspectors de SQLAlchemy
    source_inspector = inspect(source_engine)
    target_inspector = inspect(target_engine)

    # 3. Comparar esquemas
    comparator = SchemaComparator()
    diff = comparator.compare(
        source=source_inspector,
        target=target_inspector,
        include_tables=True,
        include_indices=True,
        include_comments=False,
    )

    # 4. Generar reporte
    print("=" * 70)
    print("COMPARACIÓN DE ESQUEMAS")
    print("=" * 70)
    print(f"\nOrigen: {diff.source_label}")
    print(f"Destino: {diff.target_label}")
    print(f"Resumen: {diff.summary}\n")

    # 5. Mostrar diferencias por tabla
    for table_diff in diff.table_diffs:
        if table_diff.status != "unmodified":
            print(f"📋 Tabla '{table_diff.table_name}': {table_diff.status.upper()}")

            # Columnas nuevas/eliminadas
            if table_diff.column_diffs:
                for col_diff in table_diff.column_diffs:
                    print(f"   📝 {col_diff.column_name}:")
                    print(f"      Atributo: {col_diff.attribute}")
                    print(f"      Origen:   {col_diff.source_value}")
                    print(f"      Destino:  {col_diff.target_value}")

            # Índices nuevos
            if table_diff.index_diffs:
                for idx_diff in table_diff.index_diffs:
                    print(f"   🔑 Índice '{idx_diff.index_name}': {idx_diff.status}")

    # 6. Exportar a JSON
    print("\n" + "=" * 70)
    print("EXPORTAR A JSON")
    print("=" * 70)

    result_dict = {
        "source": diff.source_label,
        "target": diff.target_label,
        "summary": diff.summary,
        "tables": [
            {
                "name": td.table_name,
                "status": td.status,
                "columns": [
                    {
                        "name": cd.column_name,
                        "change": f"{cd.attribute}: {cd.source_value} → {cd.target_value}",
                    }
                    for cd in td.column_diffs
                ],
                "indices": [{"name": id.index_name, "status": id.status} for id in td.index_diffs],
            }
            for td in diff.table_diffs
        ],
    }

    print(json.dumps(result_dict, indent=2))

    # 7. Generar reportes de diferencias usando SchemaDiffReporter
    print("\n" + "=" * 70)
    print("GENERACIÓN DE REPORTES CON REPORTERS")
    print("=" * 70)

    from pathlib import Path

    from util_bbdd.comparar.reporters import SchemaDiffReporter

    # Crear directorio de salida para reportes
    output_dir = Path("./schema_comparison_reports")
    output_dir.mkdir(exist_ok=True)

    reporter = SchemaDiffReporter(diff)

    # 7a. Generar reporte HTML (con Mermaid)
    html_output = output_dir / "schema_diff.html"
    html_content = reporter.render_html()
    html_output.write_text(html_content, encoding="utf-8")
    print(f"\n✅ Reporte HTML generado: {html_output}")

    # 7b. Generar script SQL para normalizar destino a origen (por defecto SQLite)
    sql_output = output_dir / "schema_diff.sql"
    sql_content = reporter.render_sql()  # Usa dialecto del engine de destino si está disponible
    sql_output.write_text(sql_content, encoding="utf-8")
    print(f"✅ Script SQL generado: {sql_output}")

    # 7c. Generar reporte Markdown (con tablas)
    md_output = output_dir / "schema_diff.md"
    md_content = reporter.render_markdown()
    md_output.write_text(md_content, encoding="utf-8")
    print(f"✅ Reporte Markdown generado: {md_output}")

    # 7d. Generar reporte Excel (múltiples hojas por sección)
    excel_output = output_dir / "schema_diff.xlsx"
    reporter.render_excel(str(excel_output))
    print(f"✅ Reporte Excel generado: {excel_output}")

    # 7e. Generar reporte Word
    word_output = output_dir / "schema_diff.docx"
    reporter.render_word(str(word_output))
    print(f"✅ Reporte Word generado: {word_output}")

    # 7f. Generar todos los reportes de una vez (alternativa rápida)
    print("\n--- Alternativa: render_all() ---")
    files = reporter.render_all(str(output_dir), basename="schema_comparison")
    print(f"✅ Reportes generados: {', '.join(files.values())}")


if __name__ == "__main__":
    demonstrate_schema_comparison()
