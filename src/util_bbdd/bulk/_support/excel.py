"""Re-exportación de :mod:`util_bbdd._core.export_safety` (punto único de escritura segura en Excel)."""

from __future__ import annotations

from ..._core.export_safety import neutralize_formulas, safe_frame

__all__: list[str] = ["neutralize_formulas", "safe_frame"]
