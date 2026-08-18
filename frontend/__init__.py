"""Frontend / mini-program UI stubs — reserved for future development.

These modules define the UI component interfaces for:
- Score upload and preview
- Natural-language edit input
- Real-time rendering
- Enterprise admin dashboard

They are NOT implemented in this phase. They exist only to reserve the
UI structure and prevent future breaking changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScorePreview:
    """Preview of a reconstructed score."""
    image_url: str = ""
    page_count: int = 0
    part_count: int = 0
    measure_count: int = 0


@dataclass
class EditRequest:
    """User edit request from UI."""
    user_text: str = ""
    target_part: str = ""
    target_measures: list[str] = None


class ScoreUI:
    """Stub UI controller for future mini-program."""

    def upload(self, file_path: str) -> ScorePreview:
        """STUB: upload and preview score."""
        raise NotImplementedError("Frontend not implemented in this phase")

    def apply_edit(self, request: EditRequest) -> bool:
        """STUB: apply user edit."""
        raise NotImplementedError("Frontend not implemented in this phase")
