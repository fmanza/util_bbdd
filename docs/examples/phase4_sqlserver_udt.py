"""Phase 4: SQL Server User-Defined Type (UDT) Introspection Example.

This example demonstrates how to use util_bbdd to discover and parse
SQL Server user-defined types (structured types) programmatically.

Scenario:
    You have SQL Server UDTs defined (e.g., PersonType, AddressType)
    and want to introspect their members to:
    - Validate data structures programmatically
    - Generate TypeScript/C# interfaces from SQL types
    - Build type-safe ORMs
    - Document API contracts
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlserver.types_advanced import parse_udt_structure


def main():
    """Main example: Parse SQL Server UDT and display member metadata."""

    # Initialize SQL Server manager
    manager = SyncDatabaseManager(
        db_type="sqlserver",
        conn_params={"server": "localhost", "database": "mydb", "user": "sa", "password": "YourPassword123!"},
    )

    # Example: Parse PersonType UDT (assuming it exists in your SQL Server DB)
    # Typical definition:
    #   CREATE TYPE PersonType AS TABLE (
    #       PersonID    INT NOT NULL,
    #       FirstName   VARCHAR(50),
    #       LastName    VARCHAR(50),
    #       EmailAddress VARCHAR(100)
    #   );

    type_name = "PersonType"
    print(f"Introspecting SQL Server UDT: {type_name}\n")

    udt_info = parse_udt_structure(type_name, adapter=manager.adapter)

    if udt_info is None:
        print(f"  ❌ Type '{type_name}' not found or error parsing.")
        return

    # Display UDT metadata
    print(f"✅ UDT: {udt_info.type_name}")
    print(f"   Schema: {udt_info.schema}")
    print(f"   Kind: {udt_info.kind}")  # STRUCTURED, HIERARCHY, or NATIVE
    print(f"   Members: {len(udt_info.members)}\n")

    # Display member-level metadata
    print("Member Details:")
    print("-" * 100)
    for member in udt_info.members:
        nullable_str = "✓ NULL" if member.is_nullable else "✗ NOT NULL"
        max_len_str = f"({member.max_length})" if member.max_length is not None else ""
        precision_str = ""
        if member.precision is not None:
            precision_str = f" ({member.precision}"
            if member.scale is not None:
                precision_str += f", {member.scale}"
            precision_str += ")"

        print(
            f"  {member.ordinal_position:2d}. {member.name:20s} | "
            f"{member.type_name:15s}{max_len_str:10s} | {nullable_str:12s} {precision_str}"
        )

    print("\n" + "=" * 100)
    print("Member Metadata (Serializable):")
    print("=" * 100)
    for member in udt_info.members:
        member_dict = member.to_dict()
        print(f"\n{member.name}:")
        for key, value in member_dict.items():
            print(f"  {key}: {value}")

    manager.close()
    print("\n✅ Example completed successfully.")


if __name__ == "__main__":
    main()
