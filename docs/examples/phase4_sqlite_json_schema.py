"""Phase 4: SQLite JSON Column Schema Introspection Example.

This example demonstrates how to use util_bbdd to infer and extract
JSON column schemas from SQLite databases programmatically.

Scenario:
    You have SQLite tables with JSON columns (e.g., logs.metadata,
    documents.data) and want to:
    - Discover JSON structure programmatically
    - Generate type hints from JSON samples
    - Build validation rules dynamically
    - Export data with schema documentation
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema


def main():
    """Main example: Query JSON column schema from SQLite."""

    # Initialize SQLite manager
    manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": "/path/to/mydb.sqlite3"})

    # Example: Query JSON column schema
    # Assume table structure:
    #   CREATE TABLE documents (
    #       doc_id INTEGER PRIMARY KEY,
    #       title TEXT,
    #       metadata JSON,  -- Contains {author, tags, created_date, ...}
    #       created_at TIMESTAMP
    #   );

    schema_name = "main"  # SQLite: "main" for main database
    table_name = "documents"
    column_name = "metadata"

    print(f"Querying JSON schema for {table_name}.{column_name}\n")

    schema = query_json_column_schema(
        schema=schema_name, table=table_name, column=column_name, adapter=manager.adapter, sample_size=100
    )

    if schema is None:
        print("  ❌ Could not infer schema (column empty or not JSON)")
        return

    # Display schema metadata
    print(f"✅ JSON Schema Detected for {column_name}:")
    print(f"   Root Type: {schema.get('type', 'unknown')}")
    print(f"   Properties: {len(schema.get('properties', {}))}")
    print(f"   Required Fields: {schema.get('required', [])}\n")

    # Display property-level details
    if "properties" in schema:
        print("Property Details:")
        print("-" * 80)
        for prop_name, prop_def in schema["properties"].items():
            prop_type = prop_def.get("type", "unknown")
            required_marker = "✓ REQUIRED" if prop_name in schema.get("required", []) else "⚠️ OPTIONAL"
            print(f"  • {prop_name:25s} | Type: {prop_type:15s} | {required_marker}")

    print("\n" + "=" * 80)
    print("Full Schema (JSON):")
    print("=" * 80)
    import json

    print(json.dumps(schema, indent=2))

    manager.close()
    print("\n✅ Example completed successfully.")


if __name__ == "__main__":
    main()
