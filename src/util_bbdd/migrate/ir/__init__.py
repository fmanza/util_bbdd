"""IR (Intermediate Representation) canónico para migración DDL."""

from .models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationPlan,
    MigrationWarning,
    WarningCategory,
)

__all__: list[str] = [
    "MigrationWarning",
    "WarningCategory",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    "CanonicalTable",
    "CanonicalView",
    "CanonicalRoutine",
    "MigrationPlan",
]
