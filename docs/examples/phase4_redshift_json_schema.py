"""Phase 4: Redshift JSON Column Schema Introspection Example.

This example demonstrates how to use util_bbdd to infer and extract
JSON column schemas from AWS Redshift databases programmatically.

Scenario:
    You have Redshift tables with JSON/VARCHAR columns containing JSON
    (e.g., events.event_data, analytics.raw_logs) and want to:
    - Discover JSON structure from Redshift SUPER or VARCHAR columns
    - Generate data contracts from sampled events
    - Build real-time ETL transformations
    - Document data lake schemas
    - Validate incoming data against inferred schemas
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.redshift.types_advanced import query_json_column_schema


def main():
    """Main example: Query JSON column schema from Redshift."""

    # Initialize Redshift manager
    manager = SyncDatabaseManager(
        db_type="redshift",
        conn_params={
            "host": "my-redshift-cluster.c0000abcd.us-east-1.redshift.amazonaws.com",
            "port": 5439,
            "database": "analytics",
            "user": "admin",
            "password": "YourPassword123!",
        },
    )

    # Example: Query JSON column schema
    # Assume table structure:
    #   CREATE TABLE raw_logs (
    #       log_id BIGINT,
    #       log_timestamp TIMESTAMP,
    #       event_data VARCHAR(MAX),  -- Contains JSON: {user_id, action, properties: {...}}
    #   );

    schema_name = "public"
    table_name = "raw_logs"
    column_name = "event_data"

    print(f"Querying JSON schema from Redshift: {schema_name}.{table_name}.{column_name}\n")

    schema = query_json_column_schema(
        schema=schema_name,
        table=table_name,
        column=column_name,
        adapter=manager.adapter,
        sample_size=1000,  # Sample up to 1000 rows for Redshift (larger sample for data lake)
    )

    if schema is None:
        print("  ❌ Could not infer schema (column empty or not JSON)")
        return

    # Display schema metadata
    print("✅ JSON Schema Inferred from Redshift:")
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
