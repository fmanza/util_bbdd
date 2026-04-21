"""Advanced Redshift Type System Support — Phase 4b.1.

Provides introspection for Redshift types with graceful fallback:
- Redshift is based on PostgreSQL 8.x (ancient by modern standards)
- Most deployments DO NOT have user-defined composite types
- Strategy: Detect capabilities → gracefully return None if unavailable
- If types somehow exist (rare): future extension point

Module Pattern:
    - Minimal implementation (MVP fallback approach)
    - Delegates to PostgreSQL logic if types detected (future)
    - Always graceful: None return instead of error
    - Logs all type resolution attempts for debugging

Example:
    >>> adapter = RedshiftSyncAdapter(manager)
    >>> type_info = parse_redshift_types("some_type", adapter)
    >>> type_info  # Typical: None (types not available)
    None
"""

import logging

from dataclasses import dataclass
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# REDSHIFT TYPE STRUCTURES
# ============================================================================


@dataclass(frozen=True, slots=True)
class RedshiftTypeInfo:
    """Metadata for Redshift type (placeholder for future extension).

    Note: Most Redshift deployments do NOT have composite types available.
    This class exists for future extension when/if type support is added.
    """

    type_name: str
    note: str = "Redshift composite types typically unavailable (PostgreSQL 8.x base)"


# ============================================================================
# REDSHIFT TYPE INTROSPECTION (Phase 4b.1 - MVP Fallback)
# ============================================================================


def parse_redshift_types(
    type_name: str,
    adapter: Any,
) -> RedshiftTypeInfo | None:
    """Parse Redshift type with graceful fallback for unsupported types.

    Redshift is based on PostgreSQL 8.x, which predates modern composite type
    support in PostgreSQL. This function gracefully handles the fact that
    most Redshift deployments do NOT have user-defined composite types available.

    Strategy:
    1. Check if pg_type catalog supports composite types (rare)
    2. If yes: return placeholder (for future extension)
    3. If no: return None with debug logging
    4. On error: return None gracefully (never raise)

    Args:
        type_name: Name of type to parse
        adapter: Manager adapter with _execute_metadata_many and logger

    Returns:
        None: Composite types not available (typical for Redshift)
        RedshiftTypeInfo: Type found (rare; for future extension)

    Example:
        >>> adapter = RedshiftSyncAdapter(manager)
        >>> result = parse_redshift_types("custom_type", adapter)
        >>> result  # Typical case: None
        None

    Notes:
        - Redshift: PostgreSQL 8.x heritage means no modern composite types
        - All paths return None (MVP: types not fully supported yet)
        - Logging provided for debug purposes
        - Future: extend this to parse if Redshift adds type support
    """
    logger.debug(f"Checking Redshift type support for '{type_name}'")

    try:
        # Step 1: Try to check if type exists in pg_type catalog (rare for Redshift)
        params: dict[str, Any] = {"type_name": type_name}

        rows = adapter._execute_metadata_many(
            query_name="fetch_redshift_type_info",
            params=params,
            error_message=f"Failed to check type availability for {type_name}",
        )

        if not rows:
            logger.debug(
                f"Redshift: type '{type_name}' not found in pg_type catalog (expected for PostgreSQL 8.x base)"
            )
            return None

        # Step 2: Type exists (unexpected for most Redshift deployments)
        # For MVP, still return None (types not fully supported)
        # Future: could extend to parse like PostgreSQL if needed
        adapter.logger.info(
            f"Redshift: unexpected type found in catalog: '{type_name}' (consider extending parser for this deployment)"
        )
        return None

    except Exception as e:
        # Step 3: Graceful error handling - never raise, always return None
        adapter.logger.debug(f"Redshift type parsing: '{type_name}' unavailable ({type(e).__name__}: {str(e)})")
        return None
