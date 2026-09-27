"""Re-exportación de :mod:`util_bbdd._core.excel_safety` (punto único de escritura segura en Excel)."""

from __future__ import annotations

from ..._core.excel_safety import neutralize_formulas, safe_frame

__all__: list[str] = ["neutralize_formulas", "safe_frame"]
