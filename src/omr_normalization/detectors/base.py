"""Base class for OMR detectors.

A detector consumes an lxml ElementTree of a MusicXML document and
returns a list of OMRIssue objects. Detectors are stateless and must not
mutate the input tree.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lxml import etree

from omr_normalization.issue_model import OMRIssue


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class OMRDetector(ABC):
    """Abstract base class for all OMR detectors."""

    name: str = ""

    @abstractmethod
    def detect(self, tree: etree._ElementTree, input_path: str = "") -> list[OMRIssue]:
        """Return a list of OMRIssue objects for the given MusicXML tree."""
        ...

    def _provenance(self) -> dict[str, Any]:
        return {"detector": self.name}

    def _make_issue(
        self,
        issue_id: str,
        category: str,
        check: str,
        status: str,
        severity: str,
        description: str,
        edit_safety: str = "",
        part_id: str = "",
        measure_number: str = "",
        voice_id: str = "",
        note_id: str = "",
        evidence: dict[str, Any] | None = None,
        fix: dict[str, Any] | None = None,
    ) -> OMRIssue:
        return OMRIssue(
            issue_id=issue_id,
            category=category,
            check=check,
            status=status,
            severity=severity,
            edit_safety=edit_safety,
            part_id=part_id,
            measure_number=measure_number,
            voice_id=voice_id,
            note_id=note_id,
            description=description,
            evidence=evidence or {},
            fix=fix,
            provenance=self._provenance(),
        )
