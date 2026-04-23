"""Phase 4: Oracle OBJECT Type Introspection Example.

This example demonstrates how to use util_bbdd to discover and parse
Oracle user-defined OBJECT types programmatically.

Scenario:
    You have Oracle OBJECT types defined in your database (e.g., CUSTOMER_TYPE,
    ADDRESS_TYPE) and want to introspect their structure programmatically to:
    - Generate API documentation
    - Build dynamic form validators
    - Synchronize type definitions across environments
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.oracle.types_advanced import parse_object_type_structure


def main():
    """Main example: Parse Oracle OBJECT types and display field metadata."""

    # Initialize Oracle manager
    manager = SyncDatabaseManager(db_type="oracle", conn_params={"dsn": "ORCL", "user": "scott", "password": "tiger"})

    # Example: Parse CUSTOMER_TYPE (assuming it exists in your Oracle DB)
    # Typical definition:
    #   CREATE TYPE CUSTOMER_TYPE AS OBJECT (
    #       customer_id NUMBER(10),
    #       first_name VARCHAR2(50),
    #       last_name VARCHAR2(50),
    #       created_date DATE
    #   );

    type_name = "CUSTOMER_TYPE"
    print(f"Introspecting Oracle OBJECT type: {type_name}\n")

    type_info = parse_object_type_structure(type_name, adapter=manager.adapter)

    if type_info is None:
        print(f"  ❌ Type '{type_name}' not found or error parsing.")
        return

    # Display type metadata
    print(f"✅ Type: {type_info.type_name}")
    print(f"   Owner (Schema): {type_info.owner}")
    print(f"   Fields: {len(type_info.fields)}\n")

    # Display field-level metadata
    print("Field Details:")
    print("-" * 80)
    for field in type_info.fields:
        nullable_str = "✓ NULL" if field.is_nullable else "✗ NOT NULL"
        precision_str = ""
        if field.precision is not None:
            precision_str = f" ({field.precision}"
            if field.scale is not None:
                precision_str += f", {field.scale}"
            precision_str += ")"

        print(
            f"  {field.ordinal_position:2d}. {field.name:20s} | "
            f"{field.type_name:15s} | {nullable_str:12s} {precision_str}"
        )

    print("\n" + "=" * 80)
    print("Field Metadata (Serializable):")
    print("=" * 80)
    for field in type_info.fields:
        field_dict = field.to_dict()
        print(f"\n{field.name}:")
        for key, value in field_dict.items():
            print(f"  {key}: {value}")

    manager.close()
    print("\n✅ Example completed successfully.")


if __name__ == "__main__":
    main()
