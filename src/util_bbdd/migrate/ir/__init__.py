"""IR (Intermediate Representation) canónico para migración DDL."""

from .models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    MigrationPlan,
    MigrationWarning,
)

__all__: list[str] = [
    "MigrationWarning",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    "CanonicalTable",
    "MigrationPlan",
]
