"""Phase 4: MariaDB JSON Column Schema Introspection Example.

This example demonstrates how to use util_bbdd to infer and extract
JSON column schemas from MariaDB databases programmatically.

Scenario:
    You have MariaDB tables with JSON columns (e.g., events.payload,
    documents.metadata) and want to:
    - Discover JSON structure programmatically
    - Generate API schemas from JSON data
    - Validate incoming JSON payloads
    - Document unstructured data models
    - Build type-safe serialization/deserialization
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema


def main():
    """Main example: Query JSON column schema from MariaDB."""

    # Initialize MariaDB manager
    manager = SyncDatabaseManager(
        db_type="mariadb", conn_params={"host": "localhost", "user": "root", "password": "password", "database": "mydb"}
    )

    # Example: Query JSON column schema
    # Assume table structure:
    #   CREATE TABLE events (
    #       event_id INT PRIMARY KEY AUTO_INCREMENT,
    #       event_type VARCHAR(50),
    #       payload JSON,  -- Contains {user_id, timestamp, action, tags: [...]}
    #       created_at TIMESTAMP
    #   );

    schema_name = "mydb"
    table_name = "events"
    column_name = "payload"

    print(f"Querying JSON schema for {schema_name}.{table_name}.{column_name}\n")

    schema = query_json_column_schema(
        schema=schema_name,
        table=table_name,
        column=column_name,
        adapter=manager.adapter,
        sample_size=100,  # Sample up to 100 rows to infer schema
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
