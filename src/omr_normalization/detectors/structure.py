"""Structure detector for raw OMR MusicXML.

Detects measure-level structural defects: missing measures, empty
measures, and cross-part measure-count mismatches. No auto-fixes are
performed; missing measures are reported as OMR errors because inventing
musical content (even rests) is not a deterministic structural decision.
"""

from __future__ import annotations

from lxml import etree

from omr_normalization.detectors.base import OMRDetector, _local
from omr_normalization.issue_model import OMRCategory, OMREditSafety, OMRIssue, OMRStatus


class StructureDetector(OMRDetector):
    """Detect structural defects in raw OMR MusicXML."""

    name = "structure"

    def detect(self, tree: etree._ElementTree, input_path: str = "") -> list[OMRIssue]:
        issues: list[OMRIssue] = []
        root = tree.getroot()
        part_measure_counts: dict[str, int] = {}

        for part_elem in root.findall(".//part"):
            part_id = part_elem.get("id", "P?")
            measures = part_elem.findall("measure")
            part_measure_counts[part_id] = len(measures)

            nums: list[int] = []
            for meas in measures:
                mn = meas.get("number", "?")
                try:
                    nums.append(int(mn))
                except ValueError:
                    # Non-integer measure numbers are accepted but not checked for gaps.
                    continue

                # Empty measure check
                has_event = any(
                    _local(child.tag) in ("note", "forward", "backup", "direction")
                    for child in meas
                )
                if not has_event:
                    issues.append(
                        self._make_issue(
                            issue_id=f"STR-EMPTY-{part_id}-M{mn}",
                            category=OMRCategory.STRUCTURE,
                            check="empty_measure",
                            status=OMRStatus.OMR_ERROR,
                            severity="high",
                            edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                            part_id=part_id,
                            measure_number=mn,
                            description=(
                                f"Measure {mn} in {part_id} contains no events — "
                                f"OMR emitted an empty measure"
                            ),
                        )
                    )

            # Missing measure gaps (only for integer, sequential numbering)
            if len(nums) >= 2:
                for prev, cur in zip(nums, nums[1:]):
                    if cur > prev + 1:
                        for gap in range(prev + 1, cur):
                            issues.append(
                                self._make_issue(
                                    issue_id=f"STR-MISSING-{part_id}-M{gap}",
                                    category=OMRCategory.STRUCTURE,
                                    check="missing_measure",
                                    status=OMRStatus.OMR_ERROR,
                                    severity="high",
                                    edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                                    part_id=part_id,
                                    measure_number=str(gap),
                                    description=(
                                        f"Measure {gap} missing from {part_id} — "
                                        f"OMR did not emit this measure number"
                                    ),
                                )
                            )

        # Cross-part measure count consistency
        if len(part_measure_counts) > 1:
            counts = list(part_measure_counts.values())
            if min(counts) != max(counts):
                issues.append(
                    self._make_issue(
                        issue_id="STR-COUNT-MISMATCH",
                        category=OMRCategory.STRUCTURE,
                        check="part_measure_count_mismatch",
                        status=OMRStatus.OMR_ERROR,
                        severity="high",
                        edit_safety=OMREditSafety.BLOCKING_FOR_EDIT,
                        description=(
                            f"Parts have different measure counts: {part_measure_counts}"
                        ),
                        evidence={"counts": part_measure_counts},
                    )
                )

        return issues
